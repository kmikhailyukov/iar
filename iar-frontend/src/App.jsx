import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom'
import { UserProvider, useUser } from './UserContext'
import UserSwitcher from './components/UserSwitcher'
import ManagerInbox from './pages/ManagerInbox'
import AssignmentCard from './pages/AssignmentCard'
import ExecutorInbox from './pages/ExecutorInbox'
import AdminPage from './pages/AdminPage'

function NavLinks() {
  const { currentUser } = useUser()
  const role = currentUser?.role
  return (
    <>
      {(role === 'MANAGER' || role === 'ADMIN') && <Link to="/manager">Руководитель</Link>}
      {(role === 'EXECUTOR' || role === 'ADMIN') && <Link to="/executor">Исполнитель</Link>}
      {role === 'ADMIN' && <Link to="/admin">Администратор</Link>}
      <a href="https://lotus-mock.zorro.kt" target="_blank" rel="noreferrer">Lotus Mock</a>
    </>
  )
}

function AppContent() {
  const { currentUser } = useUser()
  const defaultPath = currentUser?.role === 'EXECUTOR' ? '/executor'
    : currentUser?.role === 'ADMIN' ? '/admin'
    : '/manager'

  return (
    <>
      <nav>
        <span className="title">IAR · Распределение поручений</span>
        <NavLinks />
        <UserSwitcher />
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to={defaultPath} />} />
        <Route path="/manager" element={<ManagerInbox />} />
        <Route path="/manager/:id" element={<AssignmentCard />} />
        <Route path="/executor" element={<ExecutorInbox />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <UserProvider>
        <AppContent />
      </UserProvider>
    </BrowserRouter>
  )
}
