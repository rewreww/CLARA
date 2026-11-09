import { useState } from 'react'
import { Check, ChevronDown, Pencil, Trash2, X } from 'lucide-react'

export default function ConversationHistory({ conversations, activeId, onOpen, onRename, onDelete, error }) {
  const [expanded, setExpanded] = useState(true)
  const [editing, setEditing] = useState(null)
  const [title, setTitle] = useState('')
  const [deleting, setDeleting] = useState(null)
  return <div className={`history-section ${expanded ? "is-expanded" : "is-collapsed"}`}>
    <button type="button" className="history-heading" onClick={() => setExpanded(open => !open)}
      aria-expanded={expanded} aria-controls="clara-recent-conversations">
      <span>Recents</span>
      <ChevronDown className={`recent-chevron ${expanded ? 'is-open' : ''}`} size={16} aria-hidden="true" />
    </button>
    {error && <p className="sidebar-notice error-text" role="alert">{error}</p>}
    {expanded && <div className="history-list" id="clara-recent-conversations">
      {!conversations.length && <p className="sidebar-notice">No conversations yet</p>}
      {conversations.map(item => <div className={`history-item ${item.id === activeId ? 'is-active' : ''}`} key={item.id}>
        {editing === item.id ? <form className="history-edit" onSubmit={event => { event.preventDefault(); onRename(item.id, title); setEditing(null) }}>
          <input aria-label="Conversation title" value={title} maxLength={100} onChange={event => setTitle(event.target.value)} autoFocus onKeyDown={event => { if (event.key === 'Escape') setEditing(null) }} />
          <button className="icon-button" aria-label="Save title" title="Save title" disabled={!title.trim()}><Check size={14} /></button>
          <button className="icon-button" type="button" aria-label="Cancel rename" onClick={() => setEditing(null)}><X size={14} /></button>
        </form> : <>
          <button className="history-open" onClick={() => onOpen(item)} aria-current={item.id === activeId ? 'page' : undefined} title={item.title}>
            <span><strong>{item.title}</strong></span>
          </button>
          <div className="history-item-actions">
            <button className="icon-button" title="Rename conversation" aria-label={`Rename ${item.title}`} onClick={() => { setEditing(item.id); setTitle(item.title) }}><Pencil size={13} /></button>
            <button className="icon-button" title="Delete conversation" aria-label={`Delete ${item.title}`} onClick={() => setDeleting(item.id)}><Trash2 size={13} /></button>
          </div>
        </>}
        {deleting === item.id && <div className="history-confirm" role="group" aria-label="Confirm deletion"><span>Delete this conversation?</span><button onClick={() => { onDelete(item.id); setDeleting(null) }}>Delete</button><button onClick={() => setDeleting(null)}>Cancel</button></div>}
      </div>)}
    </div>}
  </div>
}
