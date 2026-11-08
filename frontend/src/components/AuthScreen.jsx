import { useState } from 'react'
import { ArrowLeft, ArrowRight, LockKeyhole, ShieldCheck } from 'lucide-react'
import { accountRequest } from '../hooks/useAccount'

export default function AuthScreen({ onLogin }) {
  const [view, setView] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const submit = async event => {
    event.preventDefault()
    setError(''); setNotice(''); setBusy(true)
    try {
      if (view === 'login') await onLogin(username, password)
      else {
        await accountRequest(view === 'activate' ? '/activate' : '/reset-password', {
          method: 'POST', data: { token, newPassword },
        })
        setView('login')
        setToken(''); setNewPassword(''); setPassword('')
        setNotice('Password set successfully. Sign in with your assigned username.')
      }
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  const changeView = next => { setView(next); setError(''); setNotice(''); setToken(''); setNewPassword('') }
  return <main className="clara-auth-page">
    <div className="clara-auth-card">
      <div className="clara-auth-brand">
        <img src="/clara-mark.svg" alt="" width="62" height="52" />
        <strong>CLARA</strong><span>Clinical AI Assistant</span>
      </div>
      <div className="clara-auth-heading">
        {view !== 'login' && <button className="clara-auth-back" type="button" onClick={() => changeView('login')}><ArrowLeft size={16} /> Back to login</button>}
        <h1>{view === 'login' ? 'Sign in to CLARA' : view === 'activate' ? 'Activate your account' : 'Set a new password'}</h1>
        <p>{view === 'login' ? 'For authorized hospital personnel only.' : 'Use the one-time code issued by your hospital IT administrator.'}</p>
      </div>
      <form className="clara-auth-form" onSubmit={submit}>
        {view === 'login' ? <>
          <label>Username<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required maxLength={120} /></label>
          <label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
        </> : <>
          <label>One-time {view === 'activate' ? 'activation' : 'recovery'} code<input autoComplete="off" value={token} onChange={e => setToken(e.target.value.trim())} required /></label>
          <label>New password<input type="password" autoComplete="new-password" value={newPassword} onChange={e => setNewPassword(e.target.value)} minLength={12} required /></label>
          <p className="clara-auth-hint">At least 12 characters. Do not reuse your hospital password.</p>
        </>}
        {error && <p className="clara-auth-error" role="alert">{error}</p>}
        {notice && <p className="clara-auth-success" role="status">{notice}</p>}
        <button className="clara-auth-primary" type="submit" disabled={busy}>{busy ? 'Please wait...' : view === 'login' ? 'Sign in' : 'Confirm password'} <ArrowRight size={17} /></button>
      </form>
      <div className="clara-auth-options">
        {view === 'login' && <>
          <button type="button" onClick={() => changeView('activate')}>Activate a staff account</button>
          <button type="button" onClick={() => changeView('recovery')}>Forgot password?</button>
        </>}
        {view === 'recovery' && <p>Contact hospital IT to verify your identity and request a 20-minute recovery code. Reset codes are never sent automatically to an unverified address.</p>}
      </div>
      <div className="clara-auth-foot"><ShieldCheck size={15} /><span>Protected hospital access. Activity is audited.</span></div>
    </div>
  </main>
}
