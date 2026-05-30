import { useEffect } from 'react'
import { useGdmtCheck } from '../hooks/useGdmtCheck'

const STATUS_COLOR = {
  present:         '#10b981',
  missing:         '#ef4444',
  contraindicated: '#f59e0b',
  suboptimal:      '#f59e0b',
}

const STATUS_ICON = {
  present:         '✓',
  missing:         '✗',
  contraindicated: '⊘',
  suboptimal:      '⚠',
}

const STATUS_LABEL = {
  present:         'Present',
  missing:         'Missing',
  contraindicated: 'Contraindicated',
  suboptimal:      'Suboptimal',
}

function PillarCard({ pillar, status, drug_found, subtype, note }) {
  const color = STATUS_COLOR[status] || '#6b7f99'
  const icon  = STATUS_ICON[status]  || '?'
  return (
    <div
      className="bg-[#060e1e] rounded-[10px] p-[12px_14px] flex flex-col gap-[6px]"
      style={{ border: `1px solid ${color}30` }}
    >
      <div className="font-mono text-[9px] tracking-[0.1em] uppercase text-muted">
        {pillar}
      </div>
      <div className="flex items-center gap-[7px]">
        <span className="text-[18px] leading-none" style={{ color }}>{icon}</span>
        <span className="font-mono text-[12px] font-semibold" style={{ color }}>
          {STATUS_LABEL[status]}
        </span>
      </div>
      {drug_found && (
        <div className="font-mono text-[11px] text-[#dde4f0] capitalize">
          {drug_found}
          {subtype && (
            <span className="ml-[5px] text-[9px] text-muted uppercase">({subtype})</span>
          )}
        </div>
      )}
      {note && (
        <div className="text-[10px] text-muted leading-[1.5]">{note}</div>
      )}
    </div>
  )
}

