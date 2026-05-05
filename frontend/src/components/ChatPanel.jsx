import { useRef, useEffect, useState } from 'react'
import { QUICK_PROMPTS } from '../constants'

function MessageBubble({ msg }) {
  const isDoctor = msg.role === 'doctor'
  return (
    <div className={`flex flex-col gap-1 animate-fade-up ${isDoctor ? 'items-end' : 'items-start'}`}>
      <div className="font-mono text-[9px] tracking-[0.1em] uppercase text-muted px-1">
        {isDoctor ? 'DOCTOR' : 'CLARA'}
      </div>
      <div className="max-w-[92%] px-[13px] py-[10px] text-[12.5px] leading-[1.6]"
        style={{
          borderRadius:    isDoctor ? '10px 10px 4px 10px' : '10px 10px 10px 4px',
          background:      isDoctor ? 'rgba(37,99,235,0.15)' : '#0d1526',
          border:          isDoctor ? '1px solid rgba(37,99,235,0.25)' : '1px solid #1a2d4e',
          color:           '#dde4f0',
        }}>
        {msg.text}
      </div>

      {/* Meta tags — only for CLARA messages */}
      {!isDoctor && (msg.tools?.length > 0 || msg.guidelines || msg.emergency || msg.flags?.length > 0) && (
        <div className="flex gap-[5px] flex-wrap px-1">
          {msg.tools?.map(t => (
            <span key={t} className="text-[9px] px-[7px] py-[2px] rounded-[3px]
              bg-accent2/15 text-accent2 font-mono">{t}</span>
          ))}
          {msg.guidelines && (
            <span className="text-[9px] px-[7px] py-[2px] rounded-[3px]
              bg-success/15 text-success font-mono">guidelines</span>
          )}
          {msg.emergency && (
            <span className="text-[9px] px-[7px] py-[2px] rounded-[3px]
              bg-danger/15 text-danger font-mono">EMERGENCY</span>
          )}
          {!msg.emergency && msg.flags?.length > 0 && (
            <span className="text-[9px] px-[7px] py-[2px] rounded-[3px]
              bg-warning/15 text-warning font-mono">
              ⚠ {msg.flags.length} flag{msg.flags.length > 1 ? 's' : ''}
            </span>
          )}
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

export default function ChatPanel({ patient, ruleFlags, isEmergency, messages, loading, onSend, onClear }) {
  const [input,  setInput]  = useState('')
  const bottomRef = useRef(null)
  const taRef     = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = () => {
    if (!input.trim() || loading) return
    onSend(input.trim())
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

      {/* Header */}
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
          {patient ? `patient: ${patient.id} · session active` : 'no patient selected'}
        </div>
      </div>

      {/* Rule flags */}
      {ruleFlags.length > 0 && (
        <div className="mx-3 mt-2 px-3 py-2 rounded-[8px] font-mono text-[10px] shrink-0"
          style={{
            background:   isEmergency ? 'rgba(239,68,68,0.1)'  : 'rgba(245,158,11,0.08)',
            border:       `1px solid ${isEmergency ? 'rgba(239,68,68,0.3)' : 'rgba(245,158,11,0.2)'}`,
            color:        isEmergency ? '#ef4444' : '#f59e0b',
          }}>
          <div className="tracking-[0.1em] uppercase mb-[5px]">⚠ Rule Engine Alerts</div>
          {ruleFlags.map((f, i) => (
            <div key={i} className="leading-[1.6]">! {f}</div>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-[10px]">
        {messages.map((m, i) => <MessageBubble key={i} msg={m} />)}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Quick prompts */}
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

      {/* Input area */}
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
