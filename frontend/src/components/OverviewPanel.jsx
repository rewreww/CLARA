import { useState, useEffect } from 'react'
import { useVitals }           from '../hooks/useVitals'
import GdmtCheckModal  from './GdmtCheckModal'
import GuidelinesModal from './GuidelinesModal'

const STATUS_HEX = { normal: '#10b981', warning: '#f59e0b', critical: '#ef4444' }

const VITAL_CONFIG = [
  { key: 'bp',   label: 'Blood Pressure', unit: 'mmHg', refLow: 90,   refHigh: 120  },
  { key: 'hr',   label: 'Heart Rate',     unit: 'bpm',  refLow: 60,   refHigh: 100  },
  { key: 'rr',   label: 'Respiratory',    unit: '/min', refLow: 12,   refHigh: 20   },
  { key: 'temp', label: 'Temperature',    unit: '°C',   refLow: 36.1, refHigh: 37.2 },
  { key: 'o2',   label: 'O₂ Saturation',  unit: '%',    refLow: 95,   refHigh: 100  },
]

function getStatus(value, refLow, refHigh) {
  if (value == null) return 'normal'
  if (refLow  != null && value < refLow)  return value < refLow  * 0.9 ? 'critical' : 'warning'
  if (refHigh != null && value > refHigh) return value > refHigh * 1.1 ? 'critical' : 'warning'
  return 'normal'
}

function getStatusLabel(value, refLow, refHigh) {
  if (value == null) return 'No data'
  if (refLow  != null && value < refLow)  return 'Below normal'
  if (refHigh != null && value > refHigh) return 'Above normal'
  return 'Normal'
}

// ── Diff utilities ────────────────────────────────────────────────────────────

function medKey(m) {
  return (m || '').trim().toUpperCase().split(/\s+/).slice(0, 2).join(' ')
}

function computeDiff(current, prev) {
  if (!current?.found || !prev?.found) return null

  // Lab diff from discharge summary
  const prevLabMap = {}
  for (const lab of (prev.labs || [])) {
    if (lab.test) prevLabMap[lab.test.toLowerCase().trim()] = lab
  }
  const labDiffs = []
  for (const lab of (current.labs || [])) {
    if (!lab.test) continue
    const prevLab = prevLabMap[lab.test.toLowerCase().trim()]
    if (!prevLab) continue
    const cur = parseFloat(lab.val), prv = parseFloat(prevLab.val)
    if (!isNaN(cur) && !isNaN(prv) && Math.abs(cur - prv) > 0.001) {
      labDiffs.push({
        test:      lab.test,
        curVal:    lab.val,
        prevVal:   prevLab.val,
        unit:      lab.unit || prevLab.unit || '',
        delta:     cur - prv,
        direction: cur > prv ? 'up' : 'down',
        flag:      lab.flag,
      })
    }
  }

  // Diagnosis diff
  const curDx  = (current.final_dx || '').trim().toLowerCase()
  const prevDx = (prev.final_dx    || '').trim().toLowerCase()
  const dxChanged = curDx && prevDx && curDx !== prevDx
    ? { from: prev.final_dx, to: current.final_dx } : null

  // Med diff — medications is already a string[]
  const curMeds  = Array.isArray(current.medications) ? current.medications : []
  const prevMeds = Array.isArray(prev.medications)    ? prev.medications    : []
  const curKeys  = new Set(curMeds.map(medKey))
  const prevKeys = new Set(prevMeds.map(medKey))

  return {
    labDiffs,
    dxChanged,
    medDiffs: {
      added:   curMeds.filter(m => !prevKeys.has(medKey(m))),
      removed: prevMeds.filter(m => !curKeys.has(medKey(m))),
    },
  }
}

// ── PatientRecordsTable ───────────────────────────────────────────────────────

