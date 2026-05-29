import { useState, useEffect, useCallback } from 'react'

function parseFreq(text) {
  const t = text.toUpperCase()
  if (/\bQ\.?I\.?D\.?\b|FOUR\s+TIMES\s+A?\s*DAY|4\s*X\/?\s*(?:DAY|D\b)|EVERY\s+6\s*H/.test(t))
    return { label: '4×/day', color: '#ef4444' }
  if (/\bT\.?I\.?D\.?\b|\bTDS\b|THREE\s+TIMES\s+A?\s*DAY|3\s*X\/?\s*(?:DAY|D\b)|EVERY\s+8\s*H/.test(t))
    return { label: '3×/day', color: '#f59e0b' }
  if (/\bB\.?I\.?D\.?\b|\bBD\b|TWICE\s+A?\s*DAY|TWO\s+TIMES\s+A?\s*DAY|2\s*X\/?\s*(?:DAY|D\b)|EVERY\s+12\s*H|\bQ12/.test(t))
    return { label: '2×/day', color: '#0ea5e9' }
  if (/\bO\.?D\.?\b|ONCE\s+(?:A\s+)?DAY|ONCE\s+DAILY|ONE\s+TIME\s+A?\s*DAY|1\s*X\/?\s*(?:DAY|D\b)/.test(t))
    return { label: '1×/day', color: '#10b981' }
  if (/\bPRN\b|AS\s+NEEDED/.test(t))
    return { label: 'PRN', color: '#8b5cf6' }
  if (/\bSTAT\b/.test(t))
    return { label: 'STAT', color: '#ef4444' }
  if (/\bHS\b|BEDTIME|BEFORE\s+BED|AT\s+NIGHT/.test(t))
    return { label: 'HS', color: '#6b7280' }
  return null
}

function MedItem({ index, med }) {
  const freq = parseFreq(med)
  return (
    <div className="flex items-center gap-3 px-4 py-[8px]
      border-b border-border/40 last:border-b-0">
      <span className="font-mono text-[10px] text-muted shrink-0 w-[18px] text-right">
        {index + 1}.
      </span>
      <span className="flex-1 text-[12px] leading-[1.5] text-[#d7e2f0] min-w-0">
        {med}
      </span>
      {freq && (
        <span
          className="font-mono text-[9px] font-semibold px-[6px] py-[2px] rounded-[4px] shrink-0"
          style={{ color: freq.color, background: `${freq.color}22` }}>
          {freq.label}
        </span>
      )}
    </div>
  )
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return (
    <button onClick={copy}
      className="px-3 py-[5px] rounded-[6px] font-mono text-[10px] border border-border
        text-muted hover:border-accent hover:text-accent transition-colors">
      {copied ? '✓ Copied' : 'Copy All'}
    </button>
  )
}

export default function PrescriptionsPanel({ patient }) {
  const [fileList,     setFileList]     = useState([])
  const [currentIndex, setCurrentIndex] = useState(null)
  const [visitData,    setVisitData]    = useState(null)
  const [loading,      setLoading]      = useState(false)
  const [showInstr,    setShowInstr]    = useState(true)

  const fetchVisit = useCallback((patientId, fileName) => {
    setLoading(true)
    fetch('/api/labs/discharge-parsed', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ patient: patientId, file_name: fileName }),
    })
      .then(r => r.json())
      .then(setVisitData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!patient?.id) return
    setFileList([])
    setVisitData(null)
    fetch('/api/labs/discharge-list', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ patient: patient.id }),
    })
      .then(r => r.json())
      .then(d => {
        const files = d.files || []
        setFileList(files)
        if (files.length > 0) {
          const latest = files.length - 1
          setCurrentIndex(latest)
          fetchVisit(patient.id, files[latest].file_name)
        }
      })
      .catch(() => {})
  }, [patient?.id, fetchVisit])

  const navigateTo = (index) => {
    const file = fileList[index]
    if (!file || loading) return
    setCurrentIndex(index)
    fetchVisit(patient.id, file.file_name)
  }

  const total    = fileList.length
  const showNav  = total > 1
  const meds     = visitData?.medications  || []
  const instrs   = visitData?.instructions || []
  const followup = visitData?.followup
  const copyText = meds.map((m, i) => `${i + 1}. ${m}`).join('\n')

  return (
    <div className="p-[16px_20px] overflow-y-auto h-full">

      {/* Header */}
      <div className="flex items-center gap-3 font-mono text-[10px] tracking-[0.1em]
        uppercase text-accent mb-[14px]">
        ● Prescriptions
        {showNav && <>
          <button onClick={() => navigateTo(currentIndex - 1)}
            disabled={currentIndex === 0 || loading}
            className="text-muted hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed
              transition-colors normal-case text-[13px] leading-none">‹</button>
          <span className="text-muted normal-case tracking-normal">
            Visit {currentIndex + 1} of {total}
            {fileList[currentIndex]?.date_label && ` · ${fileList[currentIndex].date_label}`}
          </span>
          <button onClick={() => navigateTo(currentIndex + 1)}
            disabled={currentIndex === total - 1 || loading}
            className="text-muted hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed
              transition-colors normal-case text-[13px] leading-none">›</button>
        </>}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1,2,3,4].map(i => (
            <div key={i} className="h-[36px] bg-card border border-border rounded-[8px] animate-pulse" />
          ))}
        </div>

      ) : !visitData?.found ? (
        <div className="text-muted font-mono text-[12px]">No discharge summary found.</div>

      ) : (
        <>
          {/* Final diagnosis */}
          {visitData.final_dx && (
            <div className="mb-3 px-4 py-3 bg-card border border-border rounded-[8px]">
              <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted mb-1">
                Final Diagnosis
              </div>
              <div className="text-[12px] text-[#d7e2f0] leading-[1.6]">{visitData.final_dx}</div>
            </div>
          )}

          {/* Medications */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-[6px]">
              <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted">
                Home Medications
              </div>
              {meds.length > 0 && <CopyButton text={copyText} />}
            </div>
            <div className="bg-card border border-border rounded-[8px] overflow-hidden">
              {meds.length === 0 ? (
                <div className="px-4 py-3 text-[12px] text-muted font-mono">
                  No medications recorded.
                </div>
              ) : (
                meds.map((med, i) => <MedItem key={i} index={i} med={med} />)
              )}
            </div>
          </div>

          {/* Instructions */}
          {instrs.length > 0 && (
            <div className="mb-3">
              <div
                onClick={() => setShowInstr(o => !o)}
                className="flex items-center justify-between mb-[6px] cursor-pointer group">
                <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted
                  group-hover:text-accent transition-colors">
                  Instructions
                </div>
                <span className="text-[9px] text-muted"
                  style={{ display: 'inline-block', transform: showInstr ? 'rotate(90deg)' : 'none' }}>
                  ▶
                </span>
              </div>
              {showInstr && (
                <div className="bg-card border border-border rounded-[8px] overflow-hidden">
                  {instrs.map((instr, i) => (
                    <div key={i} className="flex items-start gap-3 px-4 py-[8px]
                      border-b border-border/40 last:border-b-0">
                      <span className="font-mono text-[10px] text-muted shrink-0 w-[18px] text-right mt-[1px]">
                        {i + 1}.
                      </span>
                      <span className="text-[12px] leading-[1.5] text-[#d7e2f0]">{instr}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Follow-up */}
          {followup && (
            <div>
              <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted mb-[6px]">
                Follow-up
              </div>
              <div className="bg-card border border-accent/20 rounded-[8px] px-4 py-3">
                <div className="text-[12px] text-[#d7e2f0] leading-[1.6]">{followup}</div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}