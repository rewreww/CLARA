import { useRef, useEffect, useState } from 'react'
import { QUICK_PROMPTS } from '../constants'

function MessageBubble({ msg }) {
  const isDoctor = msg.role === 'doctor'
  const workedFor = msg.durationMs == null ? null : `${(msg.durationMs / 1000).toFixed(1)}s`
  return (
    <div className={`flex flex-col gap-1 animate-fade-up ${isDoctor ? 'items-end' : 'items-start'}`}>
      <div className="font-mono text-[9px] tracking-[0.1em] uppercase text-muted px-1">
        {isDoctor ? 'DOCTOR' : 'CLARA'}
      </div>
      <div className="max-w-[92%] px-[13px] py-[10px] text-[12.5px] leading-[1.6]"
        style={{
          borderRadius: isDoctor ? '10px 10px 4px 10px' : '10px 10px 10px 4px',
          background:   isDoctor ? 'rgba(37,99,235,0.15)' : '#0d1526',
          border:       isDoctor ? '1px solid rgba(37,99,235,0.25)' : '1px solid #1a2d4e',
          color: '#dde4f0',
        }}>
        {!msg.text && msg.streaming ? (
          <div className="flex items-center gap-2 font-mono text-[10px]">
            <span className="status-shimmer">{msg.status || 'Preparing a response'}</span>
            <span className="flex gap-[3px]" aria-hidden="true">
              <span className="w-[3px] h-[3px] rounded-full bg-accent2 dot-1" />
              <span className="w-[3px] h-[3px] rounded-full bg-accent2 dot-2" />
              <span className="w-[3px] h-[3px] rounded-full bg-accent2 dot-3" />
            </span>
          </div>
        ) : (
          <>
            {msg.text}
            {msg.streaming && (
              <span className="inline-block w-[2px] h-[14px] bg-accent2 ml-[2px]
                align-middle animate-pulse-dot" />
            )}
          </>
        )}
      </div>

      {!isDoctor && (msg.tools?.length > 0 || msg.guidelines || msg.mlUsed || workedFor) && (
        <div className="flex gap-[5px] flex-wrap px-1">
          {msg.tools?.map(t => (
            <span key={t} className="text-[9px] px-[7px] py-[2px] rounded-[3px]
              bg-accent2/15 text-accent2 font-mono">{t}</span>
          ))}
          {msg.guidelines && (
            <span className="text-[9px] px-[7px] py-[2px] rounded-[3px]
              bg-success/15 text-success font-mono">guidelines</span>
          )}
          {msg.mlUsed && (
            <span className="text-[9px] px-[7px] py-[2px] rounded-[3px]
              bg-[#8b5cf6]/15 text-[#c4b5fd] font-mono">ML assessment</span>
          )}
          {workedFor && (
            <span className="text-[9px] px-[3px] py-[2px] text-muted font-mono">
              Worked for {workedFor}
            </span>
          )}
        </div>
      )}

      {!isDoctor && msg.sources?.length > 0 && (
        <div className="w-full max-w-[92%] px-[10px] py-[8px] rounded-[6px]"
          style={{ background: '#091426', border: '1px solid #183254' }}>
          <div className="font-mono text-[8px] uppercase tracking-[0.1em] mb-[5px]" style={{ color: '#5d8fbd' }}>
            Guideline sources
          </div>
          <div className="flex flex-col gap-[4px]">
            {msg.sources.slice(0, 4).map((source, index) => (
              <div key={`${source.source}_${source.page}_${index}`} className="flex items-center gap-[6px] min-w-0">
                <span className="font-mono text-[9px] text-accent2 shrink-0">[PDF]</span>
                <span className="font-mono text-[9px] text-[#b9cce3] truncate">{source.title}</span>
                {source.page && <span className="font-mono text-[9px] text-[#6b8eae] shrink-0">p.{source.page}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex flex-col items-start gap-1">
      <div className="font-mono text-[9px] tracking-[0.1em] uppercase text-muted px-1">CLARA</div>
      <div className="px-[14px] py-[10px] bg-card border border-border
        rounded-[10px_10px_10px_4px] flex items-center gap-[5px]">
        {[0, 1, 2].map(n => (
          <div key={n} className={`w-[5px] h-[5px] rounded-full bg-accent2 dot-${n + 1}`} />
        ))}
      </div>
    </div>
  )
}

// ↓ activeSection added to props
export default function ChatPanel({ patient, activeSection, messages, loading, onSend, onClear }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)
  const taRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = () => {
    if (!input.trim() || loading) return
    onSend(input.trim(), activeSection)   // ← pass activeSection here
    setInput('')
    if (taRef.current) taRef.current.style.height = 'auto'
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const autoResize = (e) => {
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px'
  }

  return (
    <div className="flex flex-col h-full bg-panel border-l border-border">

      <div className="px-4 py-[13px] border-b border-border shrink-0">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2 text-[13px] font-semibold">
            <span className="w-2 h-2 rounded-full bg-accent2 animate-pulse-dot
              shadow-[0_0_8px_#0ea5e9]" />
            CLARA Assistant
          </div>
          <button onClick={onClear}
            className="font-mono text-[10px] text-muted px-2 py-[3px] rounded
              bg-card border border-border cursor-pointer transition-all
              hover:text-danger hover:border-danger">
            CLEAR
          </button>
        </div>
        <div className="font-mono text-[10px] text-muted">
          {patient
            ? `patient: ${patient.id} · ${activeSection ?? 'overview'} · session active`
            : 'no patient selected'}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-[10px]">
        {messages.map((m, i) => <MessageBubble key={i} msg={m} />)}
        {loading && !messages.some(m => m.streaming) && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      <div className="px-3 pt-2 flex gap-[6px] flex-wrap shrink-0">
        {QUICK_PROMPTS.map(q => (
          <button key={q} onClick={() => setInput(q)}
            className="font-mono text-[10px] px-[9px] py-1 rounded bg-card border border-border
              text-muted cursor-pointer transition-all whitespace-nowrap
              hover:border-accent2 hover:text-accent2">
            {q}
          </button>
        ))}
      </div>

      <div className="p-3 shrink-0">
        <div className="flex gap-2 items-end">
          <textarea ref={taRef} value={input}
            onChange={e => { setInput(e.target.value); autoResize(e) }}
            onKeyDown={handleKey}
            placeholder="Ask CLARA about this patient..."
            rows={1}
            className="flex-1 bg-card border border-border rounded-[8px] px-3 py-[9px]
              text-[12.5px] text-[#dde4f0] resize-none outline-none min-h-[38px]
              max-h-[100px] leading-[1.4] transition-colors placeholder:text-muted
              focus:border-accent font-sans"
          />
          <button onClick={handleSend}
            disabled={loading || !input.trim()}
            className={`w-[38px] h-[38px] rounded-[8px] border-none flex items-center
              justify-center text-[14px] text-white shrink-0 transition-all
              ${loading || !input.trim()
                ? 'bg-border cursor-not-allowed'
                : 'bg-accent cursor-pointer hover:bg-blue-700'}`}>
            ➤
          </button>
        </div>
      </div>
    </div>
  )
}