function PatientRecordsTable({ data, abnormalLabs, loading, diff }) {
  if (loading) {
    return (
      <div className="border border-border rounded-[10px] bg-[#0d1526] p-4 mb-[20px] animate-pulse">
        <div className="h-3 w-1/2 bg-border rounded mb-2" />
        <div className="h-3 w-1/3 bg-border rounded" />
      </div>
    )
  }

  const allAbnormal = [
    ...(abnormalLabs?.chemistry  || []),
    ...(abnormalLabs?.hematology || []),
    ...(abnormalLabs?.microscopy || []),
  ]
  const finalDx    = data?.final_dx
  const meds       = Array.isArray(data?.medications) ? data.medications : []
  const instrList  = Array.isArray(data?.instructions) ? data.instructions : []
  const followup   = data?.followup || null
  const instrText  = instrList.length ? instrList.join(' · ') : null

  const addedKeys = new Set((diff?.medDiffs?.added   || []).map(medKey))

  const flagColor = f => f === 'high' ? '#ef4444' : '#f59e0b'

  const labDiffMap = {}
  for (const d of (diff?.labDiffs || [])) {
    if (d.test) labDiffMap[d.test.toLowerCase().trim()] = d
  }

  return (
    <div className="border border-border rounded-[10px] overflow-hidden bg-[#0d1526] mb-[20px]"
      style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr' }}>

      {/* Headers */}
      {['Abnormal Labs', 'Final Diagnosis', 'Medications'].map((h, i) => (
        <div key={h}
          className="px-3 py-2 font-mono text-[9px] uppercase tracking-[0.1em] text-muted border-b border-border"
          style={{ borderLeft: i > 0 ? '1px solid #1a2d4e' : 'none' }}>
          {h}
        </div>
      ))}

      {/* Col 1 — Abnormal labs with delta */}
      <div className="px-3 py-3 flex flex-col gap-[6px]">
        {allAbnormal.length === 0 ? (
          <span className="text-[11px] text-muted">No flagged results</span>
        ) : allAbnormal.map((r, i) => {
          const d = labDiffMap[r.test_name?.toLowerCase().trim()]
          return (
            <div key={i} className="flex items-baseline gap-[5px] flex-wrap">
              <span className="font-mono text-[11px] text-[#d7e2f0]">{r.test_name}</span>
              <span className="font-mono text-[11px] font-semibold" style={{ color: flagColor(r.flag) }}>
                {String(r.value)}{r.unit ? ` ${r.unit}` : ''}
              </span>
              <span className="text-[9px]" style={{ color: flagColor(r.flag) }}>
                {r.flag === 'high' ? '↑' : '↓'}
              </span>
              {d && (
                <span className="text-[9px] font-mono px-[4px] py-[1px] rounded"
                  style={{
                    background: d.direction === 'up' ? '#ef444418' : '#f59e0b18',
                    color:      d.direction === 'up' ? '#ef4444'   : '#f59e0b',
                  }}>
                  {d.direction === 'up' ? '▲' : '▼'} {d.delta > 0 ? '+' : ''}{d.delta.toFixed(2)}
                </span>
              )}
            </div>
          )
        })}
      </div>

      {/* Col 2 — Final Diagnosis */}
      <div className="px-3 py-3 text-[12px] leading-[1.65] text-[#d7e2f0]"
        style={{ borderLeft: '1px solid #1a2d4e' }}>
        {finalDx ? (
          <>
            {diff?.dxChanged && (
              <span className="inline-block mb-[6px] px-[5px] py-[1px] rounded font-mono text-[9px]
                bg-[#a78bfa18] text-[#a78bfa] border border-[#a78bfa35]">
                ≠ updated
              </span>
            )}
            <div>{finalDx}</div>
            {diff?.dxChanged && (
              <div className="mt-[6px] text-[10px] text-muted line-through leading-[1.5]">
                {diff.dxChanged.from}
              </div>
            )}
          </>
        ) : (
          <span className="text-muted">Not recorded</span>
        )}
      </div>

      {/* Col 3 — Medications (two stacked cells) */}
      <div style={{ borderLeft: '1px solid #1a2d4e', display: 'flex', flexDirection: 'column' }}>
        {/* Top: bulleted med list */}
        <div className="px-3 py-3 border-b border-border flex-1">
          {meds.length === 0 && !(diff?.medDiffs?.removed?.length) ? (
            <span className="text-[11px] text-muted">No medications recorded</span>
          ) : (
            <ul className="space-y-[4px]">
              {meds.map((med, i) => {
                const isAdded = addedKeys.has(medKey(med))
                return (
                  <li key={i} className="flex gap-[6px] text-[11px] leading-[1.55]">
                    <span className="shrink-0 mt-[1px]"
                      style={{ color: isAdded ? '#10b981' : '#4a7fa5' }}>
                      {isAdded ? '+' : '·'}
                    </span>
                    <span style={{ color: isAdded ? '#10b981' : '#d7e2f0' }}>{med}</span>
                  </li>
                )
              })}
              {(diff?.medDiffs?.removed || []).map((med, i) => (
                <li key={`rem-${i}`} className="flex gap-[6px] text-[11px] leading-[1.55] opacity-50">
                  <span className="shrink-0 mt-[1px] text-[#ef4444]">−</span>
                  <span className="text-[#ef4444] line-through">{med}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        {/* Bottom: instructions + follow-up */}
        <div className="px-3 py-3">
          <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-accent2 mb-[5px]">
            Instructions
          </div>
          <div className="text-[11px] leading-[1.6] text-[#c8d5e8]">
            {instrText || <span className="text-muted">—</span>}
          </div>
          {followup && (
            <>
              <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-accent2 mt-[8px] mb-[4px]">
                Follow-Up
              </div>
              <div className="text-[11px] leading-[1.6] text-[#c8d5e8]">{followup}</div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Sparkline ─────────────────────────────────────────────────────────────────

function SparkLine({ data, color, refLow, refHigh, activeIndex, width = 80, height = 33 }) {
  if (!data?.length) return null
  if (data.length === 1) {
    return (
      <svg width={width} height={height} className="block">
        <line x1={0} y1={height / 2} x2={width} y2={height / 2}
          stroke={color} strokeWidth="1" strokeDasharray="3,3" opacity="0.35" />
        <circle cx={width / 2} cy={height / 2} r="4" fill={color} />
      </svg>
    )
  }
  const allVals = [...data]
  if (refLow  != null) allVals.push(refLow)
  if (refHigh != null) allVals.push(refHigh)
  const max = Math.max(...allVals), min = Math.min(...allVals), range = max - min || 1
  const toY = v => height - 4 - ((v - min) / range) * (height - 8)
  const toX = (i, len) => (i / (len - 1)) * (width - 8) + 4
  const pts = data.map((v, i) => `${toX(i, data.length)},${toY(v)}`).join(' ')
  const dotCoords = pts.split(' ')
  return (
    <svg width={width} height={height} className="block">
      {refLow != null && refHigh != null && (() => {
        const yHigh = toY(refHigh), yLow = toY(refLow)
        const yTop = Math.min(yHigh, yLow), yH = Math.max(Math.abs(yHigh - yLow), 1)
        return <rect x={4} y={yTop} width={width - 8} height={yH}
          fill="rgba(16,185,129,0.08)" stroke="rgba(16,185,129,0.2)" strokeWidth={0.5} />
      })()}
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      {dotCoords.map((pt, i) => {
        const [cx, cy] = pt.split(',')
        return <circle key={i} cx={cx} cy={cy}
          r={i === activeIndex ? 5 : 2} fill={color} opacity={i === activeIndex ? 1 : 0.5} />
      })}
    </svg>
  )
}

function VitalTile({ label, value, unit, statusLabel, status, sparkData, refLow, refHigh, activeIndex }) {
  const color = STATUS_HEX[status] || STATUS_HEX.normal
  return (
    <div className="bg-[#0d1526] border border-border rounded-[10px] p-[12px_14px]
      flex flex-col h-[145px] transition-all"
      onMouseEnter={e => e.currentTarget.style.borderColor = color}
      onMouseLeave={e => e.currentTarget.style.borderColor = '#1a2d4e'}>
      <div className="font-mono text-[9px] tracking-[0.1em] uppercase text-muted mb-[4px]">{label}</div>
      <div className="font-mono text-[20px] font-bold leading-none" style={{ color }}>
        {value ?? '—'}
        <span className="text-[10px] font-normal text-muted ml-[3px]">{unit}</span>
      </div>
      <div className="font-mono text-[9px] mt-[3px]" style={{ color }}>{statusLabel}</div>
      <div className="mt-auto">
        <SparkLine data={sparkData} color={color} refLow={refLow} refHigh={refHigh} activeIndex={activeIndex} />
      </div>
    </div>
  )
}

function SkeletonTile() {
  return (
    <div className="bg-[#0d1526] border border-border rounded-[10px] p-[12px_14px]
      flex flex-col h-[145px] animate-pulse">
      <div className="h-2 w-14 bg-border rounded mb-3" />
      <div className="h-5 w-20 bg-border rounded mb-2" />
      <div className="h-2 w-10 bg-border rounded" />
    </div>
  )
}

function VitalsRow({ vitals, trends, currentIndex, loading }) {
  if (loading) {
    return (
      <div className="grid grid-cols-5 gap-[10px] mb-[20px]">
        {VITAL_CONFIG.map(t => <SkeletonTile key={t.key} />)}
      </div>
    )
  }
  const total      = trends?.length ?? 0
  const safeIndex  = total > 0 ? Math.min(currentIndex, total - 1) : null
  const trendPoint = safeIndex != null ? trends[safeIndex] : null
  const isLatest   = safeIndex === total - 1
  return (
    <div className="grid grid-cols-5 gap-[10px] mb-[20px]">
      {VITAL_CONFIG.map(({ key, label, unit, refLow, refHigh }) => {
        const sparkData = total > 1
          ? trends.map(pt => pt[key]).filter(v => v != null)
          : vitals?.[key]?.numeric != null ? [vitals[key].numeric] : []
        let value, statusLabel, status
        if (isLatest && vitals?.[key]) {
          value = vitals[key].value; statusLabel = vitals[key].label; status = vitals[key].status
        } else if (trendPoint?.[key] != null) {
          value = String(trendPoint[key])
          status = getStatus(trendPoint[key], refLow, refHigh)
          statusLabel = getStatusLabel(trendPoint[key], refLow, refHigh)
        } else {
          value = null; status = 'normal'; statusLabel = '—'
        }
        return (
          <VitalTile key={key} label={label} unit={unit} value={value}
            statusLabel={statusLabel} status={status} sparkData={sparkData}
            refLow={refLow} refHigh={refHigh} activeIndex={safeIndex} />
        )
      })}
    </div>
  )
}

function formatAge(age) {
  if (!age) return '-'
  return String(age).match(/[a-z]/i) ? age : `${age}y`
}

function displaySection(file) {
  return file.lab_type || file.section || 'file'
}

function FileInventory({ files }) {
  if (!files?.length) return null
  return (
    <div className="bg-[#0d1526] border border-border rounded-[10px] overflow-hidden">
      <table className="w-full text-[12px]">
        <thead>
          <tr className="text-muted border-b border-border">
            {['Section', 'Date', 'File'].map(h => (
              <th key={h} className="text-left px-4 py-2 text-[10px] uppercase">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {files.map((file, i) => (
            <tr key={`${file.file_path}-${i}`} className="border-t border-border first:border-t-0">
              <td className="px-4 py-2 capitalize text-accent2">{displaySection(file)}</td>
              <td className="px-4 py-2 text-muted">{file.date || '—'}</td>
              <td className="px-4 py-2 text-[#d7e2f0]">{file.file_name}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function OverviewPanel({ patient }) {
  const { vitals, trends, loading: vitalsLoading } = useVitals(patient.id)

  const [visitList,     setVisitList]     = useState([])
  const [visitData,     setVisitData]     = useState(null)
  const [prevVisitData, setPrevVisitData] = useState(null)
  const [visitLoading,  setVisitLoading]  = useState(false)
  const [currentIndex,  setCurrentIndex]  = useState(0)
  const [abnormalLabs,  setAbnormalLabs]  = useState(null)
  const [showGdmt,       setShowGdmt]       = useState(false)
  const [showGuidelines, setShowGuidelines] = useState(false)

  useEffect(() => {
    if (!patient?.id) return
    setVisitList([]); setVisitData(null); setPrevVisitData(null)
    fetch('/api/labs/discharge-list', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient: patient.id }),
    })
      .then(r => r.json())
      .then(d => {
        const files = d.files || []
        setVisitList(files)
        setCurrentIndex(Math.max(0, files.length - 1))
      })
      .catch(() => {})
  }, [patient?.id])

  useEffect(() => {
    if (!visitList.length || !patient?.id) return
    const file = visitList[Math.min(currentIndex, visitList.length - 1)]
    if (!file) return

    setVisitLoading(true)
    setPrevVisitData(null)

    const fetchParsed = fileName =>
      fetch('/api/labs/discharge-parsed', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient: patient.id, file_name: fileName }),
      }).then(r => r.json())

    const jobs = [fetchParsed(file.file_name)]
    const prevFile = currentIndex > 0 ? visitList[currentIndex - 1] : null
    if (prevFile) jobs.push(fetchParsed(prevFile.file_name))

    Promise.all(jobs)
      .then(([cur, prev]) => { setVisitData(cur); if (prev) setPrevVisitData(prev) })
      .catch(() => {})
      .finally(() => setVisitLoading(false))
  }, [visitList, currentIndex, patient?.id])

  useEffect(() => {
    if (!patient?.id) return
    setAbnormalLabs(null)
    const isAbnormal = r => {
      const v = parseFloat(r.value)
      if (!isNaN(v)) {
        if (r.reference_high != null && v > r.reference_high) return true
        if (r.reference_low  != null && v < r.reference_low)  return true
      }
      return !!r.flag
    }
    const getFlag = r => {
      const v = parseFloat(r.value)
      if (!isNaN(v)) {
        if (r.reference_high != null && v > r.reference_high) return 'high'
        if (r.reference_low  != null && v < r.reference_low)  return 'low'
      }
      return r.flag
    }
    const fetchLab = type =>
      fetch(`/api/labs/${type}-results`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient: patient.id, labs: type }),
      }).then(r => r.json()).then(d => d.results || []).catch(() => [])

    Promise.all([fetchLab('chemistry'), fetchLab('hematology'), fetchLab('microscopy')])
      .then(([chem, heme, micro]) => setAbnormalLabs({
        chemistry:  chem.filter(isAbnormal).map(r => ({ ...r, flag: getFlag(r) })),
        hematology: heme.filter(isAbnormal).map(r => ({ ...r, flag: getFlag(r) })),
        microscopy: micro.filter(isAbnormal).map(r => ({ ...r, flag: getFlag(r) })),
      }))
  }, [patient?.id])

  const total     = visitList.length
  const safeIndex = total > 0 ? Math.min(currentIndex, total - 1) : 0
  const showNav   = total > 1
  const diff      = computeDiff(visitData, prevVisitData)

  return (
    <div className="p-[16px_20px] overflow-y-auto h-full">

      <div className="flex items-center gap-[10px] mb-[14px] flex-wrap">
        <span className="font-mono text-[10px] tracking-[0.12em] uppercase text-muted">
          Patient Overview — {patient.name}
        </span>

        {showNav && (
          <div className="flex items-center gap-[6px] font-mono text-[10px]">
            <button onClick={() => setCurrentIndex(i => Math.max(0, i - 1))}
              disabled={safeIndex === 0}
              className="text-muted hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed
                transition-colors normal-case text-[30px] leading-none">‹</button>
            <span className="text-muted normal-case tracking-normal">
              {safeIndex === 0 ? 'Baseline Visit' : `Visit ${safeIndex + 1} of ${total}`}
              {visitList[safeIndex]?.date_label && ` · ${visitList[safeIndex].date_label}`}
            </span>
            <button onClick={() => setCurrentIndex(i => Math.min(total - 1, i + 1))}
              disabled={safeIndex === total - 1}
              className="text-muted hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed
                transition-colors normal-case text-[30px] leading-none">›</button>
          </div>
        )}

        <div className="flex items-center gap-[6px] ml-auto">
          <button onClick={() => setShowGuidelines(true)}
            className="px-[10px] py-[4px] rounded-[6px] font-mono text-[9px] font-medium
              border border-accent/40 text-accent bg-accent/8
              cursor-pointer transition-colors hover:bg-accent/15 hover:border-accent/70">
            📋 Guidelines
          </button>
          <button onClick={() => setShowGdmt(true)}
            className="px-[10px] py-[4px] rounded-[6px] font-mono text-[9px] font-medium
              border border-[#10b981]/40 text-[#10b981] bg-[#10b981]/8
              cursor-pointer transition-colors hover:bg-[#10b981]/15 hover:border-[#10b981]/70">
            ✓ GDMT Check
          </button>
        </div>
      </div>

      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Vital Signs
      </div>
      <VitalsRow vitals={vitals} trends={trends} currentIndex={safeIndex} loading={vitalsLoading} />

      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Patient Records
      </div>
      <PatientRecordsTable
        data={visitData}
        abnormalLabs={abnormalLabs}
        loading={visitLoading}
        diff={diff}
      />

      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Demographics
      </div>
      <div className="bg-[#0d1526] border border-border rounded-[10px] p-[12px_14px]
        grid grid-cols-4 gap-3 mb-[20px]">
        {[
          ['Folder ID', patient.id],
          ['Age',       formatAge(patient.age)],
          ['Sex',       patient.sex || '-'],
          ['Source',    'Laboratory PDFs'],
        ].map(([label, value]) => (
          <div key={label}>
            <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted mb-[3px]">{label}</div>
            <div className="font-mono text-[13px] font-semibold text-[#dde4f0]">{value}</div>
          </div>
        ))}
      </div>

      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Available PDF Files
      </div>
      <FileInventory files={patient.files} />

      {showGuidelines && (
        <GuidelinesModal patient={patient} onClose={() => setShowGuidelines(false)} />
      )}
      {showGdmt && (
        <GdmtCheckModal patient={patient} onClose={() => setShowGdmt(false)} />
      )}
    </div>
  )
}