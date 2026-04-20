import { useState, useEffect } from 'react'
import { getExecutorTasks, acceptAssignment, disputeAssignment } from '../api'
import { useUser } from '../UserContext'

const DEPTS = ['ДОЭ', 'ДУКО', 'ДПОТ', 'УДЦТиЭ']

const STATUS_LABEL = {
  ASSIGNED: 'Назначено',
  ACCEPTED: 'Принято',
  DISPUTED: 'На рассмотрении у руководителя',
}
const STATUS_CLASS = {
  ASSIGNED: 'badge-medium',
  ACCEPTED: 'badge-green',
  DISPUTED: 'badge-yellow',
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export default function ExecutorInbox() {
  const { currentUser } = useUser()
  const executorId = currentUser?.employee_id || ''

  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionLoading, setActionLoading] = useState({})
  const [disputeOpen, setDisputeOpen] = useState({})
  const [disputeDept, setDisputeDept] = useState({})
  const [disputeComment, setDisputeComment] = useState({})

  const load = async () => {
    if (!executorId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getExecutorTasks(executorId)
      setTasks(Array.isArray(data) ? data : [])
    } catch (e) {
      setError('Не удалось загрузить задачи: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [executorId])

  const handleAccept = async (id) => {
    setActionLoading(prev => ({ ...prev, [id]: 'accept' }))
    try {
      await acceptAssignment(id)
      setTasks(prev => prev.map(t => t.id === id ? { ...t, status: 'ACCEPTED' } : t))
    } catch (e) {
      setError('Ошибка при принятии: ' + e.message)
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: null }))
    }
  }

  const handleDispute = async (id) => {
    const dept = disputeDept[id]
    if (!dept) return
    setActionLoading(prev => ({ ...prev, [id]: 'dispute' }))
    try {
      await disputeAssignment(id, dept, disputeComment[id] || '')
      setTasks(prev => prev.map(t => t.id === id ? { ...t, status: 'DISPUTED', disputed_dept: dept } : t))
      setDisputeOpen(prev => ({ ...prev, [id]: false }))
    } catch (e) {
      setError('Ошибка при оспаривании: ' + e.message)
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: null }))
    }
  }

  return (
    <div className="container">
      <div className="inbox-header">
        <div>
          <h1>Мои поручения</h1>
          <p className="text-muted">{currentUser?.name} · {currentUser?.dept_code || '—'}</p>
        </div>
        <button className="btn btn-secondary" onClick={load} disabled={loading}>
          {loading ? 'Загрузка...' : 'Обновить'}
        </button>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {!loading && tasks.length === 0 && (
        <div className="card">
          <div className="empty-state">
            <p>Нет назначенных поручений</p>
            <p className="text-muted" style={{ marginTop: 8 }}>
              Поручения появятся здесь после назначения руководителем
            </p>
          </div>
        </div>
      )}

      {tasks.map(task => {
        const busy = actionLoading[task.id]
        const isDisputed = task.status === 'DISPUTED'
        const isDone = task.status === 'ACCEPTED' || isDisputed
        const showDisputeForm = disputeOpen[task.id]

        return (
          <div key={task.id} className="card">
            <div style={{ marginBottom: 10 }}>
              <span className={`badge ${STATUS_CLASS[task.status] || 'badge-medium'}`}>
                {STATUS_LABEL[task.status] || task.status}
              </span>
              {task.assigned_dept && (
                <span className="badge badge-medium" style={{ marginLeft: 8 }}>
                  {task.assigned_dept}
                </span>
              )}
            </div>

            <p style={{ fontSize: 15, lineHeight: 1.6, marginBottom: 10 }}>{task.text}</p>

            <div className="meta">
              <span className="text-muted">Создано: {formatDate(task.created_at)}</span>
              {task.due_date && <span className="text-muted">Срок: {formatDate(task.due_date)}</span>}
              {task.assigned_at && <span className="text-muted">Назначено: {formatDate(task.assigned_at)}</span>}
              <span className={`badge ${task.priority === 'HIGH' ? 'badge-red' : task.priority === 'LOW' ? 'badge-green' : 'badge-medium'}`}>
                {task.priority}
              </span>
            </div>

            {task.manager_comment && (
              <p className="text-muted" style={{ marginTop: 8, fontStyle: 'italic' }}>
                Комментарий: {task.manager_comment}
              </p>
            )}

            {isDisputed && task.disputed_dept && (
              <p style={{ marginTop: 8, color: '#92400e', fontSize: 13 }}>
                Вы указали ответственное подразделение: <strong>{task.disputed_dept}</strong>. Ожидает решения руководителя.
              </p>
            )}

            {!isDone && !showDisputeForm && (
              <div className="actions" style={{ marginTop: 16 }}>
                <button
                  className="btn btn-success"
                  disabled={!!busy}
                  onClick={() => handleAccept(task.id)}
                >
                  {busy === 'accept' ? 'Обработка...' : 'Принять'}
                </button>
                <button
                  className="btn btn-danger"
                  disabled={!!busy}
                  onClick={() => setDisputeOpen(prev => ({ ...prev, [task.id]: true }))}
                >
                  Не согласен
                </button>
              </div>
            )}

            {!isDone && showDisputeForm && (
              <div style={{ marginTop: 16, padding: '16px', background: '#fff7ed', borderRadius: 8, border: '1px solid #fed7aa' }}>
                <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: '#92400e' }}>
                  Укажите ответственное подразделение
                </p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                  <div>
                    <label style={{ fontSize: 12, color: '#555', display: 'block', marginBottom: 4 }}>
                      Подразделение
                    </label>
                    <select
                      className="select-field"
                      value={disputeDept[task.id] || ''}
                      onChange={e => setDisputeDept(prev => ({ ...prev, [task.id]: e.target.value }))}
                    >
                      <option value="">— выберите —</option>
                      {DEPTS.filter(d => d !== task.assigned_dept).map(d => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>
                  <div style={{ flex: 1, minWidth: 160 }}>
                    <label style={{ fontSize: 12, color: '#555', display: 'block', marginBottom: 4 }}>
                      Комментарий (необязательно)
                    </label>
                    <input
                      type="text"
                      placeholder="Причина..."
                      value={disputeComment[task.id] || ''}
                      onChange={e => setDisputeComment(prev => ({ ...prev, [task.id]: e.target.value }))}
                      style={{ padding: '7px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 14, width: '100%' }}
                    />
                  </div>
                  <button
                    className="btn btn-danger"
                    disabled={!disputeDept[task.id] || !!busy}
                    onClick={() => handleDispute(task.id)}
                  >
                    {busy === 'dispute' ? 'Отправка...' : 'Отправить на пересмотр'}
                  </button>
                  <button
                    className="btn btn-secondary"
                    disabled={!!busy}
                    onClick={() => setDisputeOpen(prev => ({ ...prev, [task.id]: false }))}
                  >
                    Отмена
                  </button>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
