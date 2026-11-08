import { useCallback, useEffect, useState } from 'react'
import { ArrowRight, ClipboardCopy, KeyRound, LogOut, ShieldCheck, UserPlus, UsersRound } from 'lucide-react'
import { accountRequest } from '../hooks/useAccount'

const ROLES = ['clinician', 'trainee', 'admin', 'auditor']
export default function AdminConsole({ account, onLogout }) {
  const auditOnly = account.role === 'auditor'
  const [tab, setTab] = useState(account.role === 'auditor' ? 'audit' : 'users')
  const [users, setUsers] = useState([])
  const [audit, setAudit] = useState([])
  const [form, setForm] = useState({ username: '', displayName: '', department: '', role: 'clinician' })
  const [issued, setIssued] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = useCallback(async () => {
    try {
      if (auditOnly) {
        const logs = await accountRequest('/audit')
        setAudit(logs); setError('')
      } else {
        const [accounts, logs] = await Promise.all([accountRequest('/users'), accountRequest('/audit')])
        setUsers(accounts); setAudit(logs); setError('')
      }
    } catch (e) { setError(e.message) }
  }, [auditOnly])
  useEffect(() => { load() }, [load])
  async function action(fn) {
    setBusy(true); setError(''); setIssued(null)
    try { await fn(); await load() } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  const invite = event => {
    event.preventDefault()
    action(async () => {
      const response = await accountRequest('/users/invite', { method: 'POST', data: form })
      setIssued({ kind: 'activation', username: form.username, code: response.activationCode, expiry: '24 hours' })
      setForm({ username: '', displayName: '', department: '', role: 'clinician' })
    })
  }
  const changeRole = (user, role) => {
    if (!window.confirm(`Change ${user.username}'s role to ${role}? Current sessions will be revoked.`)) return
    action(() => accountRequest('/users/' + user.id + '/role', { method: 'PUT', data: { role } }))
  }
  const toggle = user => {
    const method = user.state === 'disabled' ? 'enable' : 'disable'
    if (!window.confirm(`${method === 'disable' ? 'Disable' : 'Enable'} account ${user.username}?`)) return
    action(() => accountRequest('/users/' + user.id + '/' + method, { method: 'POST' }))
  }
  const recover = user => {
    if (!window.confirm(`Issue a password recovery code for ${user.username}? First verify their identity outside CLARA.`)) return
    action(async () => {
      const result = await accountRequest('/users/' + user.id + '/recovery', { method: 'POST' })
      setIssued({ kind: 'recovery', username: user.username, code: result.recoveryCode, expiry: '20 minutes' })
    })
  }
  return <main className="clara-admin-page">
    <aside className="clara-admin-sidebar">
      <div className="clara-admin-brand"><strong>CLARA</strong><small>Administration</small></div>
      {!auditOnly && <button className={tab === 'users' ? 'is-active' : ''} onClick={() => setTab('users')}><UsersRound size={18} /> User Management</button>}
      <button className={tab === 'audit' ? 'is-active' : ''} onClick={() => setTab('audit')}><ShieldCheck size={18} /> Security Audit</button>
      <div className="clara-admin-account"><strong>{account.displayName}</strong><small>{account.username} · {account.role === 'admin' ? 'Administrator' : 'Auditor'}</small><button onClick={onLogout}><LogOut size={16} /> Sign out</button></div>
    </aside>
    <section className="clara-admin-content">
      <header><span className="clara-admin-eyebrow">HOSPITAL CONTROL PANEL</span><h1>{tab === 'users' ? 'User Management' : 'Security Audit'}</h1><p>Authorized administration only. Patient information is not shown here.</p></header>
      {error && <p className="clara-auth-error" role="alert">{error}</p>}
      {issued && <div className="clara-admin-secret" role="status">
        <strong>{issued.kind === 'activation' ? 'Staff activation' : 'Password recovery'} code — {issued.username}</strong>
        <p>This code is shown once. Verify the recipient and transfer it securely. Expires in {issued.expiry}.</p>
        <div className="clara-admin-secret-code"><code>{issued.code}</code><button type="button" onClick={() => navigator.clipboard.writeText(issued.code)} aria-label="Copy one-time code"><ClipboardCopy size={17}/></button></div>
        <button type="button" onClick={() => setIssued(null)}>I've delivered the code securely</button>
      </div>}
      {!auditOnly && tab === 'users' ? <>
        <form className="clara-admin-invite" onSubmit={invite}>
          <div className="clara-admin-section-title"><UserPlus size={19} /><h2>Invite a staff member</h2></div>
          <div className="clara-admin-invite-fields">
            <label>Username<input required minLength={3} maxLength={120} autoComplete="off" value={form.username} onChange={e=>setForm(f=>({...f,username:e.target.value}))} placeholder="firstname.lastname" /></label>
            <label>Full name<input required maxLength={200} value={form.displayName} onChange={e=>setForm(f=>({...f,displayName:e.target.value}))} placeholder="Dr. Juan Dela Cruz" /></label>
            <label>Department<input maxLength={120} value={form.department} onChange={e=>setForm(f=>({...f,department:e.target.value}))} placeholder="Cardiology" /></label>
            <label>Role<select value={form.role} onChange={e=>setForm(f=>({...f,role:e.target.value}))}>{ROLES.map(role=><option key={role}>{role}</option>)}</select></label>
          </div>
          <button className="clara-auth-primary" type="submit" disabled={busy}>Generate activation code <ArrowRight size={17}/></button>
        </form>
        <section className="clara-admin-list">
          <div className="clara-admin-section-title"><UsersRound size={19}/><h2>Staff accounts</h2><span>{users.length} total</span></div>
          <div className="clara-admin-users">{users.map(user => <article key={user.id}>
            <div><strong>{user.displayName}</strong><small>{user.username} · {user.department || 'No department'}</small></div>
            <span className="clara-admin-state">{user.state}</span>
            <select aria-label={'Role for ' + user.username} disabled={busy || user.id === account.id} value={user.role} onChange={e => changeRole(user, e.target.value)}>{ROLES.map(role=><option key={role}>{role}</option>)}</select>
            <div className="clara-admin-actions">
              {user.state === 'active' && <button disabled={busy} onClick={()=>recover(user)}><KeyRound size={15}/> Recovery</button>}
              {user.id !== account.id && user.state !== 'pending' && <button disabled={busy} onClick={()=>toggle(user)}>{user.state === 'active' ? 'Disable' : 'Enable'}</button>}
            </div>
          </article>)}</div>
        </section>
      </> : <section className="clara-admin-list">
        <div className="clara-admin-section-title"><ShieldCheck size={19}/><h2>Recent security events</h2></div>
        <div className="clara-admin-audit">{audit.map(e=><div key={e.id}><strong>{e.action.replaceAll('_',' ')}</strong><time dateTime={e.createdAt}>{new Date(e.createdAt).toLocaleString()}</time><small>Account: {e.subjectId || 'System'}</small></div>)}</div>
      </section>}
    </section>
  </main>
}