function LabBadge({ label, value }) {
  if (value == null) return null
  return (
    <span className="font-mono text-[10px] bg-[#0d1526] border border-border
      rounded-[5px] px-[7px] py-[2px] text-[#dde4f0]">
      {label}: <span className="text-accent2">{value}</span>
    </span>
  )
}

export default function GdmtCheckModal({ patient, onClose }) {
  const { data, loading, error, check } = useGdmtCheck()

  useEffect(() => {
    check(patient.id)
  }, [patient.id])

  const presentCount = data?.pillars?.filter(p => p.status === 'present').length ?? 0
  const totalPillars = 4

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.65)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="bg-[#0a1628] border border-border rounded-[14px] w-full
          flex flex-col overflow-hidden"
        style={{ maxWidth: 700, maxHeight: '88vh' }}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex items-start justify-between shrink-0">
          <div>
            <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-accent mb-[4px]">
              ✓ GDMT 4-Pillar Check
            </div>
            <div className="text-[15px] font-semibold text-[#dde4f0]">{patient.name}</div>
            <div className="font-mono text-[10px] text-muted mt-[2px]">{patient.id}</div>
          </div>
          <button
            onClick={onClose}
            className="font-mono text-[16px] text-muted hover:text-[#dde4f0]
              transition-colors mt-[2px] leading-none"
          >
            ✕
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1 p-5 space-y-5">

          {loading && (
            <div className="flex items-center gap-3 py-10 justify-center text-muted font-mono text-[12px]">
              <span className="animate-spin-slow inline-block text-[20px]">⟳</span>
              Analyzing medications and labs…
            </div>
          )}

          {error && !loading && (
            <div className="px-4 py-3 bg-danger/5 border border-danger/20
              rounded-[8px] text-[12px] text-danger font-mono">
              ✗ {error}
              <div className="text-[10px] text-muted mt-1">
                Ensure the Python service is running on port 8000.
              </div>
            </div>
          )}

          {data && !loading && (
            <>
              {/* HFrEF Detection */}
              <div className={`rounded-[10px] px-4 py-3 border ${
                data.hfref_detected
                  ? 'bg-[#10b981]/5 border-[#10b981]/25'
                  : 'bg-[#f59e0b]/5 border-[#f59e0b]/25'
              }`}>
                <div className="font-mono text-[10px] uppercase tracking-[0.1em] mb-[4px]"
                  style={{ color: data.hfref_detected ? '#10b981' : '#f59e0b' }}>
                  {data.hfref_detected ? '✓ HFrEF Detected' : '⚠ HFrEF Not Clearly Detected'}
                </div>
                {data.diagnosis_text ? (
                  <div className="text-[12px] text-[#dde4f0] leading-[1.5]">
                    {data.diagnosis_text}
                  </div>
                ) : (
                  <div className="text-[11px] text-muted">
                    No final diagnosis extracted from discharge summary.
                  </div>
                )}
              </div>

              {/* GDMT Score */}
              <div className="flex items-center gap-3">
                <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted">
                  GDMT Score
                </div>
                <div className="flex gap-[4px]">
                  {[0,1,2,3].map(i => (
                    <div key={i} className="w-[28px] h-[5px] rounded-full"
                      style={{ background: i < presentCount ? '#10b981' : '#1a2d4e' }} />
                  ))}
                </div>
                <div className="font-mono text-[11px] font-semibold text-[#dde4f0]">
                  {presentCount} / {totalPillars} pillars
                </div>
              </div>

              {/* 4 Pillars */}
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-accent mb-[10px]">
                  ● Pillar Status
                </div>
                <div className="grid grid-cols-2 gap-[8px]">
                  {data.pillars.map(p => <PillarCard key={p.pillar} {...p} />)}
                </div>
              </div>

              {/* Warnings */}
              {data.warnings?.length > 0 && (
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.1em] mb-[8px]"
                    style={{ color: '#f59e0b' }}>
                    ⚠ Safety Flags
                  </div>
                  <div className="space-y-[6px]">
                    {data.warnings.map((w, i) => (
                      <div key={i} className="text-[12px] leading-[1.55] text-[#dde4f0]
                        bg-[#f59e0b]/5 border border-[#f59e0b]/20 rounded-[8px] px-3 py-2">
                        {w}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Gaps */}
              {data.gaps?.length > 0 && (
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.1em]
                    text-[#ef4444] mb-[8px]">
                    ✗ Gaps Identified
                  </div>
                  <ul className="space-y-[5px]">
                    {data.gaps.map((g, i) => (
                      <li key={i} className="flex items-start gap-2 text-[12px] text-[#dde4f0]">
                        <span className="text-[#ef4444] mt-[2px] shrink-0">✗</span>
                        {g}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Recommendations */}
              {data.recommendations?.length > 0 && (
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.1em]
                    text-accent mb-[8px]">
                    ● Next-Visit Recommendations
                  </div>
                  <ol className="space-y-[8px]">
                    {data.recommendations.map((r, i) => (
                      <li key={i}
                        className="bg-[#0d1526] border border-border rounded-[8px]
                          px-3 py-[10px] text-[12px] text-[#dde4f0] leading-[1.6]">
                        <span className="font-mono text-[10px] text-accent mr-[8px]">
                          {i + 1}.
                        </span>
                        {r}
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {/* Labs Used */}
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted mb-[8px]">
                  Lab Values Used in Analysis
                </div>
                <div className="flex flex-wrap gap-[6px]">
                  <LabBadge label="K⁺" value={data.labs_used?.potassium != null
                    ? `${data.labs_used.potassium} mEq/L` : null} />
                  <LabBadge label="Creatinine" value={data.labs_used?.creatinine != null
                    ? `${data.labs_used.creatinine} mg/dL` : null} />
                  <LabBadge label="eGFR" value={data.labs_used?.egfr != null
                    ? `${data.labs_used.egfr} mL/min` : null} />
                  <LabBadge label="BP" value={data.labs_used?.bp_systolic != null
                    ? `${Math.round(data.labs_used.bp_systolic)} mmHg` : null} />
                  <LabBadge label="HR" value={data.labs_used?.hr != null
                    ? `${Math.round(data.labs_used.hr)} bpm` : null} />
                  {Object.values(data.labs_used).every(v => v == null) && (
                    <span className="text-[11px] text-muted">
                      No lab values found — contraindication check skipped
                    </span>
                  )}
                </div>
              </div>

              {/* ── Citation Banner ───────────────────────────────────────── */}
              <div className="bg-[#060e1e] border border-border rounded-[10px] px-4 py-3">
                <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted mb-[6px]">
                  Guideline Sources
                </div>
                <div className="space-y-[4px]">
                  {[
                    '2022 AHA/ACC/HFSA Guideline for the Management of Heart Failure',
                    '2023 ESC Guidelines for the Diagnosis and Treatment of Acute and Chronic Heart Failure',
                    'Philippine Society of Cardiology (PSC) Clinical Practice Guidelines',
                  ].map(src => (
                    <div key={src} className="flex items-start gap-[6px] text-[10px] text-[#6b7f99]">
                      <span className="text-accent mt-[1px] shrink-0">·</span>
                      {src}
                    </div>
                  ))}
                </div>
              </div>

            </>
          )}
        </div>

        {/* ── Sticky Disclaimer Footer ──────────────────────────────────── */}
        <div className="shrink-0 border-t border-border px-5 py-[10px]
          flex items-center gap-[8px] bg-[#060e1e]">
          <span className="text-[13px]" style={{ color: '#f59e0b' }}>⚠</span>
          <p className="font-mono text-[9px] text-muted leading-[1.5]">
            For clinical reference only. This tool does not replace physician judgment.
            All recommendations must be reviewed and approved by a licensed clinician
            before any prescribing decision is made.
          </p>
        </div>

      </div>
    </div>
  )
}