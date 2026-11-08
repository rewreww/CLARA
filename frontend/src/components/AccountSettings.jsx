import { useState } from 'react'
import { LockKeyhole, LogOut, X } from 'lucide-react'
import { accountRequest } from '../hooks/useAccount'

export default function AccountSettings({ account, onClose, onLogout }) {
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const change = async event => {
    event.preventDefault(); setBusy(true); setError('')
    try {
      await accountRequest('/change-password', { method: 'POST', data: { oldPassword: current, newPassword: password } })
      await onLogout()
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  return <div className="clara-account-overlay" role="presentation" onMouseDown={event=>{ if(event.target === event.currentTarget)onClose() }}>
    <section className="clara-account-modal" role="dialog" aria-modal="true" aria-label="Account settings">
      <header><div><h2>Account settings</h2><p>{account.displayName} · {account.role}</p></div><button type="button" onClick={onClose} aria-label="Close settings"><X size={19}/></button></header>
      <form onSubmit={change}>
        <div className="clara-admin-section-title"><LockKeyhole size={18}/><h3>Change password</h3></div>
        <label>Current password<input type="password" autoComplete="current-password" required value={current} onChange={e=>setCurrent(e.target.value)} /></label>
        <label>New password<input type="password" autoComplete="new-password" minLength={12} required value={password} onChange={e=>setPassword(e.target.value)} /></label>
        {error && <p className="clara-auth-error" role="alert">{error}</p>}
        <button className="clara-auth-primary" disabled={busy} type="submit">Change password & sign out</button>
      </form>
      <button className="clara-account-signout" onClick={onLogout}><LogOut size={17}/> Sign out</button>
    </section>
  </div>
}
