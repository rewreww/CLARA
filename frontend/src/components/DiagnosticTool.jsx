import { useState, useRef, useCallback, useEffect } from 'react'

const LABS_URL = '/api/labs'

async function extractPdf(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${LABS_URL}/extract-pdf`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(`Server error ${res.status}`)
  return res.json()
}

async function getFlagged(text, fieldName) {
  if (!text?.trim()) return []
  try {
    const res = await fetch(`${LABS_URL}/diagnose-prep`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [fieldName]: text }),
    })
    if (!res.ok) return []
    const d = await res.json()
    return [
      ...(d.chemistry_results || []),
      ...(d.hematology_results || []),
      ...(d.microscopy_results || []),
    ].filter(r => {
      const f = String(r.flag || '').toUpperCase()
      return f === 'H' || f === 'L' || f === 'HIGH' || f === 'LOW'
    })
  } catch { return [] }
}

// ── Scanline decoration ───────────────────────────────────────────────────────
function ScanTag({ label, value, color = '#0ea5e9' }) {
  return (
    <div className="flex items-center gap-[5px]">
      <span className="font-mono text-[8px] text-muted uppercase tracking-[0.1em]">{label}</span>
      <span className="font-mono text-[9px] font-semibold" style={{ color }}>{value}</span>
    </div>
  )
}

// ── Abnormal chip ─────────────────────────────────────────────────────────────
function AbnormalChip({ result, side, onMount }) {
  const isHigh = String(result.flag || '').toUpperCase().startsWith('H')
  const color  = isHigh ? '#f87171' : '#60a5fa'
  return (
    <div
      ref={onMount}
      className={`font-mono text-[8px] px-[6px] py-[2px] rounded-[2px] shrink-0
        whitespace-nowrap flex items-center gap-[4px]
        ${side === 'left' ? 'self-end' : 'self-start'}`}
      style={{ background: `${color}12`, border: `1px solid ${color}40`, color }}
    >
      <span className="opacity-60">◈</span>
      {result.test_name}: {result.value}{result.unit ? ` ${result.unit}` : ''}
      <span>{isHigh ? '▲' : '▼'}</span>
    </div>
  )
}

// ── Upload box ────────────────────────────────────────────────────────────────
function UploadBox({ title, icon, description, multiple, files, onAdd, onRemove, side, flagged, onChipMount }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  return (
    <div className="flex flex-col overflow-hidden h-full"
      style={{
        background: 'linear-gradient(145deg, #0a111f 0%, #060d1a 100%)',
        border: '1px solid #1a2d4e',
        borderRadius: 10,
      }}>

      {/* Header */}
      <div className="px-[10px] py-[8px] shrink-0 flex items-center gap-[8px]"
        style={{ borderBottom: '1px solid #0f1e35' }}>
        <div className="w-[26px] h-[26px] rounded-[6px] flex items-center justify-center text-[12px] shrink-0"
          style={{ background: '#0d1e38', border: '1px solid #1a3050' }}>
          {icon}
        </div>
        <div className="min-w-0">
          <div className="font-mono text-[10px] font-semibold text-[#c8d8f0]">{title}</div>
          <div className="font-mono text-[8px] text-muted truncate">{description}</div>
        </div>
      </div>

      {/* Drop zone */}
      <div
        onDrop={e => { e.preventDefault(); setDragging(false); onAdd(e.dataTransfer.files) }}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onClick={() => inputRef.current?.click()}
        className="mx-[8px] mt-[7px] rounded-[6px] py-[6px] flex items-center
          justify-center cursor-pointer transition-all shrink-0"
        style={{
          border: `1px dashed ${dragging ? '#2563eb' : '#1a3050'}`,
          background: dragging ? 'rgba(37,99,235,0.06)' : 'transparent',
        }}
      >
        <input ref={inputRef} type="file" accept=".pdf" multiple={multiple} className="hidden"
          onChange={e => { onAdd(e.target.files); e.target.value = '' }} />
        <span className="font-mono text-[8px] select-none" style={{ color: dragging ? '#60a5fa' : '#2d4a6a' }}>
          {dragging ? '⬇ release to upload' : '+ drop PDF or click to browse'}
        </span>
      </div>

      {/* File list */}
      <div className="flex-1 overflow-y-auto px-[8px] py-[5px] min-h-0">
        {files.length === 0 ? (
          <div className="font-mono text-[8px] text-center py-2" style={{ color: '#1e3050' }}>
            no files loaded
          </div>
        ) : files.map((f, i) => (
          <div key={i} className="flex items-center justify-between py-[4px]"
            style={{ borderBottom: '1px solid #0d1e30' }}>
            <div className="flex items-center gap-[6px] min-w-0">
              <div className={`w-[4px] h-[4px] rounded-full shrink-0 ${
                f.loading ? 'bg-yellow-400 animate-pulse' : f.error ? 'bg-red-400' : 'bg-emerald-400'
              }`} />
              <div className="min-w-0">
                <div className="font-mono text-[9px] truncate" style={{ color: '#9ab0cc' }}>{f.file.name}</div>
                <div className="font-mono text-[8px]" style={{ color: '#3d5878' }}>
                  {f.loading ? 'reading...' : f.error ? 'error' : `${f.pages}p · ${f.charCount.toLocaleString()}c`}
                </div>
              </div>
            </div>
            <button onClick={() => onRemove(i)}
              className="font-mono text-[9px] bg-transparent border-none cursor-pointer ml-1 shrink-0
                transition-colors hover:text-red-400"
              style={{ color: '#2d4a6a' }}>✕</button>
          </div>
        ))}
      </div>

      {/* Abnormal chips */}
      {flagged.length > 0 && (
        <div className="px-[8px] py-[6px] flex flex-col gap-[3px]"
          style={{ borderTop: '1px solid rgba(239,68,68,0.15)' }}>
          {flagged.map((f, i) => (
            <AbnormalChip
              key={`${f.test_name}_${i}`}
              result={f}
              side={side}
              onMount={el => onChipMount(`${side}_${f.test_name}`, el)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Chief complaint ───────────────────────────────────────────────────────────
function ChiefComplaintBox({ value, onChange }) {
  return (
    <div className="flex flex-col overflow-hidden h-full"
      style={{
        background: 'linear-gradient(145deg, #0a111f 0%, #060d1a 100%)',
        border: '1px solid #1a2d4e',
        borderRadius: 10,
      }}>
      <div className="px-[10px] py-[8px] shrink-0 flex items-center gap-[8px]"
        style={{ borderBottom: '1px solid #0f1e35' }}>
        <div className="w-[26px] h-[26px] rounded-[6px] flex items-center justify-center text-[12px] shrink-0"
          style={{ background: '#0d1e38', border: '1px solid #1a3050' }}>
          🩺
        </div>
        <div>
          <div className="font-mono text-[10px] font-semibold text-[#c8d8f0]">Chief Complaint</div>
          <div className="font-mono text-[8px] text-muted">Describe the primary presentation</div>
        </div>
      </div>
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="e.g. 58M with 3-day chest pain, worse on exertion..."
        className="flex-1 bg-transparent border-none outline-none resize-none
          p-[10px] text-[11px] leading-[1.7] font-sans"
        style={{ color: '#c8d8f0', caretColor: '#2563eb' }}
      />
      {value && (
        <div className="px-[10px] py-[4px] flex gap-[10px]"
          style={{ borderTop: '1px solid #0f1e35' }}>
          <ScanTag label="chars" value={value.length} />
          <ScanTag label="words" value={value.trim().split(/\s+/).length} />
        </div>
      )}
    </div>
  )
}

// ── Risk bar ──────────────────────────────────────────────────────────────────
function RiskBar({ label, probability, risk }) {
  const color = risk === 'high' ? '#f87171' : risk === 'moderate' ? '#fbbf24' : '#34d399'
  const pct   = Math.round(probability * 100)
  return (
    <div className="mb-[8px]">
      <div className="flex justify-between items-center mb-[3px]">
        <span className="font-mono text-[8px] truncate pr-2" style={{ color: '#5a7898' }}>{label}</span>
        <span className="font-mono text-[9px] font-bold shrink-0" style={{ color }}>{pct}%</span>
      </div>
      <div className="h-[2px] rounded-full overflow-hidden" style={{ background: '#0d1e38' }}>
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${color}80, ${color})` }} />
      </div>
    </div>
  )
}

