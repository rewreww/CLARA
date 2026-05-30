import { useEffect, useState } from 'react'
import { useGuidelines } from '../hooks/useGuidelines'

function ChunkCard({ chunk, onPreview, isPreviewActive }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className={`bg-[#060e1e] rounded-[10px] p-[12px_14px] border transition-all
      ${isPreviewActive ? 'border-accent/60' : 'border-border'}`}>
      <div className="flex items-start justify-between gap-2 mb-[6px]">
        <div className="flex items-center gap-[6px] flex-wrap">
          <span className="font-mono text-[10px] font-semibold text-[#dde4f0]">
            {chunk.source.replace(/_/g, ' ')}
          </span>
          {chunk.page && (
            <span className="font-mono text-[9px] text-muted">· p.{chunk.page}</span>
          )}
          {chunk.is_philippine && (
            <span className="text-[8px] px-[5px] py-[1px] rounded bg-accent/15 text-accent font-mono uppercase">
              Philippine
            </span>
          )}
          {chunk.is_recommendation && (
            <span className="text-[8px] px-[5px] py-[1px] rounded bg-[#10b981]/15
              text-[#10b981] font-mono uppercase">
              Recommendation
            </span>
          )}
          <span className="text-[9px] text-muted font-mono">{chunk.relevance}% match</span>
        </div>
        {chunk.page && (
          <button
            onClick={() => onPreview(chunk)}
            className={`shrink-0 font-mono text-[9px] px-[7px] py-[3px] rounded
              border transition-colors ${isPreviewActive
                ? 'border-accent text-accent bg-accent/10'
                : 'border-border text-muted hover:border-accent hover:text-accent'}`}>
            📄 p.{chunk.page}
          </button>
        )}
      </div>
      {chunk.section_heading && (
        <div className="font-mono text-[9px] uppercase tracking-[0.08em] text-accent2 mb-[5px]">
          {chunk.section_heading}
        </div>
      )}
      <div className="text-[11px] text-[#b0bfcc] leading-[1.6]">
        {expanded ? chunk.text : chunk.text.slice(0, 220) + (chunk.text.length > 220 ? '…' : '')}
      </div>
      {chunk.text.length > 220 && (
        <button onClick={() => setExpanded(e => !e)}
          className="font-mono text-[9px] text-accent mt-[4px] hover:underline">
          {expanded ? 'Show less' : 'Read more'}
        </button>
      )}
    </div>
  )
}

