import { useState } from 'react'
import { Check, LockKeyhole, Monitor, ShieldCheck, UserRound, Sun, Moon } from 'lucide-react'
import { accountRequest } from '../hooks/useAccount'

export default function AccountSettings({ account, section = 'appearance', appearance = 'comfortable', onAppearance, theme = 'dark', onTheme, onLogout, onBeforePasswordChange }) {
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const change = async event => {
    event.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('New passwords do not match.')
      return
    }
    setBusy(true)
    try {
      if (onBeforePasswordChange && !(await onBeforePasswordChange())) {
        setError('Your conversation history is still saving. Please try again.')
        return
      }
      await accountRequest('/change-password', { method: 'POST', data: { oldPassword: current, newPassword: password } })
      setCurrent('')
      setPassword('')
      setConfirm('')
      await onLogout?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return <section className="clara-settings-page" aria-label="Account settings">
    {section === 'appearance' ? <>
      <header className="clara-settings-header">
        <span className="clara-settings-eyebrow">PREFERENCES</span>
        <h1>Appearance</h1>
        <p>Personalize how CLARA looks on this device.</p>
      </header>
      <div className="clara-settings-card">
        <div className="clara-settings-card-heading"><Sun size={19} aria-hidden="true" /><h2>Color theme</h2></div>
        <p>Choose a comfortable reading environment. The change applies immediately across your clinical workspace.</p>
        <div className="clara-theme-options" role="group" aria-label="Color theme">
          <button type="button" className={theme === 'light' ? 'is-selected' : ''} aria-pressed={theme === 'light'} onClick={() => onTheme?.('light')}>
            <span className="clara-theme-preview clara-theme-preview-light" aria-hidden="true">
              <span className="clara-theme-preview-sidebar"><i/><i/><i/></span>
              <span className="clara-theme-preview-main"><i/><i/><i/><b/></span>
            </span>
            <span className="clara-theme-choice"><Sun size={16} aria-hidden="true" /><strong>Light</strong>{theme === 'light' && <Check size={16} aria-label="Selected" />}</span>
            <small>Bright and clear for daytime work</small>
          </button>
          <button type="button" className={theme === 'dark' ? 'is-selected' : ''} aria-pressed={theme === 'dark'} onClick={() => onTheme?.('dark')}>
            <span className="clara-theme-preview clara-theme-preview-dark" aria-hidden="true">
              <span className="clara-theme-preview-sidebar"><i/><i/><i/></span>
              <span className="clara-theme-preview-main"><i/><i/><i/><b/></span>
            </span>
            <span className="clara-theme-choice"><Moon size={16} aria-hidden="true" /><strong>Dark</strong>{theme === 'dark' && <Check size={16} aria-label="Selected" />}</span>
            <small>CLARA's original dark design</small>
          </button>
        </div>
        <p className="clara-theme-help">Your color theme and display density are saved on this browser only.</p>
      </div>
      <div className="clara-settings-card">
        <div className="clara-settings-card-heading"><Monitor size={19} aria-hidden="true" /><h2>Display density</h2></div>
        <p>Choose the spacing that is most comfortable for you. Your preference is stored only in this browser.</p>
        <div className="clara-appearance-options" role="group" aria-label="Display density">
          <button className={appearance === 'comfortable' ? 'is-selected' : ''} type="button"
            onClick={() => onAppearance?.('comfortable')} aria-pressed={appearance === 'comfortable'}>
            <span><strong>Comfortable</strong><small>Standard text and spacing</small></span>
            {appearance === 'comfortable' && <Check size={18} aria-hidden="true" />}
          </button>
          <button className={appearance === 'compact' ? 'is-selected' : ''} type="button"
            onClick={() => onAppearance?.('compact')} aria-pressed={appearance === 'compact'}>
            <span><strong>Compact</strong><small>Fits more navigation and history items on screen</small></span>
            {appearance === 'compact' && <Check size={18} aria-hidden="true" />}
          </button>
        </div>
      </div>
      <div className="clara-settings-card">
        <div className="clara-settings-card-heading"><UserRound size={19} aria-hidden="true" /><h2>Account</h2></div>
        <dl className="clara-settings-details">
          <div><dt>Name</dt><dd>{account.displayName || account.username}</dd></div>
          <div><dt>Username</dt><dd>{account.username}</dd></div>
          <div><dt>Position</dt><dd>{account.role}</dd></div>
          {account.department && <div><dt>Department</dt><dd>{account.department}</dd></div>}
        </dl>
        <p>Contact your administrator to change your assigned role or profile details.</p>
      </div>
    </> : <>
      <header className="clara-settings-header">
        <span className="clara-settings-eyebrow">ACCOUNT PROTECTION</span>
        <h1>Security &amp; Login</h1>
        <p>Manage your password and account access.</p>
      </header>
      <div className="clara-settings-card">
        <div className="clara-settings-card-heading"><LockKeyhole size={19} aria-hidden="true" /><h2>Change password</h2></div>
        <p>Changing your password signs you out. Sign in again with the new password.</p>
        <form className="clara-settings-password-form" onSubmit={change}>
          <label>Current password<input type="password" autoComplete="current-password" required value={current}
            onChange={event => setCurrent(event.target.value)} /></label>
          <label>New password<input type="password" autoComplete="new-password" minLength={12} required value={password}
            onChange={event => setPassword(event.target.value)} /></label>
          <label>Confirm new password<input type="password" autoComplete="new-password" minLength={12} required value={confirm}
            onChange={event => setConfirm(event.target.value)} /></label>
          {error && <p className="clara-auth-error" role="alert">{error}</p>}
          <button className="clara-auth-primary" disabled={busy} type="submit">{busy ? 'Updating…' : 'Update password'}</button>
        </form>
      </div>
      <div className="clara-settings-card">
        <div className="clara-settings-card-heading"><ShieldCheck size={19} aria-hidden="true" /><h2>Account recovery</h2></div>
        <p>For a forgotten password, contact your hospital IT administrator. After identity verification, IT can issue a one-time recovery code for the CLARA sign-in page. No email or external account service is required.</p>
      </div>
    </>}
  </section>
}
