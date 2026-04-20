import { useState, useEffect, useCallback } from 'react'
import { useUser } from '../UserContext'

const BASE = import.meta.env.VITE_API_URL || '/api/v1'

async function apiFetch(path, opts = {}) {
  const r = await fetch(`${BASE}${path}`, opts)
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${r.status}`)
  }
  if (r.status === 204) return null
  return r.json()
}

const EMPTY_DEPT = { code: '', name: '', parent_id: '', functions_text: '' }

export default function AdminPage() {
  const { currentUser } = useUser()
  const [tab, setTab] = useState('depts')

  if (currentUser && currentUser.role !== 'ADMIN') {
    return (
      <div className="container">
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <p style={{ fontSize: 16, color: '#6b7280' }}>Доступ закрыт. Требуется роль Администратор.</p>
        </div>
      </div>
    )
  }
  const [depts, setDepts] = useState([])
  const [rights, setRights] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // dept form state
  const [editingDept, setEditingDept] = useState(null) // null | 'new' | dept object
  const [deptForm, setDeptForm] = useState(EMPTY_DEPT)
  const [deptSaving, setDeptSaving] = useState(false)
  const [deptError, setDeptError] = useState(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [d, r] = await Promise.all([
        apiFetch('/admin/departments'),
        apiFetch('/admin/rights'),
      ])
      setDepts(d)
      setRights(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  // ── Dept form ────────────────────────────────────────────────
  const openNew = () => {
    setEditingDept('new')
    setDeptForm(EMPTY_DEPT)
    setDeptError(null)
  }

  const openEdit = (dept) => {
    setEditingDept(dept)
    setDeptForm({
      code: dept.code,
      name: dept.name,
      parent_id: dept.parent_id || '',
      functions_text: dept.functions_text || '',
    })
    setDeptError(null)
  }

  const saveDept = async () => {
    if (!deptForm.code.trim() || !deptForm.name.trim()) {
      setDeptError('Код и название обязательны')
      return
    }
    setDeptSaving(true)
    setDeptError(null)
    try {
      const payload = {
        code: deptForm.code.trim(),
        name: deptForm.name.trim(),
        parent_id: deptForm.parent_id || null,
        functions_text: deptForm.functions_text || null,
      }
      if (editingDept === 'new') {
        await apiFetch('/admin/departments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
      } else {
        await apiFetch(`/admin/departments/${editingDept.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
      }
      setEditingDept(null)
      await loadAll()
    } catch (e) {
      setDeptError(e.message)
    } finally {
      setDeptSaving(false)
    }
  }

  const archiveDept = async (dept) => {
    if (!confirm(`Архивировать «${dept.name}»? Это скроет подразделение из списков.`)) return
    try {
      await apiFetch(`/admin/departments/${dept.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ archived: true }),
      })
      await loadAll()
    } catch (e) {
      setError(e.message)
    }
  }

  const restoreDept = async (dept) => {
    try {
      await apiFetch(`/admin/departments/${dept.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ archived: false }),
      })
      await loadAll()
    } catch (e) {
      setError(e.message)
    }
  }

  // ── Rights matrix ────────────────────────────────────────────
  const activeDepts = depts.filter(d => !d.archived)

  const hasRight = (fromId, toId) =>
    rights.some(r => r.from_dept_id === fromId && r.to_dept_id === toId)

  const toggleRight = async (fromId, toId, currentlyOn) => {
    try {
      if (currentlyOn) {
        await apiFetch(`/admin/rights?from_dept_id=${fromId}&to_dept_id=${toId}`, { method: 'DELETE' })
      } else {
        await apiFetch(`/admin/rights?from_dept_id=${fromId}&to_dept_id=${toId}`, { method: 'POST' })
      }
      const r = await apiFetch('/admin/rights')
      setRights(r)
    } catch (e) {
      setError(e.message)
    }
  }

  // ── Tree helpers ─────────────────────────────────────────────
  const deptName = (id) => depts.find(d => d.id === id)?.name || '—'

  const buildTree = (items, parentId = null, depth = 0) => {
    return items
      .filter(d => (d.parent_id || null) === parentId)
      .map(d => ({ ...d, depth, children: buildTree(items, d.id, depth + 1) }))
  }

  const flattenTree = (nodes) => nodes.flatMap(n => [n, ...flattenTree(n.children)])
  const treeDepts = flattenTree(buildTree(depts.filter(d => !d.archived)))
  const archivedDepts = depts.filter(d => d.archived)

  return (
    <div className="container">
      <div className="inbox-header">
        <h1>Администрирование</h1>
        <button className="btn btn-secondary" onClick={loadAll} disabled={loading}>
          {loading ? 'Загрузка...' : 'Обновить'}
        </button>
      </div>

      {error && <div className="error-msg">{error}</div>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button
          className={`btn ${tab === 'depts' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setTab('depts')}
        >
          Подразделения
        </button>
        <button
          className={`btn ${tab === 'rights' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setTab('rights')}
        >
          Матрица полномочий
        </button>
      </div>

      {/* ── DEPARTMENTS TAB ── */}
      {tab === 'depts' && (
        <>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            <button className="btn btn-success" onClick={openNew}>
              + Новое подразделение
            </button>
          </div>

          {/* Edit / Create form */}
          {editingDept !== null && (
            <div className="card" style={{ borderLeft: '4px solid #2563eb', marginBottom: 24 }}>
              <h2 style={{ marginBottom: 16 }}>
                {editingDept === 'new' ? 'Новое подразделение' : `Редактирование: ${editingDept.name}`}
              </h2>

              {deptError && <div className="error-msg" style={{ marginBottom: 12 }}>{deptError}</div>}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12, marginBottom: 12 }}>
                <div>
                  <label style={labelStyle}>Код *</label>
                  <input
                    style={inputStyle}
                    value={deptForm.code}
                    disabled={editingDept !== 'new'}
                    onChange={e => setDeptForm(p => ({ ...p, code: e.target.value }))}
                    placeholder="напр. ДОЭ"
                  />
                </div>
                <div>
                  <label style={labelStyle}>Название *</label>
                  <input
                    style={inputStyle}
                    value={deptForm.name}
                    onChange={e => setDeptForm(p => ({ ...p, name: e.target.value }))}
                    placeholder="Полное название подразделения"
                  />
                </div>
              </div>

              <div style={{ marginBottom: 12 }}>
                <label style={labelStyle}>Вышестоящее подразделение (необязательно)</label>
                <select
                  style={inputStyle}
                  value={deptForm.parent_id}
                  onChange={e => setDeptForm(p => ({ ...p, parent_id: e.target.value }))}
                >
                  <option value="">— нет (корневое) —</option>
                  {activeDepts
                    .filter(d => d.id !== (editingDept !== 'new' ? editingDept.id : null))
                    .map(d => (
                      <option key={d.id} value={d.id}>{d.code} — {d.name}</option>
                    ))}
                </select>
              </div>

              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Функции и положение подразделения</label>
                <textarea
                  style={{ ...inputStyle, minHeight: 120, resize: 'vertical' }}
                  value={deptForm.functions_text}
                  onChange={e => setDeptForm(p => ({ ...p, functions_text: e.target.value }))}
                  placeholder="Опишите функции подразделения. Этот текст используется системой для классификации поручений..."
                />
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-success" onClick={saveDept} disabled={deptSaving}>
                  {deptSaving ? 'Сохранение...' : 'Сохранить'}
                </button>
                <button className="btn btn-secondary" onClick={() => setEditingDept(null)} disabled={deptSaving}>
                  Отмена
                </button>
              </div>
            </div>
          )}

          {/* Tree list */}
          <div className="card">
            {treeDepts.length === 0 && !loading && (
              <div className="empty-state">Подразделения не добавлены</div>
            )}
            {treeDepts.map(dept => (
              <div
                key={dept.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  padding: '12px 0',
                  borderBottom: '1px solid #f3f4f6',
                  paddingLeft: dept.depth * 24,
                }}
              >
                {dept.depth > 0 && (
                  <span style={{ color: '#d1d5db', fontSize: 18, marginTop: 2 }}>└</span>
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="badge badge-medium">{dept.code}</span>
                    <strong style={{ fontSize: 14 }}>{dept.name}</strong>
                  </div>
                  {dept.functions_text && (
                    <p style={{ fontSize: 12, color: '#6b7280', marginTop: 4, lineHeight: 1.5 }}>
                      {dept.functions_text.length > 120
                        ? dept.functions_text.slice(0, 120) + '…'
                        : dept.functions_text}
                    </p>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <button className="btn btn-secondary" style={{ padding: '4px 12px', fontSize: 12 }} onClick={() => openEdit(dept)}>
                    Изменить
                  </button>
                  <button className="btn btn-danger" style={{ padding: '4px 12px', fontSize: 12 }} onClick={() => archiveDept(dept)}>
                    Архивировать
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Archived */}
          {archivedDepts.length > 0 && (
            <details style={{ marginTop: 16 }}>
              <summary style={{ cursor: 'pointer', fontSize: 13, color: '#6b7280' }}>
                Архивные подразделения ({archivedDepts.length})
              </summary>
              <div className="card" style={{ marginTop: 8 }}>
                {archivedDepts.map(dept => (
                  <div key={dept.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: '1px solid #f3f4f6', opacity: 0.6 }}>
                    <span className="badge badge-medium">{dept.code}</span>
                    <span style={{ flex: 1, fontSize: 14 }}>{dept.name}</span>
                    <button className="btn btn-secondary" style={{ padding: '4px 12px', fontSize: 12 }} onClick={() => restoreDept(dept)}>
                      Восстановить
                    </button>
                  </div>
                ))}
              </div>
            </details>
          )}
        </>
      )}

      {/* ── RIGHTS MATRIX TAB ── */}
      {tab === 'rights' && (
        <>
          <div className="card" style={{ overflowX: 'auto' }}>
            <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 16 }}>
              Отмеченные ячейки означают, что подразделение <strong>в строке</strong> имеет право давать поручения подразделению <strong>в столбце</strong>.
            </p>

            {activeDepts.length === 0 ? (
              <div className="empty-state">Нет активных подразделений</div>
            ) : (
              <table style={{ borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={thStyle}>Кто даёт \ Кому</th>
                    {activeDepts.map(d => (
                      <th key={d.id} style={{ ...thStyle, textAlign: 'center', minWidth: 80 }}>
                        <span className="badge badge-medium">{d.code}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activeDepts.map(from => (
                    <tr key={from.id}>
                      <td style={{ ...tdStyle, fontWeight: 600, whiteSpace: 'nowrap' }}>
                        <span className="badge badge-medium" style={{ marginRight: 6 }}>{from.code}</span>
                        <span style={{ fontSize: 12, color: '#6b7280' }}>{from.name}</span>
                      </td>
                      {activeDepts.map(to => {
                        if (from.id === to.id) {
                          return (
                            <td key={to.id} style={{ ...tdStyle, textAlign: 'center', background: '#f9fafb', color: '#d1d5db' }}>
                              —
                            </td>
                          )
                        }
                        const on = hasRight(from.id, to.id)
                        return (
                          <td key={to.id} style={{ ...tdStyle, textAlign: 'center' }}>
                            <button
                              onClick={() => toggleRight(from.id, to.id, on)}
                              style={{
                                width: 28,
                                height: 28,
                                borderRadius: 6,
                                border: on ? '2px solid #16a34a' : '2px solid #d1d5db',
                                background: on ? '#dcfce7' : '#fff',
                                cursor: 'pointer',
                                fontSize: 16,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                margin: '0 auto',
                              }}
                              title={on ? `Убрать право: ${from.code} → ${to.code}` : `Добавить право: ${from.code} → ${to.code}`}
                            >
                              {on ? '✓' : ''}
                            </button>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  )
}

const labelStyle = { display: 'block', fontSize: 12, fontWeight: 600, color: '#555', marginBottom: 4 }
const inputStyle = {
  width: '100%',
  padding: '8px 12px',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  fontSize: 14,
  fontFamily: 'inherit',
  background: '#fafafa',
  boxSizing: 'border-box',
}
const thStyle = { padding: '8px 12px', background: '#f8f9fa', borderBottom: '2px solid #e5e7eb', textAlign: 'left', fontWeight: 600, fontSize: 12, color: '#6b7280' }
const tdStyle = { padding: '8px 12px', borderBottom: '1px solid #f3f4f6' }
