import { useEffect, useRef, useState } from 'react'
import { MessageSquarePlus, UsersRound, Search, X, UserRound, Settings, LogOut, ChevronUp, ArrowLeft, Palette, LockKeyhole } from 'lucide-react'
import { STATUS_COLOR } from '../constants'
import ConversationHistory from './ConversationHistory'

export default function WorkspaceSidebar({ activeApp, onChangeApp, selectedPatient, onSelectPatient,
  patients, loading, error, open, onClose,
  conversations, activeConversationId, onOpenConversation, onNewConversation, onRenameConversation, onDeleteConversation, historyError,
  account, onAccountSettings, onLogout, settingsMode = false, settingsSection = 'appearance', onSettingsSection, onSettingsBack }) {
  const [search, setSearch] = useState('')
  const [profileOpen, setProfileOpen] = useState(false)
  const profileRef = useRef(null)
  const profileButtonRef = useRef(null)
  const sidebarRef = useRef(null)
  const closeRef = useRef(null)
  const filtered = patients.filter(patient =>
    `${patient.name} ${patient.id}`.toLowerCase().includes(search.toLowerCase()))

  useEffect(() => {
    if (!open) return
    const previousFocus = document.activeElement
    closeRef.current?.focus()
    const onKeyDown = event => {
      if (event.key === 'Escape') onClose()
      if (event.key !== 'Tab' || !window.matchMedia('(max-width: 1100px)').matches) return
      const controls = [...sidebarRef.current.querySelectorAll('button, input, a')]
        .filter(element => !element.disabled && element.getClientRects().length)
      const first = controls[0], last = controls[controls.length - 1]
      if (!sidebarRef.current.contains(document.activeElement)) { event.preventDefault(); (event.shiftKey ? last : first)?.focus(); return }
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      previousFocus?.focus()
    }
  }, [open, onClose])

  useEffect(() => {
    if (!profileOpen) return
    const onPointerDown = event => {
      if (!profileRef.current?.contains(event.target)) setProfileOpen(false)
    }
    const onKeyDown = event => {
      if (event.key === 'Escape') {
        setProfileOpen(false)
        profileButtonRef.current?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [profileOpen])

  useEffect(() => {
    if (!open) setProfileOpen(false)
  }, [open])

  return (
    <>
      {open && <button className="workspace-backdrop" onClick={onClose} aria-label="Close sidebar" tabIndex={-1} />}
      <aside ref={sidebarRef} className={`workspace-sidebar ${open ? 'is-open' : ''}`} aria-label="CLARA navigation">
        <header className="workspace-sidebar-heading sidebar-clara-brand">
          {settingsMode
            ? <button type="button" className="clara-settings-back" onClick={onSettingsBack}>
                <ArrowLeft size={18} aria-hidden="true" /> <span>Back to the app</span>
              </button>
            : <div className="sidebar-brand-identity"><strong>CLARA</strong></div>}
          <button ref={closeRef} className="icon-button workspace-sidebar-close" onClick={onClose}
            aria-label="Close navigation"><X size={20} /></button>
        </header>
        {settingsMode ? <nav className="clara-main-navigation clara-settings-navigation" aria-label="Settings navigation">
          <div className="clara-settings-nav-title">Settings</div>
          <button type="button" className={`clara-nav-button ${settingsSection === 'appearance' ? 'is-active' : ''}`}
            aria-current={settingsSection === 'appearance' ? 'page' : undefined}
            onClick={() => onSettingsSection?.('appearance')}>
            <Palette size={19} aria-hidden="true" /><span>Appearance</span>
          </button>
          <button type="button" className={`clara-nav-button ${settingsSection === 'security' ? 'is-active' : ''}`}
            aria-current={settingsSection === 'security' ? 'page' : undefined}
            onClick={() => onSettingsSection?.('security')}>
            <LockKeyhole size={19} aria-hidden="true" /><span>Security &amp; Login</span>
          </button>
        </nav> : <>
        <nav className="clara-main-navigation" aria-label="Main navigation">
          <button className="clara-nav-button" onClick={onNewConversation}>
            <MessageSquarePlus size={19} aria-hidden="true" /><span>New Chat</span>
          </button>
          <button className={`clara-nav-button ${activeApp === 'patients' ? 'is-active' : ''}`}
            onClick={() => onChangeApp('patients')} aria-current={activeApp === 'patients' ? 'page' : undefined}>
            <UsersRound size={19} aria-hidden="true" /><span>Patients</span>
          </button>
        </nav>
        <div className="sidebar-content clara-sidebar-content">
          <ConversationHistory conversations={conversations} activeId={activeConversationId}
            onOpen={onOpenConversation} onNew={onNewConversation} onRename={onRenameConversation}
            onDelete={onDeleteConversation} error={historyError} />
          {activeApp === 'patients' && <section className="clara-patient-directory-section" aria-label="Patient directory">
            <div className="sidebar-section-label">Patient directory</div>
            <div className="patient-search"><Search size={16} />
              <input value={search} onChange={event => setSearch(event.target.value)} aria-label="Search patients" placeholder="Search name or ID" />
              {search && <button className="icon-button" onClick={() => setSearch('')} aria-label="Clear search"><X size={14} /></button>}
            </div>
            <div className="patient-directory">
              {loading && <p className="sidebar-notice" role="status">Loading patients...</p>}
              {error && <p className="sidebar-notice error-text" role="alert">Patient directory unavailable.</p>}
              {!loading && !error && !filtered.length && <p className="sidebar-notice">{search ? 'No matching patients' : 'No patient records'}</p>}
              {filtered.map(patient => (
                <button key={patient.id} className={`patient-item ${selectedPatient?.id === patient.id ? 'is-selected' : ''}`}
                  onClick={() => onSelectPatient(patient)} aria-pressed={selectedPatient?.id === patient.id} title={patient.name}>
                  <span className="patient-avatar">{patient.name?.charAt(0).toUpperCase() || 'P'}</span>
                  <span className="patient-item-text"><strong>{patient.name}</strong>
                    <span>{patient.id}{patient.age ? ` / ${patient.age}` : ''}{patient.sex ? ` / ${patient.sex}` : ''}</span></span>
                  {patient.status && <span className="patient-status-dot" style={{ background: STATUS_COLOR[patient.status] || '#92999f' }} title={patient.status} aria-label={patient.status} />}
                </button>
              ))}
            </div>
          </section>}
        </div>
        </>}
        <div className="clara-profile-area" ref={profileRef}>
          {account && profileOpen && <div className="clara-profile-menu" id="clara-profile-menu" role="group" aria-label="Profile options">
            <div className="clara-profile-menu-identity">
              <strong>{account.displayName || account.username}</strong>
              <small>{account.department ? `${account.role} · ${account.department}` : account.role}</small>
            </div>
            <div className="clara-profile-menu-divider" />
            <button type="button" className="clara-profile-menu-action" onClick={() => {
              setProfileOpen(false)
              onAccountSettings?.()
            }}><Settings size={17} aria-hidden="true" /> Settings</button>
            <div className="clara-profile-menu-divider" />
            <button type="button" className="clara-profile-menu-action" onClick={() => {
              setProfileOpen(false)
              onLogout?.()
            }}><LogOut size={17} aria-hidden="true" /> Logout</button>
          </div>}
          <footer className="clara-account-footer" aria-label="Account">
            {account ? <button ref={profileButtonRef} className="clara-account-profile-trigger" type="button"
              onClick={() => setProfileOpen(value => !value)} aria-expanded={profileOpen}
              aria-controls="clara-profile-menu" aria-label="Open account menu">
              <span className="clara-account-avatar" aria-hidden="true"><UserRound size={20} /></span>
              <span className="clara-account-label"><strong>{account.displayName || account.username}</strong><small>{account.role}</small></span>
              <ChevronUp className={profileOpen ? 'is-open' : ''} size={16} aria-hidden="true" />
            </button> : <>
              <span className="clara-account-avatar" aria-hidden="true"><UserRound size={20} /></span>
              <span className="clara-account-label"><strong>CLARA demo</strong><small>Local demonstration</small></span>
            </>}
          </footer>
        </div>
      </aside>
    </>
  )
}
