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
  } catch {
    return []
  }
}

// ── Abnormal chip ────────────────────────────────────────────────────────────
function AbnormalChip({ result, side, onMount }) {
  const isHigh = String(result.flag || '').toUpperCase().startsWith('H')
  return (
    <div
      ref={onMount}
      className={`font-mono text-[9px] px-[5px] py-[1px] rounded-[3px] shrink-0
        bg-danger/10 border border-danger/40 text-danger whitespace-nowrap
        ${side === 'left' ? 'self-end' : 'self-start'}`}
    >
      {result.test_name}: {result.value}{result.unit ? ` ${result.unit}` : ''} {isHigh ? '↑' : '↓'}
    </div>
  )
}

// ── Upload box ───────────────────────────────────────────────────────────────
function UploadBox({ title, icon, description, multiple, files, onAdd, onRemove, side, flagged, onChipMount }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  return (
    <div className="bg-card border border-border rounded-[10px] flex flex-col overflow-hidden">

      <div className="px-[10px] py-[7px] border-b border-border shrink-0 flex items-center gap-[6px]">
        <span className="text-[12px]">{icon}</span>
        <div>
          <div className="font-mono text-[10px] font-semibold text-[#dde4f0]">{title}</div>
          <div className="font-mono text-[8px] text-muted">{description}</div>
        </div>
      </div>

      <div
        onDrop={e => { e.preventDefault(); setDragging(false); onAdd(e.dataTransfer.files) }}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onClick={() => inputRef.current?.click()}
        className={`mx-[8px] mt-[7px] border border-dashed rounded-[6px] py-[5px]
          flex items-center justify-center cursor-pointer transition-all shrink-0
          ${dragging ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/40'}`}
      >
        <input ref={inputRef} type="file" accept=".pdf" multiple={multiple} className="hidden"
          onChange={e => { onAdd(e.target.files); e.target.value = '' }} />
        <span className="font-mono text-[9px] text-muted select-none">
          {dragging ? 'Drop here' : '+ Drop PDF or browse'}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-[8px] py-[5px] min-h-0">
        {files.length === 0 ? (
          <div className="font-mono text-[9px] text-border text-center py-1">No files</div>
        ) : files.map((f, i) => (
          <div key={i} className="flex items-center justify-between py-[3px]
            border-b border-border/30 last:border-0">
            <div className="flex items-center gap-[5px] min-w-0">
              <div className={`w-[5px] h-[5px] rounded-full shrink-0
                ${f.loading ? 'bg-warning animate-pulse' : f.error ? 'bg-danger' : 'bg-success'}`} />
              <div className="min-w-0">
                <div className="font-mono text-[9px] truncate text-[#dde4f0]">{f.file.name}</div>
                <div className="font-mono text-[8px] text-muted">
                  {f.loading ? 'Extracting...'
                    : f.error ? 'Failed'
                      : `${f.pages}p · ${f.charCount.toLocaleString()}c`}
                </div>
              </div>
            </div>
            <button onClick={() => onRemove(i)}
              className="font-mono text-[9px] text-muted hover:text-danger
                bg-transparent border-none cursor-pointer ml-1 shrink-0">✕</button>
          </div>
        ))}
      </div>

      {flagged.length > 0 && (
        <div className="px-[8px] py-[5px] border-t border-danger/20 flex flex-col gap-[3px]">
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

// ── Chief complaint ──────────────────────────────────────────────────────────
function ChiefComplaintBox({ value, onChange }) {
  return (
    <div className="bg-card border border-border rounded-[10px] flex flex-col overflow-hidden">
      <div className="px-[10px] py-[7px] border-b border-border shrink-0 flex items-center gap-[6px]">
        <span className="text-[12px]">🩺</span>
        <div>
          <div className="font-mono text-[10px] font-semibold text-[#dde4f0]">Chief Complaint</div>
          <div className="font-mono text-[8px] text-muted">Type the patient's main problem</div>
        </div>
      </div>
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        className="flex-1 bg-transparent border-none outline-none resize-none
          p-[10px] text-[11px] text-[#dde4f0] leading-[1.65] font-sans"
      />
    </div>
  )
}

// ── Center diagnosis panel ───────────────────────────────────────────────────
function DiagnosisPanel({ result, loading, onStop }) {
  if (loading) {
    return (
      <div className="bg-[#060b14] rounded-[10px] w-full h-full
        flex flex-col items-center justify-center gap-4">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent
          rounded-full animate-spin-slow" />
        <div className="font-mono text-[11px] text-muted">Analyzing clinical data...</div>
        <button onClick={onStop}
          className="mt-1 px-[12px] py-[5px] rounded-[6px] text-[11px]
            border border-danger/50 text-danger bg-danger/10
            hover:bg-danger/20 transition-all cursor-pointer">
          ■ Stop
        </button>
      </div>
    )
  }

  if (result) {
    return (
      <div className="bg-[#060b14] rounded-[10px] w-full h-full flex flex-col overflow-hidden">
        <div className="px-[14px] py-[9px] border-b border-border/40 shrink-0 flex items-center gap-2">
          <span className="w-[6px] h-[6px] rounded-full bg-success" />
          <span className="font-mono text-[10px] text-accent2 uppercase tracking-[0.1em]">
            Diagnostic Result
          </span>
        </div>
        <div className="flex-1 overflow-y-auto p-[16px] text-[12px]
          leading-[1.8] text-[#dde4f0] whitespace-pre-wrap font-sans">
          {result}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-[#060b14] rounded-[10px] w-full h-full
      flex items-center justify-center">
      <div className="text-[52px] select-none" style={{ opacity: 0.06 }}>⚕</div>
    </div>
  )
}

// ── Main ─────────────────────────────────────────────────────────────────────
export default function DiagnosticTool() {
  const [chiefComplaint, setChiefComplaint] = useState('')
  const [labFiles, setLabFiles] = useState([])
  const [dischargeFiles, setDischargeFiles] = useState([])
  const [imagingFiles, setImagingFiles] = useState([])
  const [diagnosis, setDiagnosis] = useState(null)
  const [diagLoading, setDiagLoading] = useState(false)
  const [lines, setLines] = useState([])

  const abortRef = useRef(null)
  const gridRef = useRef(null)
  const centerRef = useRef(null)
  const chipRefs = useRef({})

  const onChipMount = useCallback((key, el) => {
    if (el) chipRefs.current[key] = el
    else delete chipRefs.current[key]
  }, [])

  // Recalculate SVG lines whenever files change
  useEffect(() => {
    const calc = () => {
      if (!gridRef.current || !centerRef.current) return
      const gRect = gridRef.current.getBoundingClientRect()
      const cRect = centerRef.current.getBoundingClientRect()
      const cLeft = cRect.left - gRect.left
      const cRight = cRect.right - gRect.left

      const next = []
      for (const [key, el] of Object.entries(chipRefs.current)) {
        if (!el) continue
        const r = el.getBoundingClientRect()
        const midY = r.top - gRect.top + r.height / 2
        const rL = r.left - gRect.left
        const rR = r.right - gRect.left

        if (rR < cLeft) {
          // chip is left of center panel
          next.push({ key, x1: rR + 2, y1: midY, x2: cLeft - 2, y2: midY })
        } else if (rL > cRight) {
          // chip is right of center panel
          next.push({ key, x1: cRight + 2, y1: midY, x2: rL - 2, y2: midY })
        }
      }
      setLines(next)
    }

    const t = setTimeout(calc, 80)
    const ro = new ResizeObserver(calc)
    if (gridRef.current) ro.observe(gridRef.current)
    return () => { clearTimeout(t); ro.disconnect() }
  }, [labFiles, dischargeFiles])

  const handleAdd = useCallback((setter, fieldName) => async (incoming) => {
    const pdfs = Array.from(incoming).filter(f => f.type === 'application/pdf')
    if (!pdfs.length) return

    setter(prev => [
      ...prev,
      ...pdfs.map(file => ({ file, loading: true, error: null, text: '', pages: 0, charCount: 0, flagged: [] })),
    ])

    for (const file of pdfs) {
      try {
        const res = await extractPdf(file)
        // First update with extracted text
        setter(prev => prev.map(e =>
          e.file === file && e.loading
            ? { ...e, loading: false, text: res.text, pages: res.pages, charCount: res.char_count }
            : e
        ))
        // Then get flagged results from the extracted text
        const flagged = await getFlagged(res.text, fieldName)
        setter(prev => prev.map(e =>
          e.file === file ? { ...e, flagged } : e
        ))
      } catch (err) {
        setter(prev => prev.map(e =>
          e.file === file && e.loading
            ? { ...e, loading: false, error: err.message }
            : e
        ))
      }
    }
  }, [])

  const handleRemove = setter => i =>
    setter(prev => prev.filter((_, idx) => idx !== i))

  const collect = files =>
    files.filter(f => f.text).map(f => f.text).join('\n\n')

  // Deduplicate flagged items across files in same section
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
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chief_complaint: chiefComplaint,
          lab_text: collect(labFiles),
          discharge_text: collect(dischargeFiles),
          imaging_text: collect(imagingFiles),
        }),
        signal: ctrl.signal,
      })
      const prep = prepRes.ok ? await prepRes.json() : {}

      const diagRes = await fetch('/api/llm/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...prep,
          chief_complaint: chiefComplaint,
          lab_text: collect(labFiles),
          discharge_text: collect(dischargeFiles),
          imaging_text: collect(imagingFiles),
        }),
        signal: ctrl.signal,
      })
      if (!diagRes.ok) throw new Error(`LLM service ${diagRes.status}`)
      const d = await diagRes.json()
      setDiagnosis(d.result)
    } catch (e) {
      if (e.name === 'AbortError') setDiagnosis('Analysis stopped by user.')
      else setDiagnosis(`⚠ ${e.message}\n\nEnsure both services are running (ports 8000 and 8001).`)
    } finally {
      setDiagLoading(false)
      abortRef.current = null
    }
  }

  const totalFiles = labFiles.length + dischargeFiles.length + imagingFiles.length
  const anyExtracting = [...labFiles, ...dischargeFiles, ...imagingFiles].some(f => f.loading)
  const hasInput = chiefComplaint.trim().length > 0 ||
    [...labFiles, ...dischargeFiles, ...imagingFiles].some(f => f.text)

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-bg">

      {/* Header */}
      <div className="px-5 py-3 border-b border-border bg-panel shrink-0 flex items-center justify-between">
        <div>
          <div className="text-[14px] font-semibold">Diagnostic Tool</div>
          <div className="font-mono text-[10px] text-muted mt-[1px]">
            Independent workspace · not linked to patient records
            {totalFiles > 0 && (
              <span className="ml-2 text-accent2">
                · {totalFiles} file{totalFiles !== 1 ? 's' : ''} uploaded
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={runDiagnostic}
            disabled={!hasInput || diagLoading || anyExtracting}
            className="px-[18px] py-[7px] rounded-[7px] text-[12px] font-medium bg-accent
              text-white border-none transition-all
              enabled:cursor-pointer enabled:hover:bg-blue-700
              disabled:opacity-30 disabled:cursor-not-allowed">
            {anyExtracting ? '⟳ Extracting...' : '▶ Run Diagnostic'}
          </button>
          <button
            onClick={stopDiagnostic}
            disabled={!diagLoading}
            className="px-[14px] py-[7px] rounded-[7px] text-[12px] font-medium border transition-all
              enabled:cursor-pointer enabled:border-danger/60 enabled:text-danger enabled:hover:bg-danger/10
              disabled:opacity-20 disabled:cursor-not-allowed disabled:border-border disabled:text-muted">
            ■ Stop
          </button>
        </div>
      </div>

      {/* Grid */}
      <div
        ref={gridRef}
        className="flex-1 min-h-0 p-[14px] relative"
      >
        {/* SVG overlay */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ zIndex: 30 }}
        >
          {lines.map(l => (
            <line
              key={l.key}
              x1={l.x1}
              y1={l.y1}
              x2={l.x2}
              y2={l.y2}
              stroke="#ef4444"
              strokeWidth="1.5"
              strokeDasharray="5,4"
              opacity="0.65"
            />
          ))}
        </svg>
        {/* MAIN GRID */}
        <div
          className="w-full h-full grid gap-[12px]"
          style={{
            gridTemplateColumns: '320px 1fr 320px',
            gridTemplateRows: '1fr 1fr',
          }}
        >

          {/* TOP LEFT */}
          <div style={{ gridColumn: 1, gridRow: 1, minHeight: 0 }}>
            <ChiefComplaintBox
              value={chiefComplaint}
              onChange={setChiefComplaint}
            />
          </div>

          {/* TOP RIGHT */}
          <div style={{ gridColumn: 3, gridRow: 1, minHeight: 0 }}>
            <UploadBox
              title="Laboratory Results"
              icon="🧪"
              description="CBC, chemistry, urinalysis"
              multiple
              files={labFiles}
              onAdd={handleAdd(setLabFiles, 'lab_text')}
              onRemove={handleRemove(setLabFiles)}
              side="right"
              flagged={labFlagged}
              onChipMount={onChipMount}
            />
          </div>

          {/* BOTTOM LEFT */}
          <div style={{ gridColumn: 1, gridRow: 2, minHeight: 0 }}>
            <UploadBox
              title="Discharge Summary"
              icon="📋"
              description="From referring or previous hospital"
              multiple
              files={dischargeFiles}
              onAdd={handleAdd(setDischargeFiles, 'discharge_text')}
              onRemove={handleRemove(setDischargeFiles)}
              side="left"
              flagged={dischFlagged}
              onChipMount={onChipMount}
            />
          </div>

          {/* BOTTOM RIGHT */}
          <div style={{ gridColumn: 3, gridRow: 2, minHeight: 0 }}>
            <UploadBox
              title="Imaging & Radiology"
              icon="🔬"
              description="X-ray, CT, MRI, ECG reports"
              multiple
              files={imagingFiles}
              onAdd={handleAdd(setImagingFiles, 'imaging_text')}
              onRemove={handleRemove(setImagingFiles)}
              side="right"
              flagged={[]}
              onChipMount={onChipMount}
            />
          </div>

          {/* CENTER PANEL */}
          <div
            ref={centerRef}
            style={{
              gridColumn: 2,
              gridRow: '1 / 3',
              minHeight: 0,
            }}
          >
            <DiagnosisPanel
              result={diagnosis}
              loading={diagLoading}
              onStop={stopDiagnostic}
            />
          </div>
        </div>
      </div>
    </div>

  )
}