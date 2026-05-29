import { useState, useEffect } from 'react'
import { useVitals }           from '../hooks/useVitals'

const STATUS_HEX = { normal: '#10b981', warning: '#f59e0b', critical: '#ef4444' }

const VITAL_CONFIG = [
  { key: 'bp',   label: 'Blood Pressure', unit: 'mmHg', refLow: 90,   refHigh: 120  },
  { key: 'hr',   label: 'Heart Rate',     unit: 'bpm',  refLow: 60,   refHigh: 100  },
  { key: 'rr',   label: 'Respiratory',    unit: '/min', refLow: 12,   refHigh: 20   },
  { key: 'temp', label: 'Temperature',    unit: '°C',   refLow: 36.1, refHigh: 37.2 },
  { key: 'o2',   label: 'O₂ Saturation',  unit: '%',    refLow: 95,   refHigh: 100  },
]

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

function formatTrendDate(dateStr) {
  if (!dateStr) return ''
  const parts = dateStr.split('-')
  if (parts.length >= 3) return `${MONTHS[parseInt(parts[1]) - 1]} ${parts[2]}, ${parts[0]}`
  if (parts.length === 2) return `${MONTHS[parseInt(parts[1]) - 1]} ${parts[0]}`
  return dateStr
}

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

  const max   = Math.max(...allVals)
  const min   = Math.min(...allVals)
  const range = max - min || 1

  const toY = v => height - 4 - ((v - min) / range) * (height - 8)
  const toX = (i, len) => (i / (len - 1)) * (width - 8) + 4
  const pts  = data.map((v, i) => `${toX(i, data.length)},${toY(v)}`).join(' ')
  const dotCoords = pts.split(' ')

  return (
    <svg width={width} height={height} className="block">
      {refLow != null && refHigh != null && (() => {
        const yHigh = toY(refHigh)
        const yLow  = toY(refLow)
        const yTop  = Math.min(yHigh, yLow)
        const yH    = Math.max(Math.abs(yHigh - yLow), 1)
        return (
          <rect x={4} y={yTop} width={width - 8} height={yH}
            fill="rgba(16,185,129,0.08)" stroke="rgba(16,185,129,0.2)" strokeWidth={0.5} />
        )
      })()}
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      {dotCoords.map((pt, i) => {
        const [cx, cy] = pt.split(',')
        return (
          <circle key={i} cx={cx} cy={cy}
            r={i === activeIndex ? 5 : 2}
            fill={color}
            opacity={i === activeIndex ? 1 : 0.5}
          />
        )
      })}
    </svg>
  )
}

