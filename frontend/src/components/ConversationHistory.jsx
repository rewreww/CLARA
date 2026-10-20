import { useState } from 'react'
import { Check, MessageSquare, Pencil, Search, SquarePen, Trash2, X } from 'lucide-react'

export default function ConversationHistory({ conversations, activeId, onOpen, onNew, onRename, onDelete, error }) {
  const [query, setQuery] = useState('')
  const [editing, setEditing] = useState(null)
  const [title, setTitle] = useState('')
  const [deleting, setDeleting] = useState(null)
  const filtered = conversations.filter(item => `${item.title} ${item.patientId} ${item.messages.map(message => message.text).join(' ')}`.toLowerCase().includes(query.toLowerCase()))
  return <div className="history-section">
    <div className="history-heading"><span>Recent</span><button className="icon-button" title="New conversation" aria-label="New conversation" onClick={onNew}><SquarePen size={16} /></button></div>
    <div className="patient-search"><Search size={15} /><input aria-label="Search conversations" placeholder="Search conversations" value={query} onChange={event => setQuery(event.target.value)} />
      {query && <button className="icon-button" aria-label="Clear conversation search" onClick={() => setQuery('')}><X size={13} /></button>}</div>
    <span className="history-storage">Saved in this browser</span>
    {error && <p className="sidebar-notice error-text" role="alert">{error}</p>}
    <div className="history-list">
      {!filtered.length && <p className="sidebar-notice">{query ? 'No matching conversations' : 'No conversations yet'}</p>}
      {filtered.map(item => <div className={`history-item ${item.id === activeId ? 'is-active' : ''}`} key={item.id}>
        {editing === item.id ? <form className="history-edit" onSubmit={event => { event.preventDefault(); onRename(item.id, title); setEditing(null) }}>
          <input aria-label="Conversation title" value={title} maxLength={100} onChange={event => setTitle(event.target.value)} autoFocus onKeyDown={event => { if (event.key === 'Escape') setEditing(null) }} />
          <button className="icon-button" aria-label="Save title" title="Save title" disabled={!title.trim()}><Check size={14} /></button>
          <button className="icon-button" type="button" aria-label="Cancel rename" onClick={() => setEditing(null)}><X size={14} /></button>
        </form> : <>
          <button className="history-open" onClick={() => onOpen(item)} aria-current={item.id === activeId ? 'page' : undefined} title={item.title}>
            <MessageSquare size={14} /><span><strong>{item.title}</strong><small>Patient {item.patientId} <span>/ {new Date(item.updatedAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span></small></span>
          </button>
          <div className="history-item-actions">
            <button className="icon-button" title="Rename conversation" aria-label={`Rename ${item.title}`} onClick={() => { setEditing(item.id); setTitle(item.title) }}><Pencil size={13} /></button>
            <button className="icon-button" title="Delete conversation" aria-label={`Delete ${item.title}`} onClick={() => setDeleting(item.id)}><Trash2 size={13} /></button>
          </div>
        </>}
        {deleting === item.id && <div className="history-confirm" role="group" aria-label="Confirm deletion"><span>Delete this conversation?</span><button onClick={() => { onDelete(item.id); setDeleting(null) }}>Delete</button><button onClick={() => setDeleting(null)}>Cancel</button></div>}
      </div>)}
    </div>
  </div>
}
