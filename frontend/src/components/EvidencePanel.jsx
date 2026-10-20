import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { ArrowLeft, FileText, LoaderCircle, X } from 'lucide-react'
import ActivityTimeline from './ActivityTimeline'
import { sourceKey } from '../lib/conversations'
import { citationPage } from '../lib/sources'

const PdfPreview = lazy(() => import('./PdfPreview'))

export default function EvidencePanel({ mobileOpen, sources, selectedSource, onSelectSource, onClose, patientId, message, tab, onTab }) {
  const panelRef = useRef(null)
  const closeRef = useRef(null)
  const [modal, setModal] = useState(() => matchMedia('(max-width: 1100px)').matches)
  useEffect(() => {
    const media = matchMedia('(max-width: 1100px)')
    const resize = () => setModal(media.matches)
    resize()
    media.addEventListener('change', resize)
    return () => media.removeEventListener('change', resize)
  }, [])
  useEffect(() => {
    if (!modal || !mobileOpen) return
    const previousFocus = window.document.activeElement
    closeRef.current?.focus()
    const handleKey = event => {
      if (event.key === 'Escape') { event.stopPropagation(); onClose() }
      if (event.key !== 'Tab' || !matchMedia('(max-width: 1100px)').matches) return
      const focusable = [...panelRef.current.querySelectorAll('button, a, select, input')].filter(el => !el.disabled && el.getClientRects().length)
      const first = focusable[0], last = focusable.at(-1)
      if (!panelRef.current.contains(window.document.activeElement)) { event.preventDefault(); (event.shiftKey ? last : first)?.focus(); return }
      if (event.shiftKey && window.document.activeElement === first) { event.preventDefault(); last?.focus() }
      if (!event.shiftKey && window.document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    window.document.addEventListener('keydown', handleKey)
    return () => { window.document.removeEventListener('keydown', handleKey); if (previousFocus?.isConnected) previousFocus.focus() }
  }, [onClose, modal, mobileOpen])
  useEffect(() => {
    if (modal && mobileOpen && window.document.activeElement === window.document.body) {
      const target = panelRef.current?.querySelector(selectedSource ? '.source-back' : '.source-item')
      ;(target || closeRef.current)?.focus()
    }
  }, [selectedSource, modal, mobileOpen])
  return <>
    {mobileOpen && <button className="evidence-backdrop" aria-label="Close document panel" tabIndex={-1} onClick={onClose} />}
    <aside className={`evidence-panel ${mobileOpen ? 'mobile-open' : ''}`} role={modal ? 'dialog' : undefined} aria-modal={modal || undefined} aria-label="Sources and activity" ref={panelRef}>
      <header><strong>Source preview</strong><button ref={closeRef} className="icon-button evidence-close" onClick={onClose} aria-label="Close source preview" title="Close panel"><X size={18} /></button></header>
      <div className="evidence-tabs" role="tablist" aria-label="Evidence views">
        {['sources', 'activity'].map(value => <button key={value} role="tab" aria-selected={tab === value} tabIndex={tab === value ? 0 : -1}
          onKeyDown={event => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
            event.preventDefault()
            const next = event.key === 'Home' ? 'sources' : event.key === 'End' ? 'activity' : value === 'sources' ? 'activity' : 'sources'
            onTab(next)
            event.currentTarget.parentElement.children[next === 'sources' ? 0 : 1].focus()
          } }}
          className={tab === value ? 'is-active' : ''} onClick={() => onTab(value)}>{value === 'sources' ? `Sources (${sources.length})` : 'Activity'}</button>)}
      </div>
      {tab === 'activity' ? <div className="evidence-activity" role="tabpanel"><ActivityTimeline key={message?.startedAt || 'empty'} message={message} expanded /></div>
        : <div className="evidence-sources" role="tabpanel">
          {selectedSource ? <><button className="source-back" onClick={() => onSelectSource(null)}><ArrowLeft size={14} />All sources</button>
            <Suspense fallback={<div className="pdf-state"><LoaderCircle className="spin-icon" />Loading viewer...</div>}><PdfPreview key={sourceKey(selectedSource)} source={selectedSource} patientId={patientId} /></Suspense></>
            : sources.length ? <div className="source-list">{sources.map((source, index) => <button className="source-item" key={sourceKey(source)} onClick={() => onSelectSource(source)}>
              <span className="source-number">{index + 1}</span><span><small>{source.type === 'patient_pdf' ? 'Patient record' : 'Clinical guideline'}{citationPage(source) ? ` / Page ${citationPage(source)}` : ''}</small><strong>{source.title || source.source}</strong>{source.section && <span>{source.section}</span>}</span><FileText size={17} />
            </button>)}</div> : <div className="evidence-empty"><FileText size={26} /><p>No PDF sources for this response</p></div>}
        </div>}
    </aside>
  </>
}
