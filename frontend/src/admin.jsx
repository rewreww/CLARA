import React from 'react'
import ReactDOM from 'react-dom/client'
import AdminConsole from './components/AdminConsole.jsx'
import AuthScreen from './components/AuthScreen.jsx'
import { useAccount } from './hooks/useAccount.js'
import './index.css'
import './admin.css'

function AdminApp() {
  const { loading, enabled, user, error, login, logout } = useAccount()
  if (loading) return <main className="admin-gate" role="status">Loading CLARA Administration…</main>
  if (error) return <main className="admin-gate" role="alert">{error}</main>
  if (!enabled) return <main className="admin-gate">Hospital account management is not enabled on this server.</main>
  if (!user) return <AuthScreen onLogin={async (username, password) => {
    const result = await login(username, password)
    if (!['admin', 'auditor'].includes(result.role)) {
      await logout()
      throw new Error('Only hospital administrators can sign in here.')
    }
  }} />
  if (!['admin', 'auditor'].includes(user.role)) return <main className="admin-gate">This account is not authorized for administration. <button onClick={logout}>Sign out</button></main>
  return <AdminConsole account={user} onLogout={logout} />
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode><AdminApp /></React.StrictMode>,
)
