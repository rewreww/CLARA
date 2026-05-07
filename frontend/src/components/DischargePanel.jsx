import { useState } from 'react'

// ── Collapsible section block ─────────────────────────────────────────────────
function Section({ title, content, icon, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen)
  if (!content?.trim()) return null

  return (
    <div className="border border-border rounded-[10px] overflow-hidden mb-3">
      <div
        onClick={() => setOpen(o => !o)}
        className="flex items-center justify-between px-4 py-[11px]
          bg-card cursor-pointer hover:bg-accent/5 transition-colors select-none">
        <div className="flex items-center gap-2 font-mono text-[11px]
          tracking-[0.08em] uppercase text-accent2 font-semibold">
          <span>{icon}</span>
          {title}
        </div>
        <span
          className="text-[9px] text-muted transition-transform duration-150"
          style={{ display: 'inline-block', transform: open ? 'rotate(90deg)' : 'none' }}>
          ▶
        </span>
      </div>
      {open && (
        <div className="px-4 py-3 text-[12.5px] leading-[1.75]
          text-[#c8d4e8] bg-bg animate-fade-up border-t border-border">
          {content}
        </div>
      )}
    </div>
  )
}

// ── Vitals display ────────────────────────────────────────────────────────────
function VitalsBlock({ text }) {
  if (!text) return null

  // Split on comma or semicolon to show each vital as a chip
  const items = text.split(/[,;]/).map(s => s.trim()).filter(Boolean)

  return (
    <div className="border border-border rounded-[10px] overflow-hidden mb-3">
      <div className="flex items-center gap-2 px-4 py-[11px] bg-card
        font-mono text-[11px] tracking-[0.08em] uppercase text-accent2
        font-semibold border-b border-border">
        <span>💓</span> Vital Signs
      </div>
      <div className="px-4 py-3 bg-bg flex flex-wrap gap-2">
        {items.map((item, i) => (
          <div key={i}
            className="px-3 py-[6px] rounded-[7px] bg-card border border-border
              font-mono text-[11px] text-[#dde4f0]">
            {item}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Lab results table from parsed discharge ───────────────────────────────────
function DischargeLabs({ labs }) {
  if (!labs || labs.length === 0) return null

  const flagged = labs.filter(l => l.flag)

  return (
    <div className="border border-border rounded-[10px] overflow-hidden mb-3">
      <div className="flex items-center justify-between px-4 py-[11px] bg-card
        border-b border-border">
        <div className="flex items-center gap-2 font-mono text-[11px]
          tracking-[0.08em] uppercase text-accent2 font-semibold">
          <span>🧪</span> Lab Results from Discharge
        </div>
        {flagged.length > 0 && (
          <span className="font-mono text-[9px] px-[7px] py-[2px] rounded-[3px]
            bg-danger/15 text-danger">
            {flagged.length} abnormal
          </span>
        )}
      </div>

      <div className="bg-bg">
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr>
              {['Test', 'Value', 'Unit', 'Date', 'Flag'].map(h => (
                <th key={h} className="text-left px-4 py-[7px] font-mono text-[9px]
                  tracking-[0.08em] uppercase text-muted border-b border-border
                  font-normal">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {labs.map((lab, i) => {
              const isHigh = lab.flag === 'high'
              const isLow  = lab.flag === 'low'
              const valColor = isHigh ? '#ef4444' : isLow ? '#f59e0b' : '#10b981'

              return (
                <tr key={i}
                  className="transition-colors hover:bg-accent/5"
                  style={{ borderBottom: '1px solid rgba(26,45,78,0.5)' }}>
                  <td className="px-4 py-[9px] font-mono text-[12px]">
                    {lab.test}
                  </td>
                  <td className="px-4 py-[9px] font-mono font-semibold"
                    style={{ color: valColor }}>
                    {lab.val}
                    {isHigh && (
                      <span className="ml-2 text-[9px] px-[5px] py-[1px] rounded-[3px]
                        bg-danger/15 text-danger font-semibold">H</span>
                    )}
                    {isLow && (
                      <span className="ml-2 text-[9px] px-[5px] py-[1px] rounded-[3px]
                        bg-warning/15 text-warning font-semibold">L</span>
                    )}
                  </td>
                  <td className="px-4 py-[9px] font-mono text-[11px] text-muted">
                    {lab.unit || '—'}
                  </td>
                  <td className="px-4 py-[9px] font-mono text-[11px] text-muted">
                    {lab.date || '—'}
                  </td>
                  <td className="px-4 py-[9px]">
                    {lab.flag ? (
                      <span className={`font-mono text-[9px] px-[5px] py-[1px]
                        rounded-[3px] capitalize
                        ${isHigh
                          ? 'bg-danger/15 text-danger'
                          : isLow
                          ? 'bg-warning/15 text-warning'
                          : 'bg-muted/15 text-muted'}`}>
                        {lab.flag}
                      </span>
                    ) : (
                      <span className="font-mono text-[9px] px-[5px] py-[1px]
                        rounded-[3px] bg-success/15 text-success">
                        normal
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Header strip ──────────────────────────────────────────────────────────────
function HeaderStrip({ data, patient }) {
  const chips = [
    data.condition_discharge && { label: 'Discharge condition', value: data.condition_discharge },
    data.admitting_dx        && { label: 'Admitting Dx',        value: data.admitting_dx },
    data.final_dx            && { label: 'Final Dx',            value: data.final_dx },
  ].filter(Boolean)

  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="font-mono text-[10px] tracking-[0.12em] uppercase
            text-muted mb-1">
            Discharge Summary — {patient?.name || 'Patient'}
          </div>
          <div className="font-mono text-[10px] text-muted">
            ID: {patient?.id} · {patient?.age}y · {patient?.sex === 'M' ? 'Male' : 'Female'}
          </div>
        </div>
        <div className="font-mono text-[9px] px-2 py-1 rounded bg-success/15
          text-success border border-success/20">
          ✓ PDF parsed
        </div>
      </div>

      {chips.length > 0 && (
        <div className="grid grid-cols-1 gap-2">
          {chips.map(chip => (
            <div key={chip.label}
              className="bg-card border border-border rounded-[8px] px-4 py-3">
              <div className="font-mono text-[9px] uppercase tracking-[0.1em]
                text-muted mb-1">
                {chip.label}
              </div>
              <div className="text-[12.5px] text-[#dde4f0] leading-[1.5]">
                {chip.value}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function DischargePanel({ data, patient }) {

  // Not yet loaded
  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <div className="text-[40px] opacity-20">📋</div>
        <div className="font-mono text-[12px] text-muted tracking-[0.08em]">
          Select "Discharge" in the sidebar to load the summary
        </div>
      </div>
    )
  }

  // PDF not found
  if (!data.found) {
    return (
      <div className="p-[16px_20px]">
        <div className="font-mono text-[10px] tracking-[0.12em] uppercase
          text-muted mb-4">
          Discharge Summary — {patient?.name || 'Patient'}
        </div>
        <div className="flex flex-col items-center justify-center py-16 gap-4
          bg-card border border-border rounded-[10px]">
          <div className="text-[40px] opacity-30">📋</div>
          <div className="text-center">
            <div className="font-mono text-[13px] text-[#dde4f0] font-semibold mb-2">
              No discharge summary found
            </div>
            <div className="font-mono text-[11px] text-muted mb-3">
              Place a PDF at this path:
            </div>
            <div className="font-mono text-[10px] text-accent2 bg-bg border
              border-border rounded-[6px] px-4 py-2 text-left">
              Desktop\Patients\{patient?.id || '00001'}\discharge\*.pdf
            </div>
          </div>
        </div>
      </div>
    )
  }

  // PDF found and parsed
  return (
    <div className="p-[16px_20px] overflow-y-auto h-full">

      <HeaderStrip data={data} patient={patient} />

      <VitalsBlock text={data.physical_exam?.vitals} />

      <Section
        title="Chief Complaint"
        icon="🗣"
        content={data.chief_complaint}
        defaultOpen={true}
      />
      <Section
        title="History of Present Illness"
        icon="📖"
        content={data.hpi}
        defaultOpen={true}
      />
      <Section
        title="Physical Examination Findings"
        icon="🔍"
        content={data.physical_exam?.findings}
        defaultOpen={true}
      />
      <Section
        title="Past Medical History"
        icon="📁"
        content={data.pmh}
        defaultOpen={false}
      />

      <DischargeLabs labs={data.labs} />

    </div>
  )
}