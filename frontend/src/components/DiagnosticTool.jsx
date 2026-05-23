import { useState, useRef, useCallback } from 'react'

const LABS_URL = '/api/labs'

async function extractPdf(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${LABS_URL}/extract-pdf`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(`Server error ${res.status}`)
  return res.json()
}

// ── PDF upload box ────────────────────────────────────────────────────────────
function UploadBox({ title, icon, description, multiple, files, onAdd, onRemove }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    onAdd(e.dataTransfer.files)
  }

  return (
    <div className="bg-card border border-border rounded-[12px] flex flex-col overflow-hidden">

      <div className="px-[14px] py-[10px] border-b border-border shrink-0 flex items-center gap-[8px]">
        <span className="text-[15px]">{icon}</span>
        <div>
          <div className="font-mono text-[11px] font-semibold text-[#dde4f0]">{title}</div>
          <div className="font-mono text-[9px] text-muted">{description}</div>
        </div>
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onClick={() => inputRef.current?.click()}
        className={`mx-[10px] mt-[10px] border border-dashed rounded-[8px] py-[10px]
          flex items-center justify-center cursor-pointer transition-all shrink-0
          ${dragging
            ? 'border-accent bg-accent/5'
            : 'border-border hover:border-accent/40 hover:bg-accent/[0.02]'}`}
      >
        <input ref={inputRef} type="file" accept=".pdf"
          multiple={multiple} className="hidden"
          onChange={e => { onAdd(e.target.files); e.target.value = '' }} />
        <span className="font-mono text-[10px] text-muted select-none">
          {dragging ? 'Drop here' : '+ Drop PDF or click to browse'}
        </span>
      </div>

      {/* File list */}
      <div className="flex-1 overflow-y-auto px-[10px] py-[8px] min-h-0">
        {files.length === 0 ? (
          <div className="font-mono text-[10px] text-border text-center py-2">
            No files added
          </div>
        ) : files.map((f, i) => (
          <div key={i} className="flex items-center justify-between py-[5px]
            border-b border-border/40 last:border-0">
            <div className="flex items-center gap-[8px] min-w-0">
              <div className={`w-[6px] h-[6px] rounded-full shrink-0
                ${f.loading ? 'bg-warning animate-pulse' : f.error ? 'bg-danger' : 'bg-success'}`} />
              <div className="min-w-0">
                <div className="font-mono text-[10px] truncate text-[#dde4f0]">{f.file.name}</div>
                <div className="font-mono text-[9px] text-muted">
                  {f.loading
                    ? 'Extracting text...'
                    : f.error
                      ? 'Extraction failed'
                      : `${f.pages}p · ${f.charCount.toLocaleString()} chars`}
                </div>
              </div>
            </div>
            <button onClick={() => onRemove(i)}
              className="font-mono text-[10px] text-muted hover:text-danger
                transition-colors bg-transparent border-none cursor-pointer ml-2 shrink-0">
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Chief complaint box ───────────────────────────────────────────────────────
function ChiefComplaintBox({ value, onChange }) {
  return (
    <div className="bg-card border border-border rounded-[12px] flex flex-col overflow-hidden">
      <div className="px-[14px] py-[10px] border-b border-border shrink-0 flex items-center gap-[8px]">
        <span className="text-[15px]">🩺</span>
        <div>
          <div className="font-mono text-[11px] font-semibold text-[#dde4f0]">Chief Complaint</div>
          <div className="font-mono text-[9px] text-muted">Describe the patient's main problem</div>
        </div>
      </div>
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={
          'e.g. 58M with 3-day history of chest pain, worse on exertion.\n' +
          'Associated dyspnea, diaphoresis. No fever. HTN x10y.'
        }
        className="flex-1 bg-transparent border-none outline-none resize-none
          p-[12px] text-[12px] text-[#dde4f0] placeholder:text-border
          leading-[1.65] font-sans"
      />
    </div>
  )
}

// ── Center diagnosis panel ────────────────────────────────────────────────────
function DiagnosisPanel({ result, loading, hasInput }) {
  if (loading) {
    return (
      <div className="bg-[#060b14] border border-accent/20 rounded-[12px] h-full
        flex flex-col items-center justify-center gap-4">
        <div className="w-9 h-9 border-2 border-accent border-t-transparent
          rounded-full animate-spin-slow" />
        <div className="font-mono text-[11px] text-muted">Analyzing clinical data...</div>
      </div>
    )
  }

  if (result) {
    return (
      <div className="bg-[#060b14] border border-accent/30 rounded-[12px] h-full
        flex flex-col overflow-hidden">
        <div className="px-[16px] py-[10px] border-b border-border shrink-0 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-success" />
          <span className="font-mono text-[10px] text-accent2 uppercase tracking-[0.1em]">
            Diagnostic Result
          </span>
        </div>
        <div className="flex-1 overflow-y-auto p-[16px] text-[12px]
          leading-[1.75] text-[#dde4f0] whitespace-pre-wrap font-sans">
          {result}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-[#060b14] border border-border rounded-[12px] h-full
      flex flex-col items-center justify-center gap-3 px-6 text-center">
      <div className="text-[44px] opacity-10 select-none">⚕</div>
      <div className="font-mono text-[11px] text-muted leading-[1.7]">
        {hasInput
          ? 'Ready — click Run Diagnostic'
          : 'Add a chief complaint or upload PDFs\nto begin diagnostic analysis'}
      </div>
      {hasInput && (
        <div className="font-mono text-[9px] text-border mt-1">
          Extracted text will be analyzed by AI
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function DiagnosticTool() {
  const [chiefComplaint,  setChiefComplaint]  = useState('')
  const [labFiles,        setLabFiles]        = useState([])
  const [dischargeFiles,  setDischargeFiles]  = useState([])
  const [imagingFiles,    setImagingFiles]    = useState([])
  const [diagnosis,       setDiagnosis]       = useState(null)
  const [diagLoading,     setDiagLoading]     = useState(false)

  const hasInput = chiefComplaint.trim().length > 0 ||
    [...labFiles, ...dischargeFiles, ...imagingFiles].some(f => f.text)

  const handleAdd = useCallback((setter) => async (incoming) => {
    const pdfs = Array.from(incoming).filter(f => f.type === 'application/pdf')
    if (!pdfs.length) return

    const pending = pdfs.map(file => ({
      file, loading: true, error: null, text: '', pages: 0, charCount: 0,
    }))
    setter(prev => [...prev, ...pending])

    for (const file of pdfs) {
      try {
        const res = await extractPdf(file)
        setter(prev => prev.map(e =>
          e.file === file && e.loading
            ? { file, loading: false, error: null, text: res.text, pages: res.pages, charCount: res.char_count }
            : e
        ))
      } catch (err) {
        setter(prev => prev.map(e =>
          e.file === file && e.loading
            ? { file, loading: false, error: err.message, text: '', pages: 0, charCount: 0 }
            : e
        ))
      }
    }
  }, [])

  const handleRemove = (setter) => (i) =>
    setter(prev => prev.filter((_, idx) => idx !== i))

  const runDiagnostic = async () => {
    setDiagLoading(true)
    setDiagnosis(null)
    // Wire to ML/LLM in next step
    setDiagLoading(false)
  }

  const totalFiles = labFiles.length + dischargeFiles.length + imagingFiles.length
  const anyLoading = [...labFiles, ...dischargeFiles, ...imagingFiles].some(f => f.loading)

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-bg">

      {/* Header */}
      <div className="px-5 py-3 border-b border-border bg-panel shrink-0
        flex items-center justify-between">
        <div>
          <div className="text-[14px] font-semibold">Diagnostic Tool</div>
          <div className="font-mono text-[10px] text-muted mt-[1px]">
            Independent workspace · not linked to patient records
            {totalFiles > 0 && (
              <span className="ml-2 text-accent2">
                · {totalFiles} file{totalFiles > 1 ? 's' : ''} uploaded
              </span>
            )}
          </div>
        </div>
        <button
          onClick={runDiagnostic}
          disabled={!hasInput || diagLoading || anyLoading}
          className="px-[18px] py-[7px] rounded-[7px] text-[12px] font-medium bg-accent
            text-white border-none transition-all
            enabled:cursor-pointer enabled:hover:bg-blue-700
            disabled:opacity-30 disabled:cursor-not-allowed">
          {anyLoading ? '⟳ Extracting...' : '▶ Run Diagnostic'}
        </button>
      </div>

      {/* 3-column grid */}
      <div className="flex-1 min-h-0 p-[14px]" style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1.4fr 1fr',
        gridTemplateRows: '1fr 1fr',
        gap: '12px',
      }}>

        {/* Top-left: Chief Complaint */}
        <ChiefComplaintBox value={chiefComplaint} onChange={setChiefComplaint} />

        {/* Center: Diagnosis (spans both rows) */}
        <div style={{ gridRow: '1 / 3' }}>
          <DiagnosisPanel result={diagnosis} loading={diagLoading} hasInput={hasInput} />
        </div>

        {/* Top-right: Lab Results */}
        <UploadBox
          title="Laboratory Results"
          icon="🧪"
          description="CBC, chemistry, urinalysis PDFs"
          multiple
          files={labFiles}
          onAdd={handleAdd(setLabFiles)}
          onRemove={handleRemove(setLabFiles)}
        />

        {/* Bottom-left: Discharge Summary */}
        <UploadBox
          title="Discharge Summary"
          icon="📋"
          description="From referring or previous hospital"
          multiple
          files={dischargeFiles}
          onAdd={handleAdd(setDischargeFiles)}
          onRemove={handleRemove(setDischargeFiles)}
        />

        {/* Bottom-right: Imaging & Radiology */}
        <UploadBox
          title="Imaging & Radiology"
          icon="🔬"
          description="X-ray, CT, MRI, ECG reports"
          multiple
          files={imagingFiles}
          onAdd={handleAdd(setImagingFiles)}
          onRemove={handleRemove(setImagingFiles)}
        />

      </div>
    </div>
  )
}