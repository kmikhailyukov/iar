import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getManagerTasks } from '../api'
import { useUser } from '../UserContext'

const ZONE_LABEL = { GREEN: 'Высокая', YELLOW: 'Средняя', RED: 'Низкая' }
const ZONE_CLASS = { GREEN: 'badge-green', YELLOW: 'badge-yellow', RED: 'badge-red' }
const STATUS_BADGE = { DISPUTED: 'badge-yellow' }
const PRIORITY_CLASS = { HIGH: 'badge-red', MEDIUM: 'badge-medium', LOW: 'badge-green' }
const STATUS_LABEL = { NEW: 'Новое', CLASSIFIED: 'Классифицировано', ASSIGNED: 'Назначено', DISPUTED: 'Оспорено исполнителем' }

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export default function ManagerInbox() {
  const { currentUser } = useUser()
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getManagerTasks()
      setTasks(Array.isArray(data) ? data : [])
    } catch (e) {
      setError('Не удалось загрузить задачи: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // Директор отдела видит только поручения своего отдела; ГД и ADMIN — все
  const visibleTasks = currentUser?.dept_code
    ? tasks.filter(t =>
        t.suggested_dept === currentUser.dept_code ||
        t.assigned_dept === currentUser.dept_code ||
        t.disputed_dept === currentUser.dept_code
      )
    : tasks

  const disputedCount = visibleTasks.filter(t => t.status === 'DISPUTED').length

  return (
    <div className="container">
      <div className="inbox-header">
        <div>
          <h1>Входящие поручения</h1>
          <p className="text-muted">
            {currentUser?.name}
            {currentUser?.dept_code ? ` · ${currentUser.dept_code}` : ' · все подразделения'}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {disputedCount > 0 && (
            <span className="badge badge-yellow">{disputedCount} оспорено</span>
          )}
          <button className="btn btn-secondary" onClick={load} disabled={loading}>
            {loading ? 'Загрузка...' : 'Обновить'}
          </button>
        </div>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {!loading && visibleTasks.length === 0 && (
        <div className="card">
          <div className="empty-state">
            <p>Нет задач, требующих внимания</p>
            <p className="text-muted" style={{ marginTop: 8 }}>
              Новые поручения появятся здесь после обработки системой
            </p>
          </div>
        </div>
      )}

      {visibleTasks.map(task => (
        <div
          key={task.id}
          className="card"
          style={{
            cursor: 'pointer',
            borderLeft: task.status === 'DISPUTED' ? '4px solid #f59e0b' : undefined,
          }}
          onClick={() => navigate(`/manager/${task.id}`)}
        >
          <div className="task-row">
            <div className="task-info">
              <div className="task-text">{task.text}</div>
              <div className="task-meta">
                <span className={`badge ${PRIORITY_CLASS[task.priority] || 'badge-medium'}`}>
                  {task.priority}
                </span>
                <span className={`badge ${STATUS_BADGE[task.status] || 'badge-medium'}`}>
                  {STATUS_LABEL[task.status] || task.status}
                </span>
                {task.suggested_dept && (
                  <span className="badge badge-medium">{task.suggested_dept}</span>
                )}
                {task.status === 'DISPUTED' && task.disputed_dept && (
                  <span className="badge badge-yellow">→ {task.disputed_dept}</span>
                )}
                {task.confidence_zone && (
                  <span className={`badge ${ZONE_CLASS[task.confidence_zone] || 'badge-medium'}`}>
                    {ZONE_LABEL[task.confidence_zone] || task.confidence_zone}
                    {task.confidence ? ` · ${Math.round(task.confidence * 100)}%` : ''}
                  </span>
                )}
                <span className="text-muted">{formatDate(task.created_at)}</span>
                {task.due_date && (
                  <span className="text-muted">Срок: {formatDate(task.due_date)}</span>
                )}
              </div>
            </div>
            <button
              className="btn btn-primary"
              style={{ flexShrink: 0 }}
              onClick={e => { e.stopPropagation(); navigate(`/manager/${task.id}`) }}
            >
              Рассмотреть
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
