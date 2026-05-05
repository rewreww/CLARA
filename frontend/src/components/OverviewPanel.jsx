import { STATUS_COLOR } from '../constants'

function SparkLine({ data, color, width = 80, height = 28 }) {
  const max = Math.max(...data)
  const min = Math.min(...data)
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((v - min) / (max - min || 1)) * (height - 4) - 2
    return `${x},${y}`
  }).join(' ')
  const last = pts.split(' ').pop().split(',')

  return (
    <svg width={width} height={height} className="block">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r="2.5" fill={color} />
    </svg>
  )
}

function VitalTile({ label, value, unit, trend, color, data }) {
  const trendColor = trend === '↑' ? '#ef4444' : trend === '↓' ? '#3b82f6' : '#10b981'
  return (
    <div
      className="bg-[#0d1526] border border-border rounded-[10px] p-[12px_14px]
        cursor-pointer transition-all animate-fade-up"
      onMouseEnter={e => e.currentTarget.style.borderColor = color}
      onMouseLeave={e => e.currentTarget.style.borderColor = '#1a2d4e'}
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <div className="font-mono text-[9px] tracking-[0.1em] uppercase text-muted mb-[3px]">
            {label}
          </div>
          <div className="font-mono text-[20px] font-bold" style={{ color }}>
            {value}
            <span className="text-[10px] font-normal text-muted ml-[3px]">{unit}</span>
          </div>
        </div>
        <span className="font-mono text-[10px] mt-[2px]" style={{ color: trendColor }}>
          {trend}
        </span>
      </div>
      <SparkLine data={data} color={color} />
    </div>
  )
}

function InfoTile({ title, body, icon }) {
  return (
    <div
      className="bg-[#0d1526] border border-border rounded-[10px] p-[12px_14px]
        cursor-pointer transition-all animate-fade-up"
      onMouseEnter={e => e.currentTarget.style.borderColor = '#2563eb'}
      onMouseLeave={e => e.currentTarget.style.borderColor = '#1a2d4e'}
    >
      <div className="text-[18px] mb-[6px]">{icon}</div>
      <div className="text-[11px] font-semibold mb-1">{title}</div>
      <div className="text-[11px] text-muted leading-[1.5]">{body}</div>
    </div>
  )
}

export default function OverviewPanel({ patient }) {
  const vitals = [
    { label: 'Heart Rate',      value: 82,        unit: 'bpm',  trend: '↑', color: '#ef4444', data: [74,76,79,78,82,80,82] },
    { label: 'Blood Pressure',  value: '128/84',  unit: 'mmHg', trend: '→', color: '#f59e0b', data: [125,130,128,132,126,129,128] },
    { label: 'O₂ Saturation',   value: 97,        unit: '%',    trend: '→', color: '#10b981', data: [96,97,97,98,97,96,97] },
    { label: 'Respiratory',     value: 16,        unit: '/min', trend: '↓', color: '#0ea5e9', data: [18,17,17,16,16,15,16] },
  ]

  const infoTiles = [
    { title: 'Patient History',   body: 'Hypertension (2018), T2DM (2020), Prior MI (2022)',    icon: '📁' },
    { title: 'Diagnosis History', body: 'Latest: Essential HTN with CKD Stage 2',               icon: '🩺' },
    { title: 'Allergies',         body: 'Penicillin — Documented severe reaction',               icon: '⚠' },
    { title: 'Last Admission',    body: 'April 2025 · 5-day stay · Cardiology Ward',            icon: '📅' },
  ]

  return (
    <div className="p-[16px_20px] overflow-y-auto h-full">

      {/* Header */}
      <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-muted mb-[14px]">
        Patient Overview — {patient.name}
      </div>

      {/* Vital Trends */}
      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Vital Trends
      </div>
      <div className="grid grid-cols-2 gap-[10px] mb-[20px]">
        {vitals.map(v => <VitalTile key={v.label} {...v} />)}
      </div>

      {/* Patient Records */}
      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Patient Records
      </div>
      <div className="grid grid-cols-2 gap-[10px] mb-[20px]">
        {infoTiles.map(t => <InfoTile key={t.title} {...t} />)}
      </div>

      {/* Demographics */}
      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Demographics
      </div>
      <div className="bg-[#0d1526] border border-border rounded-[10px] p-[12px_14px]
        grid grid-cols-4 gap-3">
        {[
          ['Age',    patient.age + 'y'],
          ['Sex',    patient.sex === 'M' ? 'Male' : 'Female'],
          ['Ward',   patient.ward],
          ['Status', patient.status.toUpperCase()],
        ].map(([k, v]) => (
          <div key={k}>
            <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted mb-[3px]">{k}</div>
            <div className="font-mono text-[13px] font-semibold"
              style={{ color: k === 'Status' ? STATUS_COLOR[patient.status] : '#dde4f0' }}>
              {v}
            </div>
          </div>
        ))}
      </div>

    </div>
  )
}