// ── Diagnosis panel ───────────────────────────────────────────────────────────
function DiagnosisPanel({ data, loading, onStop }) {

  if (loading) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center gap-5 rounded-[10px]"
        style={{ background: 'linear-gradient(160deg, #050b17 0%, #03070f 100%)' }}>

        {/* Pulsing ring */}
        <div className="relative w-14 h-14 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border border-blue-500/30 animate-ping" />
          <div className="absolute inset-2 rounded-full border border-blue-400/50 animate-spin-slow" style={{
            borderTopColor: '#3b82f6', borderRightColor: 'transparent',
            borderBottomColor: 'transparent', borderLeftColor: 'transparent',
          }} />
          <span className="text-[18px] opacity-60">⚕</span>
        </div>

        <div>
          <div className="font-mono text-[11px] text-center mb-1" style={{ color: '#4a7aaa' }}>
            analyzing clinical data
          </div>
          <div className="font-mono text-[8px] text-center" style={{ color: '#1e3a5a' }}>
            RAG · ML · LLM synthesis in progress
          </div>
        </div>

        <button onClick={onStop}
          className="px-[14px] py-[5px] rounded-[5px] font-mono text-[10px] transition-all cursor-pointer"
          style={{ border: '1px solid rgba(239,68,68,0.4)', color: '#f87171', background: 'rgba(239,68,68,0.08)' }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.15)'}
          onMouseLeave={e => e.currentTarget.style.background = 'rgba(239,68,68,0.08)'}>
          ■ abort
        </button>
      </div>
    )
  }

  if (data) {
    return (
      <div className="w-full h-full flex flex-col overflow-hidden rounded-[10px]"
        style={{
          background: 'linear-gradient(160deg, #050b17 0%, #03070f 100%)',
          border: '1px solid #0f2040',
        }}>

        {/* Header bar */}
        <div className="px-[14px] py-[9px] shrink-0 flex items-center justify-between"
          style={{ borderBottom: '1px solid #0d1e30' }}>
          <div className="flex items-center gap-[8px]">
            <div className="flex gap-[3px]">
              <div className="w-[5px] h-[5px] rounded-full bg-emerald-400" />
              <div className="w-[5px] h-[5px] rounded-full bg-emerald-400/30" />
              <div className="w-[5px] h-[5px] rounded-full bg-emerald-400/10" />
            </div>
            <span className="font-mono text-[9px] uppercase tracking-[0.14em]" style={{ color: '#0ea5e9' }}>
              diagnostic output
            </span>
          </div>
          <ScanTag label="hybrid" value="RAG + ML + LLM" color="#2563eb" />
        </div>

        <div className="flex-1 overflow-y-auto flex flex-col min-h-0 gap-[1px]">

          {/* Guidelines */}
          {data.guidelines && (
            <div className="mx-[12px] mt-[10px] rounded-[6px] p-[10px] shrink-0"
              style={{ background: '#060f20', border: '1px solid #0e2444' }}>
              <div className="font-mono text-[8px] uppercase tracking-[0.14em] mb-[6px] flex items-center gap-[5px]"
                style={{ color: '#1d4ed8' }}>
                <span>▸</span> clinical guidelines
              </div>
              <div className="text-[10px] leading-[1.65]" style={{ color: '#4a6d9a' }}>
                {data.guidelines}
              </div>
            </div>
          )}

          {/* ML risks */}
          {data.mlRisks?.length > 0 && (
            <div className="mx-[12px] mt-[8px] rounded-[6px] p-[10px] shrink-0"
              style={{ background: '#060f20', border: '1px solid #0e2444' }}>
              <div className="font-mono text-[8px] uppercase tracking-[0.14em] mb-[8px] flex items-center gap-[5px]"
                style={{ color: '#6b7280' }}>
                <span>▸</span> ml cardiac risk · ecg-based
              </div>
              {data.mlRisks.map(r => (
                <RiskBar key={r.label} label={r.label} probability={r.probability} risk={r.risk} />
              ))}
            </div>
          )}

          {/* LLM narrative */}
          <div className="px-[14px] pt-[12px] pb-[16px] text-[12px] leading-[1.85]
            whitespace-pre-wrap font-sans" style={{ color: '#c0d0e8' }}>
            {data.result}
          </div>

        </div>
      </div>
    )
  }

  return (
    <div className="w-full h-full flex flex-col items-center justify-center gap-3 rounded-[10px]"
      style={{ background: 'linear-gradient(160deg, #050b17 0%, #03070f 100%)' }}>
      <div className="text-[60px] select-none" style={{ opacity: 0.04 }}>⚕</div>
      <div className="font-mono text-[9px] uppercase tracking-[0.12em]" style={{ color: '#0f2040' }}>
        awaiting input
      </div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function DiagnosticTool() {
  const [chiefComplaint,  setChiefComplaint]  = useState('')
  const [labFiles,        setLabFiles]        = useState([])
  const [dischargeFiles,  setDischargeFiles]  = useState([])
  const [imagingFiles,    setImagingFiles]    = useState([])
  const [diagnosis,       setDiagnosis]       = useState(null)
  const [diagLoading,     setDiagLoading]     = useState(false)
  const [lines,           setLines]           = useState([])

  const abortRef  = useRef(null)
  const gridRef   = useRef(null)
  const centerRef = useRef(null)
  const chipRefs  = useRef({})

  const onChipMount = useCallback((key, el) => {
    if (el) chipRefs.current[key] = el
    else delete chipRefs.current[key]
  }, [])

  useEffect(() => {
    const calc = () => {
      if (!gridRef.current || !centerRef.current) return
      const gRect = gridRef.current.getBoundingClientRect()
      const cRect = centerRef.current.getBoundingClientRect()
      const next  = []
      for (const [key, el] of Object.entries(chipRefs.current)) {
        if (!el) continue
        const r    = el.getBoundingClientRect()
        const midY = r.top - gRect.top + r.height / 2
        const rL   = r.left - gRect.left
        const rR   = r.right - gRect.left
        const cL   = cRect.left - gRect.left
        const cR   = cRect.right - gRect.left
        if (rR < cL) next.push({ key, x1: rR + 2, y1: midY, x2: cL - 2, y2: midY })
        else if (rL > cR) next.push({ key, x1: cR + 2, y1: midY, x2: rL - 2, y2: midY })
      }
      setLines(next)
    }
    const t  = setTimeout(calc, 80)
    const ro = new ResizeObserver(calc)
    if (gridRef.current) ro.observe(gridRef.current)
    return () => { clearTimeout(t); ro.disconnect() }
  }, [labFiles, dischargeFiles, imagingFiles])

  const handleAdd = useCallback((setter, fieldName) => async (incoming) => {
    const pdfs = Array.from(incoming).filter(f => f.type === 'application/pdf')
    if (!pdfs.length) return
    setter(prev => [...prev, ...pdfs.map(file => ({
      file, loading: true, error: null, text: '', pages: 0, charCount: 0, flagged: [],
    }))])
    for (const file of pdfs) {
      try {
        const res = await extractPdf(file)
        setter(prev => prev.map(e => e.file === file && e.loading
          ? { ...e, loading: false, text: res.text, pages: res.pages, charCount: res.char_count } : e))
        const flagged = await getFlagged(res.text, fieldName)
        setter(prev => prev.map(e => e.file === file ? { ...e, flagged } : e))
      } catch (err) {
        setter(prev => prev.map(e => e.file === file && e.loading
          ? { ...e, loading: false, error: err.message } : e))
      }
    }
  }, [])

  const handleRemove = setter => i => setter(prev => prev.filter((_, idx) => idx !== i))
  const collect      = files  => files.filter(f => f.text).map(f => f.text).join('\n\n')

  const labFlagged = [...new Map(
    labFiles.flatMap(f => f.flagged || []).map(r => [r.test_name, r])
  ).values()]
  const dischFlagged = [...new Map(
    dischargeFiles.flatMap(f => f.flagged || []).map(r => [r.test_name, r])
  ).values()]

  const stopDiagnostic = () => abortRef.current?.abort()

  const runDiagnostic = async () => {
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setDiagLoading(true)
    setDiagnosis(null)
    try {
      const prepRes = await fetch(`${LABS_URL}/diagnose-prep`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          chief_complaint: chiefComplaint,
          lab_text:        collect(labFiles),
          discharge_text:  collect(dischargeFiles),
          imaging_text:    collect(imagingFiles),
        }),
        signal: ctrl.signal,
      })
      const prep = prepRes.ok ? await prepRes.json() : {}

      const diagRes = await fetch('/api/llm/diagnose', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ ...prep, chief_complaint: chiefComplaint, imaging_text: collect(imagingFiles) }),
        signal:  ctrl.signal,
      })
      if (!diagRes.ok) throw new Error(`LLM service ${diagRes.status}`)
      const d = await diagRes.json()
      setDiagnosis({ result: d.result, guidelines: d.guidelines, mlRisks: d.ml_risks })
    } catch (e) {
      if (e.name === 'AbortError') {
        setDiagnosis({ result: 'Analysis aborted.', guidelines: null, mlRisks: null })
      } else {
        setDiagnosis({
          result: `⚠ ${e.message}\n\nEnsure services are running on ports 8000 and 8001.`,
          guidelines: null, mlRisks: null,
        })
      }
    } finally {
      setDiagLoading(false)
      abortRef.current = null
    }
  }

  const totalFiles    = labFiles.length + dischargeFiles.length + imagingFiles.length
  const anyExtracting = [...labFiles, ...dischargeFiles, ...imagingFiles].some(f => f.loading)
  const hasInput      = chiefComplaint.trim().length > 0 ||
    [...labFiles, ...dischargeFiles, ...imagingFiles].some(f => f.text)

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ background: '#030810' }}>

      {/* ── Header ── */}
      <div className="px-5 py-[10px] shrink-0 flex items-center justify-between"
        style={{ borderBottom: '1px solid #0a1828', background: '#040c1a' }}>
        <div>
          <div className="flex items-center gap-[8px]">
            <span className="font-mono text-[11px] font-bold" style={{ color: '#c8d8f0' }}>
              Diagnostic Tool
            </span>
            <span className="font-mono text-[8px] px-[5px] py-[1px] rounded-[3px]"
              style={{ background: '#0d1e38', color: '#2563eb', border: '1px solid #1a3050' }}>
              HYBRID AI
            </span>
          </div>
          <div className="font-mono text-[9px] mt-[1px]" style={{ color: '#1e3a5a' }}>
            independent workspace · not linked to patient records
            {totalFiles > 0 && (
              <span style={{ color: '#0ea5e9' }}> · {totalFiles} file{totalFiles !== 1 ? 's' : ''}</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-[6px]">
          <button
            onClick={stopDiagnostic}
            disabled={!diagLoading}
            className="px-[12px] py-[6px] rounded-[6px] font-mono text-[10px] transition-all"
            style={{
              border: diagLoading ? '1px solid rgba(239,68,68,0.5)' : '1px solid #0f1e30',
              color:  diagLoading ? '#f87171' : '#1e3a5a',
              background: diagLoading ? 'rgba(239,68,68,0.08)' : 'transparent',
              cursor: diagLoading ? 'pointer' : 'not-allowed',
            }}>
            ■ abort
          </button>
          <button
            onClick={runDiagnostic}
            disabled={!hasInput || diagLoading || anyExtracting}
            className="px-[18px] py-[6px] rounded-[6px] font-mono text-[10px] font-semibold
              transition-all border-none"
            style={{
              background: (!hasInput || diagLoading || anyExtracting)
                ? '#0a1828' : 'linear-gradient(135deg, #1d4ed8, #2563eb)',
              color: (!hasInput || diagLoading || anyExtracting) ? '#1e3a5a' : '#e0edff',
              cursor: (!hasInput || diagLoading || anyExtracting) ? 'not-allowed' : 'pointer',
              boxShadow: (!hasInput || diagLoading || anyExtracting)
                ? 'none' : '0 0 16px rgba(37,99,235,0.3)',
            }}>
            {anyExtracting ? '⟳ reading pdfs...' : diagLoading ? '⟳ analyzing...' : '▶ run diagnostic'}
          </button>
        </div>
      </div>

      {/* ── Grid ── */}
      <div ref={gridRef} className="flex-1 min-h-0 relative p-[12px]">

        {/* SVG lines */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 30 }}>
          {lines.map(l => (
            <line key={l.key}
              x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
              stroke="#f87171" strokeWidth="1" strokeDasharray="4,3" opacity="0.5" />
          ))}
        </svg>

        <div className="w-full h-full grid gap-[10px]" style={{
          gridTemplateColumns: '300px 1fr 300px',
          gridTemplateRows: '1fr 1fr',
        }}>

          <div style={{ gridColumn: 1, gridRow: 1, minHeight: 0 }}>
            <ChiefComplaintBox value={chiefComplaint} onChange={setChiefComplaint} />
          </div>

          <div style={{ gridColumn: 3, gridRow: 1, minHeight: 0 }}>
            <UploadBox title="Laboratory Results" icon="🧪"
              description="CBC · chemistry · urinalysis"
              multiple files={labFiles}
              onAdd={handleAdd(setLabFiles, 'lab_text')}
              onRemove={handleRemove(setLabFiles)}
              side="right" flagged={labFlagged} onChipMount={onChipMount} />
          </div>

          <div style={{ gridColumn: 1, gridRow: 2, minHeight: 0 }}>
            <UploadBox title="Discharge Summary" icon="📋"
              description="From referring or previous hospital"
              multiple files={dischargeFiles}
              onAdd={handleAdd(setDischargeFiles, 'discharge_text')}
              onRemove={handleRemove(setDischargeFiles)}
              side="left" flagged={dischFlagged} onChipMount={onChipMount} />
          </div>

          <div style={{ gridColumn: 3, gridRow: 2, minHeight: 0 }}>
            <UploadBox title="Imaging & Radiology" icon="🔬"
              description="X-ray · CT · MRI · ECG reports"
              multiple files={imagingFiles}
              onAdd={handleAdd(setImagingFiles, 'imaging_text')}
              onRemove={handleRemove(setImagingFiles)}
              side="right" flagged={[]} onChipMount={onChipMount} />
          </div>

          <div ref={centerRef} style={{ gridColumn: 2, gridRow: '1 / 3', minHeight: 0 }}>
            <DiagnosisPanel data={diagnosis} loading={diagLoading} onStop={stopDiagnostic} />
          </div>

        </div>
      </div>
    </div>
  )
}