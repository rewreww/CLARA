import { useEffect, useState } from 'react'
import { Check, ChevronDown, Circle, LoaderCircle, OctagonAlert, Square } from 'lucide-react'

export default function ActivityTimeline({ message, expanded = false }) {
  const [open, setOpen] = useState(expanded)
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!message?.streaming) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [message?.streaming])
  if (!message) return <div className="evidence-empty"><Circle size={24} /><p>No activity yet</p></div>
  const running = message.streaming
  const failed = message.error
  const stopped = message.interrupted
  const steps = message.actions || []
  const elapsed = running ? Math.max(0, Math.floor((now - (message.startedAt || now)) / 1000)) : Math.round((message.durationMs || 0) / 1000)
  const label = running ? message.status || 'Writing the response' : failed ? 'Response failed' : stopped ? 'Response stopped' : 'Response complete'
  const Icon = running ? LoaderCircle : failed ? OctagonAlert : stopped ? Square : Check
  return <div className={`activity-tracker ${running ? 'is-running' : ''}`}>
    <button className="activity-toggle" aria-label={`${label}, ${elapsed} seconds, activity details`} aria-expanded={open} onClick={() => setOpen(value => !value)}>
      <Icon size={15} className={running ? 'spin-icon' : ''} /><span className="activity-current" role={running ? 'status' : undefined}>{label}</span>
      <span className="activity-time">{elapsed}s</span><ChevronDown size={14} className={open ? 'is-expanded' : ''} />
    </button>
    {open && <ol className="activity-steps">{steps.map((step, index) => {
      const last = index === steps.length - 1
      const StepIcon = last && running ? LoaderCircle : last && failed ? OctagonAlert : last && stopped ? Square : Check
      return <li key={`${index}-${step.label}`}><StepIcon size={13} className={last && running ? 'spin-icon' : ''} /><span>{step.label}</span><small>{Math.max(0, Math.round((step.at - message.startedAt) / 1000))}s</small></li>
    })}{!steps.length && <li>No action details were recorded.</li>}</ol>}
  </div>
}
