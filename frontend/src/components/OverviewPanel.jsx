function SparkLine({ data, color, width = 80, height = 28 }) {
  const max = Math.max(...data)
  const min = Math.min(...data)
  const pts = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width
    const y = height - ((value - min) / (max - min || 1)) * (height - 4) - 2
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
      onMouseEnter={event => { event.currentTarget.style.borderColor = color }}
      onMouseLeave={event => { event.currentTarget.style.borderColor = '#1a2d4e' }}
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
      onMouseEnter={event => { event.currentTarget.style.borderColor = '#2563eb' }}
      onMouseLeave={event => { event.currentTarget.style.borderColor = '#1a2d4e' }}
    >
      <div className="text-[18px] mb-[6px]">{icon}</div>
      <div className="text-[11px] font-semibold mb-1">{title}</div>
      <div className="text-[11px] text-muted leading-[1.5]">{body}</div>
    </div>
  )
}

function formatAge(age) {
  if (!age) return '-'
  return String(age).match(/[a-z]/i) ? age : `${age}y`
}

function displaySection(file) {
  if (file.lab_type) return file.lab_type
  return file.section || 'file'
}

function latestLabDate(files) {
  const dates = (files || [])
    .map(file => file.date)
    .filter(Boolean)
    .sort()

  return dates[dates.length - 1] || 'No dated labs'
}

function FileInventory({ files }) {
  if (!files?.length) return null

  return (
    <div className="bg-[#0d1526] border border-border rounded-[10px] overflow-hidden">
      <table className="w-full text-[12px]">
        <thead>
          <tr className="text-muted border-b border-border">
            {['Section', 'Date', 'File'].map(header => (
              <th key={header} className="text-left px-4 py-2 text-[10px] uppercase">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {files.map((file, index) => (
            <tr key={`${file.file_path || file.file_name}-${index}`} className="border-t border-border first:border-t-0">
              <td className="px-4 py-2 capitalize text-accent2">
                {displaySection(file)}
              </td>
              <td className="px-4 py-2 text-muted">
                {file.date || '-'}
              </td>
              <td className="px-4 py-2 text-[#d7e2f0]">
                {file.file_name}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function OverviewPanel({ patient }) {
  const vitals = [
    { label: 'Heart Rate', value: 82, unit: 'bpm', trend: '↑', color: '#ef4444', data: [74, 76, 79, 78, 82, 80, 82] },
    { label: 'Blood Pressure', value: '128/84', unit: 'mmHg', trend: '→', color: '#f59e0b', data: [125, 130, 128, 132, 126, 129, 128] },
    { label: 'O2 Saturation', value: 97, unit: '%', trend: '→', color: '#10b981', data: [96, 97, 97, 98, 97, 96, 97] },
    { label: 'Respiratory', value: 16, unit: '/min', trend: '↓', color: '#0ea5e9', data: [18, 17, 17, 16, 16, 15, 16] },
  ]

  const fileCount = patient.files?.length || 0
  const sections = patient.available_sections?.length
    ? patient.available_sections.join(', ')
    : 'No PDF sections found'

  const infoTiles = [
    { title: 'Patient Folder', body: `Desktop/Patients/${patient.id}`, icon: '📁' },
    { title: 'Available Sections', body: sections, icon: '🗂' },
    { title: 'PDF Files', body: `${fileCount} document${fileCount === 1 ? '' : 's'} indexed`, icon: '📄' },
    { title: 'Latest Lab Date', body: latestLabDate(patient.files), icon: '📅' },
  ]

  return (
    <div className="p-[16px_20px] overflow-y-auto h-full">
      <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-muted mb-[14px]">
        Patient Overview - {patient.name}
      </div>

      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Vital Trends
      </div>
      <div className="grid grid-cols-2 gap-[10px] mb-[20px]">
        {vitals.map(vital => <VitalTile key={vital.label} {...vital} />)}
      </div>

      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Patient Records
      </div>
      <div className="grid grid-cols-2 gap-[10px] mb-[20px]">
        {infoTiles.map(tile => <InfoTile key={tile.title} {...tile} />)}
      </div>

      <div className="font-mono text-[10px] tracking-[0.1em] uppercase text-accent mb-[10px]">
        ● Demographics
      </div>
      <div className="bg-[#0d1526] border border-border rounded-[10px] p-[12px_14px]
        grid grid-cols-4 gap-3 mb-[20px]">
        {[
          ['Folder ID', patient.id],
          ['Age', formatAge(patient.age)],
          ['Sex', patient.sex || '-'],
          ['Name Source', 'Laboratory PDFs'],
        ].map(([label, value]) => (
          <div key={label}>
            <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted mb-[3px]">{label}</div>
            <div className="font-mono text-[13px] font-semibold text-[#dde4f0]">
              {value}
            </div>
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
