const BASE = import.meta.env.VITE_API_URL || '/api/v1';

export async function getManagerTasks() {
  const r = await fetch(`${BASE}/user-tasks/manager`);
  return r.json();
}

export async function getAssignment(id) {
  const r = await fetch(`${BASE}/assignments/${id}`);
  return r.json();
}

export async function confirmAssignment(id, payload) {
  const r = await fetch(`${BASE}/assignments/${id}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return r.json();
}

export async function getExecutorTasks(executorId) {
  const r = await fetch(`${BASE}/user-tasks/executor/${executorId}`);
  return r.json();
}

export async function acceptAssignment(id) {
  const r = await fetch(`${BASE}/assignments/${id}/accept`, { method: 'POST' });
  return r.json();
}

export async function rejectAssignment(id, reason = '') {
  const r = await fetch(
    `${BASE}/assignments/${id}/reject?reason=${encodeURIComponent(reason)}`,
    { method: 'POST' }
  );
  return r.json();
}

export async function disputeAssignment(id, disputedDept, comment = '') {
  const r = await fetch(`${BASE}/assignments/${id}/dispute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ disputed_dept: disputedDept, comment: comment || null }),
  });
  return r.json();
}

export async function getUsers() {
  const r = await fetch(`${BASE}/users`);
  return r.json();
}

export async function getDashboard() {
  const r = await fetch(`${BASE}/dashboard/metrics`);
  return r.json();
}
