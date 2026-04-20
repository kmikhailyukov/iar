import { createContext, useContext, useState, useEffect } from 'react'
import { getUsers } from './api'

const UserContext = createContext(null)

export function UserProvider({ children }) {
  const [users, setUsers] = useState([])
  const [currentUser, setCurrentUser] = useState(null)

  useEffect(() => {
    getUsers()
      .then(data => {
        setUsers(data)
        // Default: первый MANAGER (генеральный директор)
        const defaultUser = data.find(u => u.employee_id === 'MGR_GD') || data[0] || null
        setCurrentUser(defaultUser)
      })
      .catch(() => {})
  }, [])

  return (
    <UserContext.Provider value={{ currentUser, setCurrentUser, users }}>
      {children}
    </UserContext.Provider>
  )
}

export function useUser() {
  return useContext(UserContext)
}
