import { useVitals } from '../hooks/useVitals'

const STATUS_HEX = { normal: '#10b981', warning: '#f59e0b', critical: '#ef4444' }

// ── SparkLine — single point shows dashed line + dot ─────────────────────────
function SparkLine({ data, color, width = 80, height = 22 }) {
  if (!data?.length) return null

  if (data.length === 1) {
    return (
      <svg width={width} height={height} className="block">
        <line x1={0} y1={height / 2} x2={width} y2={height / 2}
          stroke={color} strokeWidth="1" strokeDasharray="3,3" opacity="0.35" />
        <circle cx={width / 2} cy={height / 2} r="3" fill={color} />
      </svg>
    )
  }

  const max = Math.max(...data)
  const min = Math.min(...data)
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((v - min) / (max - min || 1)) * (height - 6) - 3
    return `${x},${y}`
  }).join(' ')
  const [lx, ly] = pts.split(' ').pop().split(',')

  return (
    <svg width={width} height={height} className="block">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx={lx} cy={ly} r="2.5" fill={color} />
    </svg>
  )
}

// ── Vital tile ────────────────────────────────────────────────────────────────
function VitalTile({ label, value, unit, statusLabel, status, sparkData }) {
  const color = STATUS_HEX[status] || STATUS_HEX.normal
  return (
    <div
      className="bg-[#0d1526] border border-border rounded-[10px] p-[12px_14px]
        flex flex-col h-[110px] transition-all"
      onMouseEnter={e => e.currentTarget.style.borderColor = color}
      onMouseLeave={e => e.currentTarget.style.borderColor = '#1a2d4e'}
    >
      <div className="font-mono text-[9px] tracking-[0.1em] uppercase text-muted mb-[4px]">
        {label}
      </div>
      <div className="font-mono text-[20px] font-bold leading-none" style={{ color }}>
        {value ?? '—'}
        <span className="text-[10px] font-normal text-muted ml-[3px]">{unit}</span>
      </div>
      <div className="font-mono text-[9px] mt-[3px]" style={{ color }}>
        {statusLabel}
      </div>
      <div className="mt-auto">
        <SparkLine data={sparkData} color={color} />
      </div>
    </div>
  )
}

// ── Skeleton while loading ────────────────────────────────────────────────────
function SkeletonTile() {
  return (
    <div className="bg-[#0d1526] border border-border rounded-[10px] p-[12px_14px]
      flex flex-col h-[110px] animate-pulse">
      <div className="h-2 w-14 bg-border rounded mb-3" />
      <div className="h-5 w-20 bg-border rounded mb-2" />
      <div className="h-2 w-10 bg-border rounded" />
    </div>
  )
}

// ── 5-tile vitals row ─────────────────────────────────────────────────────────
const VITAL_CONFIG = [
  { key: 'bp',   label: 'Blood Pressure',  unit: 'mmHg' },
  { key: 'hr',   label: 'Heart Rate',      unit: 'bpm'  },
  { key: 'rr',   label: 'Respiratory',     unit: '/min' },
  { key: 'temp', label: 'Temperature',     unit: '°C'   },
  { key: 'o2',   label: 'O₂ Saturation',   unit: '%'    },
]

function VitalsRow({ vitals, loading }) {
  if (loading) {
    return (
      <div className="grid grid-cols-5 gap-[10px] mb-[20px]">
        {VITAL_CONFIG.map(t => <SkeletonTile key={t.key} />)}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-5 gap-[10px] mb-[20px]">
      {VITAL_CONFIG.map(({ key, label, unit }) => {
        const entry = vitals?.[key]
        return (
          <VitalTile
            key={key}
            label={label}
            unit={unit}
            value={entry?.value ?? null}
            statusLabel={entry?.label ?? (vitals ? 'No data' : '—')}
            status={entry?.status ?? 'normal'}
            sparkData={entry?.numeric != null ? [entry.numeric] : [0]}
          />
        )
      })}
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatAge(age) {
  if (!age) return '-'
  return String(age).match(/[a-z]/i) ? age : `${age}y`
}

function displaySection(file) {
  return file.lab_type || file.section || 'file'
}

function latestLabDate(files) {
  const dates = (files || []).map(f => f.date).filter(Boolean).sort()
  return dates[dates.length - 1] || 'No dated labs'
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

// ── Main export ───────────────────────────────────────────────────────────────
export default function OverviewPanel({ patient }) {
  const { vitals, loading: vitalsLoading } = useVitals(patient.id)

  const fileCount = patient.files?.length || 0
  const sections  = patient.available_sections?.length
    ? patient.available_sections.join(', ')
    : 'No PDF sections found'

  const infoTiles = [
    { title: 'Patient Folder',     body: `Desktop/Patients/${patient.id}`, icon: '📁' },
    { title: 'Available Sections', body: sections,                          icon: '🗂' },
    { title: 'PDF Files',          body: `${fileCount} document${fileCount === 1 ? '' : 's'} indexed`, icon: '📄' },
    { title: 'Latest Lab Date',    body: latestLabDate(patient.files),     icon: '📅' },
  ]

  return (
    <div className="p-[16px_20px] overflow-y-auto h-full">

      <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-muted mb-[14px]">
        Patient Overview — {patient.name}
      </div>

      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Vital Signs
      </div>
      <VitalsRow vitals={vitals} loading={vitalsLoading} />

      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Patient Records
      </div>
      <div className="grid grid-cols-2 gap-[10px] mb-[20px]">
        {infoTiles.map(t => <InfoTile key={t.title} {...t} />)}
      </div>

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