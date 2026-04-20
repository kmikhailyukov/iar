import { useState, useRef, useEffect } from 'react'
import { useUser } from '../UserContext'
import { useNavigate } from 'react-router-dom'

const ROLE_LABEL = { ADMIN: 'Администратор', MANAGER: 'Руководитель', EXECUTOR: 'Исполнитель' }
const ROLE_ORDER = { ADMIN: 0, MANAGER: 1, EXECUTOR: 2 }
const ROLE_HOME = { ADMIN: '/admin', MANAGER: '/manager', EXECUTOR: '/executor' }

export default function UserSwitcher() {
  const { currentUser, setCurrentUser, users } = useUser()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (!currentUser) return null

  const grouped = users.reduce((acc, u) => {
    acc[u.role] = acc[u.role] || []
    acc[u.role].push(u)
    return acc
  }, {})

  const handleSelect = (user) => {
    setCurrentUser(user)
    setOpen(false)
    navigate(ROLE_HOME[user.role] || '/')
  }

  return (
    <div ref={ref} style={{ position: 'relative', marginLeft: 'auto' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: 'rgba(255,255,255,0.15)',
          border: '1px solid rgba(255,255,255,0.3)',
          borderRadius: 8,
          padding: '6px 12px',
          cursor: 'pointer',
          color: 'white',
          fontSize: 13,
          maxWidth: 220,
        }}
      >
        <Avatar user={currentUser} size={24} />
        <div style={{ textAlign: 'left', overflow: 'hidden' }}>
          <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {currentUser.name}
          </div>
          <div style={{ fontSize: 11, opacity: 0.8 }}>
            {ROLE_LABEL[currentUser.role]}{currentUser.dept_code ? ` · ${currentUser.dept_code}` : ''}
          </div>
        </div>
        <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 2 }}>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div style={{
          position: 'absolute',
          right: 0,
          top: 'calc(100% + 6px)',
          background: 'white',
          borderRadius: 10,
          boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
          minWidth: 260,
          zIndex: 1000,
          overflow: 'hidden',
        }}>
          {Object.entries(grouped)
            .sort(([a], [b]) => ROLE_ORDER[a] - ROLE_ORDER[b])
            .map(([role, group]) => (
              <div key={role}>
                <div style={{
                  padding: '8px 14px 4px',
                  fontSize: 10,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: '#9ca3af',
                  background: '#f9fafb',
                  borderBottom: '1px solid #f3f4f6',
                }}>
                  {ROLE_LABEL[role]}
                </div>
                {group.map(user => {
                  const active = user.employee_id === currentUser.employee_id
                  return (
                    <button
                      key={user.employee_id}
                      onClick={() => handleSelect(user)}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '9px 14px',
                        background: active ? '#eff6ff' : 'white',
                        border: 'none',
                        borderBottom: '1px solid #f3f4f6',
                        cursor: 'pointer',
                        textAlign: 'left',
                      }}
                    >
                      <Avatar user={user} size={32} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: active ? 700 : 500, color: '#111' }}>
                          {user.name}
                          {active && <span style={{ marginLeft: 6, fontSize: 10, color: '#2563eb' }}>● текущий</span>}
                        </div>
                        <div style={{ fontSize: 11, color: '#6b7280', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {user.position}{user.dept_code ? ` · ${user.dept_code}` : ''}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            ))}
        </div>
      )}
    </div>
  )
}

function Avatar({ user, size }) {
  const initials = user.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
  const colors = {
    ADMIN:    ['#7c3aed', '#ede9fe'],
    MANAGER:  ['#1d4ed8', '#dbeafe'],
    EXECUTOR: ['#065f46', '#d1fae5'],
  }
  const [fg, bg] = colors[user.role] || ['#374151', '#f3f4f6']
  return (
    <div style={{
      width: size, height: size,
      borderRadius: '50%',
      background: bg,
      color: fg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.38,
      fontWeight: 700,
      flexShrink: 0,
    }}>
      {initials}
    </div>
  )
}
