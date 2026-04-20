import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getAssignment, confirmAssignment } from '../api'
import { useUser } from '../UserContext'

const ZONE_CLASS = { GREEN: 'badge-green', YELLOW: 'badge-yellow', RED: 'badge-red' }
const ZONE_LABEL = { GREEN: 'Высокая', YELLOW: 'Средняя', RED: 'Низкая' }

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function AssignmentCard() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { currentUser } = useUser()
  const [task, setTask] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [mode, setMode] = useState(null) // null | 'top3' | 'manual'
  const [selectedTop3, setSelectedTop3] = useState('')
  const [manualTo, setManualTo] = useState('')
  const [manualDept, setManualDept] = useState('')
  const [comment, setComment] = useState('')

  useEffect(() => {
    setLoading(true)
    getAssignment(id)
      .then(data => { setTask(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [id])

  const doConfirm = async (action, overrides = {}) => {
    setSubmitting(true)
    setError(null)
    try {
      await confirmAssignment(id, {
        action,
        comment: comment || null,
        assigned_by: currentUser?.employee_id,
        ...overrides,
      })
      navigate('/manager')
    } catch (e) {
      setError('Ошибка: ' + e.message)
      setSubmitting(false)
    }
  }

  if (loading) return <div className="container"><div className="loading">Загрузка...</div></div>
  if (!task) return <div className="container"><div className="error-msg">{error || 'Задача не найдена'}</div></div>

  const top3 = Array.isArray(task.top3_json)
    ? task.top3_json
    : (task.top3_json ? JSON.parse(task.top3_json) : [])

  return (
    <div className="container">
      <button className="btn btn-secondary" style={{ marginBottom: 16 }} onClick={() => navigate('/manager')}>
        ← Назад
      </button>

      <div className="card">
        <h1 style={{ marginBottom: 8 }}>Поручение</h1>
        <div className="meta">
          <span className="text-muted">Автор: {task.author_id || '—'}</span>
          <span className="text-muted">Создано: {formatDate(task.created_at)}</span>
          {task.due_date && <span className="text-muted">Срок: {formatDate(task.due_date)}</span>}
          <span className={`badge badge-medium`}>{task.priority}</span>
          <span className="badge badge-medium">{task.status}</span>
        </div>
        <p style={{ marginTop: 16, lineHeight: 1.6, fontSize: 15 }}>{task.text}</p>
      </div>

      {task.suggested_dept && (
        <div className="suggestion-box">
          <h3>Предложение системы</h3>
          <div className="meta">
            <span><strong>Подразделение:</strong> {task.suggested_dept}</span>
            <span><strong>Исполнитель:</strong> {task.suggested_executor}</span>
            {task.confidence_zone && (
              <span className={`badge ${ZONE_CLASS[task.confidence_zone] || 'badge-medium'}`}>
                {ZONE_LABEL[task.confidence_zone] || task.confidence_zone}
                {task.confidence ? ` · ${Math.round(task.confidence * 100)}%` : ''}
              </span>
            )}
          </div>
          {task.justification && (
            <div className="justification">
              {task.justification.split('\n').map((line, i) => (
                <div key={i} style={{ marginBottom: i < task.justification.split('\n').length - 1 ? 6 : 0 }}>
                  {line}
                </div>
              ))}
            </div>
          )}

          {top3.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="text-muted">Топ-3 подразделения:</div>
              <ul className="top3-list">
                {top3.map((item, i) => (
                  <li key={i}>
                    <span className="badge badge-medium">{item.department_code}</span>
                    <span className="text-muted">{Math.round((item.confidence || 0) * 100)}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {task.status === 'DISPUTED' && task.disputed_dept && (
        <div className="card" style={{ borderLeft: '4px solid #f59e0b', background: '#fffbeb' }}>
          <h3 style={{ color: '#92400e', marginBottom: 8 }}>Исполнитель не согласен</h3>
          <p style={{ fontSize: 14, color: '#78350f' }}>
            Исполнитель <strong>{task.assigned_to}</strong> считает, что поручение относится к подразделению{' '}
            <strong>{task.disputed_dept}</strong>.
          </p>
          {task.manager_comment && (
            <p style={{ fontSize: 13, marginTop: 6, fontStyle: 'italic', color: '#92400e' }}>
              Комментарий: {task.manager_comment}
            </p>
          )}
        </div>
      )}

      {error && <div className="error-msg">{error}</div>}

      <div className="card">
        <h2>Решение руководителя</h2>

        <div style={{ marginTop: 12 }}>
          <label style={{ fontSize: 13, color: '#555', display: 'block', marginBottom: 6 }}>
            Комментарий (необязательно)
          </label>
          <input
            type="text"
            value={comment}
            onChange={e => setComment(e.target.value)}
            placeholder="Добавить комментарий..."
            style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 14, marginBottom: 16 }}
          />
        </div>

        <div className="actions">
          {task.status === 'DISPUTED' ? (
            <button
              className="btn btn-success"
              disabled={submitting}
              onClick={() => doConfirm('CORRECTED', { assigned_dept: task.disputed_dept })}
            >
              {submitting ? 'Обработка...' : `Подтвердить: ${task.disputed_dept}`}
            </button>
          ) : (
            <button
              className="btn btn-success"
              disabled={submitting || !task.suggested_dept}
              onClick={() => doConfirm('ACCEPTED')}
            >
              {submitting ? 'Обработка...' : 'Принять предложение системы'}
            </button>
          )}

          {top3.length > 0 && (
            <button
              className="btn btn-primary"
              disabled={submitting}
              onClick={() => setMode(mode === 'top3' ? null : 'top3')}
            >
              Выбрать из топ-3
            </button>
          )}

          <button
            className="btn btn-secondary"
            disabled={submitting}
            onClick={() => setMode(mode === 'manual' ? null : 'manual')}
          >
            Назначить вручную
          </button>
        </div>

        {mode === 'top3' && top3.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <label style={{ fontSize: 13, color: '#555', display: 'block', marginBottom: 6 }}>
              Выберите подразделение из топ-3:
            </label>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <select
                className="select-field"
                value={selectedTop3}
                onChange={e => setSelectedTop3(e.target.value)}
              >
                <option value="">— выберите —</option>
                {top3.map((item, i) => (
                  <option key={i} value={item.department_code}>
                    {item.department_code} ({Math.round((item.confidence || 0) * 100)}%)
                  </option>
                ))}
              </select>
              <button
                className="btn btn-primary"
                disabled={!selectedTop3 || submitting}
                onClick={() => doConfirm('CORRECTED', { assigned_dept: selectedTop3 })}
              >
                Подтвердить
              </button>
            </div>
          </div>
        )}

        {mode === 'manual' && (
          <div style={{ marginTop: 16 }}>
            <div className="manual-row">
              <input
                type="text"
                value={manualTo}
                onChange={e => setManualTo(e.target.value)}
                placeholder="ID исполнителя (напр. EMP_001)"
              />
              <input
                type="text"
                value={manualDept}
                onChange={e => setManualDept(e.target.value)}
                placeholder="Код отдела (напр. ДОЭ)"
              />
              <button
                className="btn btn-primary"
                disabled={!manualTo || submitting}
                onClick={() => doConfirm('MANUAL', {
                  assigned_to: manualTo,
                  assigned_dept: manualDept || undefined,
                })}
              >
                Назначить
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