function CrossCheckSection({ crossCheck }) {
  const sections = [
    { key: 'consistent', label: 'Consistent',     color: '#10b981', icon: '✓' },
    { key: 'gaps',       label: 'Gaps',            color: '#ef4444', icon: '✗' },
    { key: 'concerns',   label: 'Concerns',        color: '#f59e0b', icon: '⚠' },
  ]
  const hasAny = sections.some(s => crossCheck[s.key]?.length > 0)
  if (!hasAny) return null

  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-accent mb-[10px]">
        ● Medication Cross-Check
      </div>
      <div className="space-y-[8px]">
        {sections.map(({ key, label, color, icon }) => {
          const items = crossCheck[key] || []
          if (!items.length) return null
          return (
            <div key={key} className="bg-[#060e1e] rounded-[10px] p-[10px_14px] border"
              style={{ borderColor: `${color}25` }}>
              <div className="font-mono text-[9px] uppercase tracking-[0.1em] mb-[6px]"
                style={{ color }}>
                {icon} {label} ({items.length})
              </div>
              <ul className="space-y-[4px]">
                {items.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-[11px] text-[#dde4f0]">
                    <span style={{ color }} className="shrink-0 mt-[1px]">{icon}</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function GuidelinesModal({ patient, onClose }) {
  const { data, loading, error, check, query, querying, queryResult } = useGuidelines()
  const [previewChunk, setPreviewChunk] = useState(null)
  const [question,     setQuestion]     = useState('')

  useEffect(() => { check(patient.id) }, [patient.id])

  function handlePreview(chunk) {
    setPreviewChunk(prev => (prev?.source === chunk.source && prev?.page === chunk.page) ? null : chunk)
  }

  function handleQuery(e) {
    e.preventDefault()
    if (!question.trim()) return
    query(question.trim(), data?.diagnosis_category)
  }

  const chunks = queryResult?.chunks?.length ? queryResult.chunks : (data?.guideline_chunks || [])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.65)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="bg-[#0a1628] border border-border rounded-[14px] w-full
          flex flex-col overflow-hidden"
        style={{ maxWidth: 740, maxHeight: '90vh' }}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex items-start justify-between shrink-0">
          <div>
            <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-accent mb-[4px]">
              📋 CPG Guidelines Check
            </div>
            <div className="text-[15px] font-semibold text-[#dde4f0]">{patient.name}</div>
            <div className="font-mono text-[10px] text-muted mt-[2px]">{patient.id}</div>
          </div>
          <button onClick={onClose}
            className="font-mono text-[16px] text-muted hover:text-[#dde4f0] transition-colors leading-none mt-[2px]">
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 p-5 space-y-5">

          {loading && (
            <div className="flex items-center gap-3 py-10 justify-center text-muted font-mono text-[12px]">
              <span className="animate-spin-slow inline-block text-[20px]">⟳</span>
              Retrieving guidelines for this patient…
            </div>
          )}

          {error && !loading && (
            <div className="px-4 py-3 bg-danger/5 border border-danger/20
              rounded-[8px] text-[12px] text-danger font-mono">
              ✗ {error}
              <div className="text-[10px] text-muted mt-1">
                Ensure the Python service (port 8000) is running and ingest.py has been run.
              </div>
            </div>
          )}

          {data && !loading && (
            <>
              {/* Diagnosis */}
              <div className="bg-[#060e1e] border border-border rounded-[10px] px-4 py-3">
                <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted mb-[5px]">
                  Detected Diagnosis
                </div>
                <div className="text-[13px] text-[#dde4f0] leading-[1.5] mb-[6px]">
                  {data.diagnosis_text || 'No final diagnosis extracted from discharge summary'}
                </div>
                <div className="flex items-center gap-[6px] flex-wrap">
                  <span className="font-mono text-[9px] px-[7px] py-[2px] rounded
                    bg-accent/15 text-accent border border-accent/30">
                    {data.diagnosis_category_label}
                  </span>
                  {data.has_philippine_guidelines && (
                    <span className="font-mono text-[9px] px-[7px] py-[2px] rounded
                      bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/25">
                      ✓ Philippine CPG found
                    </span>
                  )}
                  {!data.rag_available && (
                    <span className="font-mono text-[9px] px-[7px] py-[2px] rounded
                      bg-[#f59e0b]/10 text-[#f59e0b] border border-[#f59e0b]/25">
                      ⚠ RAG not available — run ingest.py
                    </span>
                  )}
                </div>
              </div>

              {/* Medications found */}
              {data.medications_found?.length > 0 && (
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted mb-[8px]">
                    Medications Identified
                  </div>
                  <div className="flex flex-wrap gap-[5px]">
                    {data.medications_found.map(m => (
                      <span key={m} className="font-mono text-[10px] px-[8px] py-[3px]
                        rounded bg-[#0d1526] border border-border text-[#dde4f0] capitalize">
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Cross-check */}
              <CrossCheckSection crossCheck={data.cross_check} />

              {/* Guideline chunks */}
              {chunks.length > 0 && (
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-accent mb-[10px]">
                    ● Guideline Evidence
                    {queryResult?.chunks?.length > 0 && (
                      <span className="ml-2 text-muted normal-case">
                        — results for "{queryResult.question}"
                      </span>
                    )}
                  </div>
                  <div className="space-y-[8px]">
                    {chunks.map((chunk, i) => (
                      <ChunkCard
                        key={`${chunk.source}-${chunk.page}-${i}`}
                        chunk={chunk}
                        onPreview={handlePreview}
                        isPreviewActive={
                          previewChunk?.source === chunk.source &&
                          previewChunk?.page   === chunk.page
                        }
                      />
                    ))}
                  </div>
                </div>
              )}

              {chunks.length === 0 && data.rag_available && (
                <div className="text-center py-6 text-muted font-mono text-[11px]">
                  No relevant guideline sections found for this diagnosis.
                  <br />Try searching manually below.
                </div>
              )}

              {/* PDF Preview */}
              {previewChunk && (
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-accent mb-[8px]">
                    ● PDF Preview — {previewChunk.source.replace(/_/g, ' ')} p.{previewChunk.page}
                  </div>
                  <div className="bg-[#060e1e] border border-accent/30 rounded-[10px] overflow-hidden">
                    <img
                      src={`/api/labs/guidelines-preview?source=${encodeURIComponent(previewChunk.source)}&page=${previewChunk.page}`}
                      alt={`${previewChunk.source} page ${previewChunk.page}`}
                      className="w-full"
                      onError={e => { e.target.style.display = 'none' }}
                    />
                  </div>
                </div>
              )}

              {/* Follow-up search */}
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted mb-[8px]">
                  Search Guidelines
                </div>
                <form onSubmit={handleQuery} className="flex gap-[8px]">
                  <input
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                    placeholder="e.g. beta-blocker dose in elderly patients…"
                    className="flex-1 bg-[#060e1e] border border-border rounded-[7px]
                      px-3 py-[7px] font-mono text-[11px] text-[#dde4f0]
                      placeholder:text-muted focus:outline-none focus:border-accent"
                  />
                  <button
                    type="submit"
                    disabled={querying || !question.trim()}
                    className="px-4 py-[7px] rounded-[7px] font-mono text-[11px]
                      bg-accent text-white border-none cursor-pointer
                      disabled:opacity-40 disabled:cursor-not-allowed
                      hover:bg-blue-700 transition-colors shrink-0">
                    {querying ? '⟳' : 'Search'}
                  </button>
                </form>
              </div>

              {/* Citation list */}
              <div className="bg-[#060e1e] border border-border rounded-[10px] px-4 py-3">
                <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted mb-[6px]">
                  Guideline Sources
                </div>
                {[
                  '2022 AHA/ACC/HFSA Guideline for the Management of Heart Failure',
                  '2023 ESC Guidelines for the Diagnosis and Treatment of Acute and Chronic Heart Failure',
                  'Philippine Society of Cardiology (PSC) Clinical Practice Guidelines',
                ].map(src => (
                  <div key={src} className="flex items-start gap-[6px] text-[10px] text-[#6b7f99]">
                    <span className="text-accent mt-[1px] shrink-0">·</span>{src}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Disclaimer footer */}
        <div className="shrink-0 border-t border-border px-5 py-[10px]
          flex items-center gap-[8px] bg-[#060e1e]">
          <span className="text-[13px]" style={{ color: '#f59e0b' }}>⚠</span>
          <p className="font-mono text-[9px] text-muted leading-[1.5]">
            For clinical reference only. This tool does not replace physician judgment.
            All recommendations must be reviewed by a licensed clinician before any prescribing decision.
          </p>
        </div>
      </div>
    </div>
  )
}