function VitalTile({ label, value, unit, statusLabel, status, sparkData, refLow, refHigh, activeIndex }) {
  const color = STATUS_HEX[status] || STATUS_HEX.normal
  return (
    <div
      className="bg-[#0d1526] border border-border rounded-[10px] p-[12px_14px]
        flex flex-col h-[145px] transition-all"
      onMouseEnter={e => e.currentTarget.style.borderColor = color}
      onMouseLeave={e => e.currentTarget.style.borderColor = '#1a2d4e'}
    >
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

function PatientRecordsTable({ data, abnormalLabs, loading }) {
  if (loading) {
    return (
      <div className="border border-border rounded-[10px] bg-[#0d1526] p-4 mb-[20px]">
        <div className="h-3 w-1/2 bg-border rounded animate-pulse mb-2" />
        <div className="h-3 w-1/3 bg-border rounded animate-pulse" />
      </div>
    )
  }

  const chemistry  = abnormalLabs?.chemistry  || []
  const hematology = abnormalLabs?.hematology || []
  const microscopy = abnormalLabs?.microscopy || []
  const meds       = data?.medications || []
  const finalDx    = data?.final_dx

  const columns = [
    { key: 'chemistry',  label: 'Chemistry',      items: chemistry,  type: 'lab'  },
    { key: 'hematology', label: 'Hematology',      items: hematology, type: 'lab'  },
    { key: 'microscopy', label: 'Microscopy',      items: microscopy, type: 'lab'  },
    { key: 'final_dx', label: 'Final Diagnosis', items: finalDx ? [finalDx] : [], type: 'text' },
    { key: 'meds', label: 'Prescriptions', items: meds, type: 'text' },
  ].filter(col => col.items.length > 0)

  if (!columns.length) {
    return (
      <div className="border border-border rounded-[10px] bg-[#0d1526] px-4 py-3 mb-[20px]
        font-mono text-[11px] text-muted">
        No flagged values or diagnosis recorded
      </div>
    )
  }

  const maxRows = Math.max(...columns.map(c => c.items.length))

  return (
    <div className="border border-border rounded-[10px] overflow-hidden bg-[#0d1526] mb-[20px]">
      <div className="grid border-b border-border"
        style={{ gridTemplateColumns: `repeat(${columns.length}, 1fr)` }}>
        {columns.map((col, i) => (
          <div key={col.key}
            className={`px-3 py-2 font-mono text-[9px] uppercase tracking-[0.1em] text-muted
              ${i > 0 ? 'border-l border-border' : ''}`}>
            {col.label}
          </div>
        ))}
      </div>
      {Array.from({ length: maxRows }).map((_, rowIdx) => (
        <div key={rowIdx} className="grid border-t border-border"
          style={{ gridTemplateColumns: `repeat(${columns.length}, 1fr)` }}>
          {columns.map((col, colIdx) => {
            const item = col.items[rowIdx]
            return (
              <div key={col.key}
                className={`px-3 py-[5px] font-mono text-[11px]
                  ${colIdx > 0 ? 'border-l border-border' : ''}`}>
                {item && col.type === 'lab' ? (
                  <span className="flex items-baseline gap-[5px] flex-wrap">
                    <span className="text-[#d7e2f0]">{item.test_name}</span>
                    <span style={{ color: item.flag === 'high' ? '#ef4444' : '#f59e0b' }}>
                      {String(item.value)}{item.unit ? ` ${item.unit}` : ''}
                    </span>
                    <span className="text-[9px]"
                      style={{ color: item.flag === 'high' ? '#ef4444' : '#f59e0b' }}>
                      {item.flag === 'high' ? '↑' : '↓'}
                    </span>
                  </span>
                ) : item ? (
                  <span className="text-[#d7e2f0] leading-[1.5]">{item}</span>
                ) : null}
              </div>
            )
          })}
        </div>
      ))}
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

export default function OverviewPanel({ patient }) {
  const { vitals, trends, loading: vitalsLoading } = useVitals(patient.id)

  const [visitList,    setVisitList]    = useState([])
  const [visitData,    setVisitData]    = useState(null)
  const [visitLoading, setVisitLoading] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [abnormalLabs, setAbnormalLabs] = useState(null)

  useEffect(() => {
    if (!patient?.id) return
    setVisitList([])
    setVisitData(null)
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
    fetch('/api/labs/discharge-parsed', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient: patient.id, file_name: file.file_name }),
    })
      .then(r => r.json())
      .then(setVisitData)
      .catch(() => {})
      .finally(() => setVisitLoading(false))
  }, [visitList, currentIndex, patient?.id])

    useEffect(() => {
    if (!patient?.id) return
    setAbnormalLabs(null)

    const isAbnormal = (r) => {
      const val = typeof r.value === 'number' ? r.value : parseFloat(r.value)
      if (!isNaN(val)) {
        if (r.reference_high != null && val > r.reference_high) return true
        if (r.reference_low  != null && val < r.reference_low)  return true
      }
      return !!r.flag
    }

    const getFlag = (r) => {
      const val = typeof r.value === 'number' ? r.value : parseFloat(r.value)
      if (!isNaN(val)) {
        if (r.reference_high != null && val > r.reference_high) return 'high'
        if (r.reference_low  != null && val < r.reference_low)  return 'low'
      }
      return r.flag
    }

    const fetchLab = (type) =>
      fetch('/api/labs/' + type + '-results', {
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

  const navButtons = (
    <>
      <button
        onClick={() => setCurrentIndex(i => Math.max(0, i - 1))}
        disabled={safeIndex === 0}
        className="text-muted hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed
          transition-colors normal-case text-[13px] leading-none"
      >‹</button>
      <span className="text-muted normal-case tracking-normal">
        Visit {safeIndex + 1} of {total}
        {visitList[safeIndex]?.date_label && ` · ${visitList[safeIndex].date_label}`}
      </span>
      <button
        onClick={() => setCurrentIndex(i => Math.min(total - 1, i + 1))}
        disabled={safeIndex === total - 1}
        className="text-muted hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed
          transition-colors normal-case text-[13px] leading-none"
      >›</button>
    </>
  )

  return (
    <div className="p-[16px_20px] overflow-y-auto h-full">

      <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-muted mb-[14px]">
        Patient Overview — {patient.name}
      </div>

      <div className="flex items-center gap-3 font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Vital Signs
        {showNav && navButtons}
      </div>
      <VitalsRow vitals={vitals} trends={trends} currentIndex={safeIndex} loading={vitalsLoading} />

      <div className="flex items-center gap-3 font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Patient Records
        {showNav && navButtons}
      </div>
      <PatientRecordsTable data={visitData} abnormalLabs={abnormalLabs} loading={visitLoading} />

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

    </div>
  )
}