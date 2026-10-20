import { useRef, useEffect, useState, useCallback } from 'react'
import { Activity, ArrowUp, ArrowUpRight, BookOpen, Check, ChevronDown, Copy, FileText, FlaskConical, HeartPulse, ShieldCheck, Square, SquarePen, UserRound } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import ActivityTimeline from './ActivityTimeline'
import EvidencePanel from './EvidencePanel'

const PROMPTS = [
  { icon: FlaskConical, label: 'Review lab results', message: 'Summarize this patient\'s abnormal laboratory results.' },
  { icon: HeartPulse, label: 'Review patient history', message: 'Summarize this patient\'s clinical history.' },
  { icon: BookOpen, label: 'Explore guidelines', message: 'What cardiovascular guidelines apply to this patient?' },
]

function Message({ msg, onSource, onActivity }) {
  const [copied, setCopied] = useState(false)
  const [copyFailed, setCopyFailed] = useState(false)
  const copyTimer = useRef(null)
  useEffect(() => () => clearTimeout(copyTimer.current), [])
  const isDoctor = msg.role === 'doctor'
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(msg.text)
      setCopyFailed(false)
      setCopied(true)
      clearTimeout(copyTimer.current)
      copyTimer.current = setTimeout(() => setCopied(false), 1800)
    } catch { setCopyFailed(true) }
  }

  return (
    <article className={`chat-message ${isDoctor ? 'from-doctor' : 'from-clara'}`} aria-label={isDoctor ? 'Your message' : 'CLARA response'}>
      {!isDoctor && <span className="message-avatar"><Activity size={18} /></span>}
      <div className="message-content">
        {!isDoctor && <div className="message-author">CLARA</div>}
        {!isDoctor && (msg.streaming || msg.actions?.length > 0 || msg.error || msg.interrupted) && <ActivityTimeline message={msg} />}
        {msg.text && (
          <div className="message-body"><ReactMarkdown>{msg.text}</ReactMarkdown>{msg.streaming && <span className="stream-cursor" aria-hidden="true" />}</div>
        )}
        {!isDoctor && msg.sources?.length > 0 && (
          <details className="message-sources">
            <summary><FileText size={14} />{msg.sources.length} source{msg.sources.length === 1 ? '' : 's'}<ChevronDown size={14} /></summary>
            <ul>{msg.sources.map((source, index) => (
              <li key={`${source.source}-${source.page}-${index}`}>
                <span className="source-kind">{source.type === 'patient_pdf' ? 'Patient PDF' : 'Guideline'}</span>
                <button className="citation-link" onClick={() => onSource(source)}><span>{source.title || source.source}{source.page ? ` / p. ${source.page}` : ''}</span><ArrowUpRight size={14} /></button>
              </li>
            ))}</ul>
          </details>
        )}
        {!isDoctor && !msg.streaming && msg.text && (
          <div className="message-actions">
            <button className="icon-button" title={copied ? 'Copied' : 'Copy response'} aria-label={copied ? 'Response copied' : 'Copy response'} onClick={copy}>
              {copied ? <Check size={15} /> : <Copy size={15} />}
            </button>
            {copyFailed && <span role="status">Copy unavailable</span>}
            {msg.guidelines && <span><ShieldCheck size={13} />Guidelines referenced</span>}
            {msg.mlUsed && <span>ML assessment</span>}
            {msg.durationMs != null && <span>{(msg.durationMs / 1000).toFixed(1)}s</span>}
            {!!msg.actions?.length && <button className="activity-detail-link" onClick={onActivity}>View activity</button>}
          </div>
        )}
      </div>
    </article>
  )
}

