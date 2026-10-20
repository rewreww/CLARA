import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, Search, X } from 'lucide-react'
import { STATUS_COLOR } from '../constants'
import ConversationHistory from './ConversationHistory'

export default function WorkspaceSidebar({ activeApp, onChangeApp, selectedPatient, onSelectPatient,
  patients, loading, error, open, onClose,
  conversations, activeConversationId, onOpenConversation, onNewConversation, onRenameConversation, onDeleteConversation, historyError }) {
  const [search, setSearch] = useState('')
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

  return (
    <>
      {open && <button className="workspace-backdrop" onClick={onClose} aria-label="Close sidebar" tabIndex={-1} />}
      <aside ref={sidebarRef} className={`workspace-sidebar ${open ? 'is-open' : ''}`} aria-label={activeApp === 'home' ? 'Conversation history' : 'Patient directory'}>
        <header className="workspace-sidebar-heading"><strong>{activeApp === 'home' ? 'Conversations' : 'Patients'}</strong>
          <button ref={closeRef} className="icon-button workspace-sidebar-close" onClick={onClose} aria-label="Close sidebar"><X size={20} /></button>
        </header>
        <div className="sidebar-content">
          {activeApp === 'patients' ? (
            <>
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
                    <span className="patient-item-text"><strong>{patient.name}</strong><span>{patient.id}{patient.age ? ` / ${patient.age}` : ''}{patient.sex ? ` / ${patient.sex}` : ''}</span></span>
                    {patient.status && <span className="patient-status-dot" style={{ background: STATUS_COLOR[patient.status] || '#92999f' }} title={patient.status} aria-label={patient.status} />}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <><ConversationHistory conversations={conversations} activeId={activeConversationId}
              onOpen={onOpenConversation} onNew={onNewConversation} onRename={onRenameConversation} onDelete={onDeleteConversation} error={historyError} />
            <div className="home-sidebar-context">
              <div className="sidebar-section-label">Current patient</div>
              {selectedPatient ? <button className="context-record-link" onClick={() => onChangeApp('patients')}>
                <span><strong>{selectedPatient.name}</strong><small>Record {selectedPatient.id}</small></span><ArrowUpRight size={17} />
              </button> : <span className="sidebar-notice">No patient selected</span>}
            </div></>
          )}
        </div>
      </aside>
    </>
  )
}
