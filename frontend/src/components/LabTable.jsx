export default function LabTable({ results, type }) {
  if (!results || !results.length) {
    return (
      <div className="p-5 text-muted font-mono text-[12px]">
        No {type} results found for this patient.
      </div>
    )
  }

  const flagged = results.filter(r =>
    typeof r.value === 'number' && (
      (r.reference_high && r.value > r.reference_high) ||
      (r.reference_low  && r.value < r.reference_low)
    )
  )

  return (
    <div className="p-[16px_20px]">

      {/* Alert banner */}
      {flagged.length > 0 && (
        <div className="flex items-center gap-[10px] px-[14px] py-[9px]
          bg-warning/10 border border-warning/25 rounded-[8px] mb-4
          text-[11px] text-warning font-mono">
          ⚠ {flagged.length} value{flagged.length > 1 ? 's' : ''} outside reference range:&nbsp;
          {flagged.map(f => f.test_name).join(', ')}
        </div>
      )}

      <table className="w-full border-collapse text-[12px]">
        <thead>
          <tr>
            {['Test', 'Result', 'Reference', 'Unit'].map(h => (
              <th key={h} className="text-left px-3 py-[7px] font-mono text-[9px]
                tracking-[0.1em] uppercase text-muted border-b border-border font-normal">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => {
            let valColor = '#10b981'
            let flag = null
            if (typeof r.value === 'number') {
              if (r.reference_high && r.value > r.reference_high) {
                valColor = '#ef4444'
                flag = <span className="text-[9px] px-[5px] py-[1px] rounded-[3px]
                  bg-danger/15 text-danger ml-[6px] font-semibold">H</span>
              } else if (r.reference_low && r.value < r.reference_low) {
                valColor = '#f59e0b'
                flag = <span className="text-[9px] px-[5px] py-[1px] rounded-[3px]
                  bg-warning/15 text-warning ml-[6px] font-semibold">L</span>
              }
            }

            const ref = r.reference_low && r.reference_high
              ? `${r.reference_low} – ${r.reference_high}`
              : r.reference_high ? `< ${r.reference_high}`
              : r.reference_low  ? `> ${r.reference_low}` : '—'

            const displayVal = typeof r.value === 'number'
              ? r.value
              : (r.value || '—')

            return (
              <tr key={i}
                className="transition-colors hover:bg-accent/5"
                style={{ borderBottom: '1px solid rgba(26,45,78,0.5)' }}>
                <td className="px-3 py-[9px] font-mono text-[12px]">{r.test_name}</td>
                <td className="px-3 py-[9px] font-mono font-medium" style={{ color: valColor }}>
                  {displayVal}{flag}
                </td>
                <td className="px-3 py-[9px] font-mono text-[11px] text-muted">{ref}</td>
                <td className="px-3 py-[9px] font-mono text-[11px] text-muted">{r.unit || '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