export default function ChatPanel({ patient, patients, patientsLoading, patientsError, onSelectPatient,
  activeSection, isActive, messages, loading, onSend, onClear, onStop, onOpenRecord }) {
  const [input, setInput] = useState('')
  const scrollRef = useRef(null)
  const taRef = useRef(null)
  const followResponse = useRef(true)
  const latestResponse = messages.findLast(message => message.role === 'clara')
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [evidenceTab, setEvidenceTab] = useState('sources')
  const [selectedSource, setSelectedSource] = useState(null)
  const [evidenceIndex, setEvidenceIndex] = useState(null)
  const evidenceMessage = evidenceIndex == null ? latestResponse : messages[evidenceIndex]
  const evidenceSources = evidenceMessage?.sources || []
  const closeEvidence = useCallback(() => setEvidenceOpen(false), [])
  useEffect(() => {
    if (latestResponse?.sources?.length) {
      setSelectedSource(source => source || latestResponse.sources[0])
    }
  }, [latestResponse?.sources])
  const hasConversation = messages.some(message => message.role === 'doctor')
  const visibleMessages = hasConversation ? messages : []

  useEffect(() => {
    if (isActive && followResponse.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, isActive])

  useEffect(() => {
    if (!taRef.current) return
    taRef.current.style.height = 'auto'
    taRef.current.style.height = Math.min(taRef.current.scrollHeight, 180) + 'px'
  }, [input, isActive])

  const handleSend = event => {
    event?.preventDefault()
    if (!input.trim() || loading || !patient) return
    followResponse.current = true
    setEvidenceIndex(null)
    setSelectedSource(null)
    onSend(input.trim(), activeSection)
    setInput('')
  }

  const newChat = () => {
    onClear()
    setInput('')
    followResponse.current = true
    taRef.current?.focus()
  }

  const composer = (
    <div className="composer-area">
      <form className="chat-composer" onSubmit={handleSend}>
        <textarea ref={taRef} value={input} onChange={event => setInput(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) handleSend(event)
          }}
          placeholder={patient ? 'Ask about this patient...' : 'Ask CLARA...'} aria-label="Message CLARA" rows={2} />
        <div className="composer-controls">
          <div className="patient-picker">
            <UserRound size={15} />
            <label className="sr-only" htmlFor="chat-patient">Patient for this conversation</label>
            <select id="chat-patient" value={patient?.id || ''} disabled={patientsLoading || !!patientsError}
              onChange={event => onSelectPatient(patients.find(item => item.id === event.target.value) || null)}>
              <option value="">{patientsLoading ? 'Loading patients...' : patientsError ? 'Patients unavailable' : 'Select a patient'}</option>
              {patients.map(item => <option key={item.id} value={item.id}>{item.name} / {item.id}</option>)}
            </select>
            <ChevronDown size={13} />
          </div>
          {loading ? <button className="send-button stop-button" type="button" onClick={onStop} aria-label="Stop response" title="Stop response"><Square size={16} fill="currentColor" /></button>
            : <button className="send-button" type="submit" disabled={!input.trim() || !patient}
                aria-label="Send message" title={!patient ? 'Select a patient to send a message' : 'Send message'}><ArrowUp size={20} /></button>}
        </div>
      </form>
      {patient && <div className="composer-context">
        <span>Record {patient.id}<span className="context-separator">/</span>{activeSection.charAt(0).toUpperCase() + activeSection.slice(1)}</span>
        <button onClick={onOpenRecord}>View record<ArrowUpRight size={13} /></button>
      </div>}
      {patientsError && <p className="composer-error" role="alert">Patient records are currently unavailable.</p>}
    </div>
  )

  return (
    <div className="chat-workspace evidence-is-open">
    <div className={`chat-page ${hasConversation ? 'has-conversation' : 'is-new-chat'}`}>
      <div className="chat-page-toolbar">
        <span className="chat-context-label">{patient ? `Patient ${patient.id}` : 'New conversation'}</span>
        <div className="chat-toolbar-actions"><button className="text-button" onClick={newChat} title="New chat"><SquarePen size={16} />New chat</button>
          <button className="source-preview-tile" aria-label="Open source preview" aria-expanded={evidenceOpen} onClick={() => setEvidenceOpen(true)} title="Source preview"><FileText size={18} /><span>Sources<small>{evidenceSources.length} document{evidenceSources.length === 1 ? '' : 's'}</small></span><ArrowUpRight size={14} /></button></div>
      </div>
      {hasConversation ? (
        <>
          <div ref={scrollRef} className="conversation-scroll" onScroll={event => {
            const { scrollHeight, scrollTop, clientHeight } = event.currentTarget
            followResponse.current = scrollHeight - scrollTop - clientHeight < 100
          }}>
            <div className="conversation-content" role="log" aria-label="Conversation" aria-busy={loading}>
              {visibleMessages.map((message, index) => <Message key={index} msg={message}
                onSource={source => { setEvidenceIndex(index); setSelectedSource(source); setEvidenceTab('sources'); setEvidenceOpen(true) }}
                onActivity={() => { setEvidenceIndex(index); setEvidenceTab('activity'); setEvidenceOpen(true) }} />)}
            </div>
          </div>
          <div className="conversation-composer">{composer}</div>
        </>
      ) : (
        <div className="chat-welcome-scroll">
          <div className="chat-welcome">
            <div className="welcome-brand"><Activity size={30} strokeWidth={1.8} /><span>CLARA</span></div>
            <h1>How can I help, Doctor?</h1>
            {composer}
            <div className="suggested-prompts">
              {PROMPTS.map(({ icon: Icon, label, message }) => (
                <button key={label} onClick={() => { setInput(message); taRef.current?.focus() }}>
                  <Icon size={18} /><span>{label}</span><ArrowUpRight size={14} />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
    {isActive && <EvidencePanel mobileOpen={evidenceOpen} sources={evidenceSources} selectedSource={selectedSource} onSelectSource={setSelectedSource}
      onClose={closeEvidence} patientId={patient?.id} message={evidenceMessage} tab={evidenceTab} onTab={setEvidenceTab} />}
    </div>
  )
}
