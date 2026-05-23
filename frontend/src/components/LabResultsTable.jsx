import { useState, useMemo } from 'react'

// ── Helpers ───────────────────────────────────────────────────────────────────

function getStatus(value, refLow, refHigh) {
  const n = typeof value === 'number' ? value : parseFloat(value)
  if (isNaN(n)) return null
  if (refHigh != null && n > refHigh) return 'high'
  if (refLow  != null && n < refLow)  return 'low'
  return 'normal'
}

function formatRef(low, high) {
  if (low != null && high != null) return `${low} – ${high}`
  if (high != null) return `< ${high}`
  if (low  != null) return `> ${low}`
  return '—'
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  if (status === 'high') return (
    <span className="px-[5px] py-[1px] rounded-[3px] bg-danger/15 text-danger text-[9px] font-mono">HIGH</span>
  )
  if (status === 'low') return (
    <span className="px-[5px] py-[1px] rounded-[3px] bg-warning/15 text-warning text-[9px] font-mono">LOW</span>
  )
  if (status === 'normal') return (
    <span className="px-[5px] py-[1px] rounded-[3px] bg-success/15 text-success text-[9px] font-mono">NORMAL</span>
  )
  return (
    <span className="px-[5px] py-[1px] rounded-[3px] bg-border/30 text-muted text-[9px] font-mono">—</span>
  )
}

function DeltaBadge({ first, last }) {
  if (first == null || last == null || typeof first !== 'number') return null
  const delta = last - first
  if (delta === 0) return (
    <span className="text-[9px] font-mono px-[5px] py-[1px] rounded-[3px] bg-success/10 text-success">
      → stable
    </span>
  )
  const pct = first !== 0 ? Math.abs((delta / Math.abs(first)) * 100).toFixed(1) : '—'
  return (
    <span className={`text-[9px] font-mono px-[5px] py-[1px] rounded-[3px]
      ${delta > 0 ? 'bg-danger/10 text-danger' : 'bg-blue-500/10 text-blue-400'}`}>
      {delta > 0 ? '↑' : '↓'} {pct}%
    </span>
  )
}

function SparkLine({ points, refLow, refHigh, color, width = 100, height = 28 }) {
  const numeric = points.filter(p => typeof p.value === 'number' || !isNaN(parseFloat(p.value)))
  if (!numeric.length) return null

  // Single point — just a dot, no line
  if (numeric.length === 1) {
    return (
      <svg width={width} height={height} className="block opacity-40">
        <circle cx={width / 2} cy={height / 2} r={3} fill={color} />
      </svg>
    )
  }

  const vals = numeric.map(p => typeof p.value === 'number' ? p.value : parseFloat(p.value))
  const max   = Math.max(...vals)
  const min   = Math.min(...vals)
  const range = max - min || 1

  const pts = numeric.map((p, i) => {
    const v = typeof p.value === 'number' ? p.value : parseFloat(p.value)
    const x = (i / (numeric.length - 1)) * (width - 8) + 4
    const y = height - 4 - ((v - min) / range) * (height - 8)
    return `${x},${y}`
  }).join(' ')

  const dotCoords = pts.split(' ')

  return (
    <svg width={width} height={height} className="block">
      {/* Reference band */}
      {refLow != null && refHigh != null && (() => {
        const yHigh = height - 4 - ((refHigh - min) / range) * (height - 8)
        const yLow  = height - 4 - ((refLow  - min) / range) * (height - 8)
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
        const flag = numeric[i]?.flag
        return (
          <circle key={i} cx={cx} cy={cy} r={flag ? 3 : 2}
            fill={flag ? '#ef4444' : color} />
        )
      })}
    </svg>
  )
}

// ── Test row (single test, expandable) ───────────────────────────────────────

function TestRow({ testName, points, unit, refLow, refHigh, hasTrend }) {
  const [expanded, setExpanded] = useState(false)

  const latest  = points[points.length - 1]
  const first   = points[0]
  const status  = getStatus(latest?.value, refLow, refHigh)
  const hasFlag = points.some(p =>
    getStatus(p.value, refLow, refHigh) === 'high' ||
    getStatus(p.value, refLow, refHigh) === 'low'
  )

  const valColor =
    status === 'high'   ? '#ef4444' :
    status === 'low'    ? '#f59e0b' :
    status === 'normal' ? '#10b981' : '#dde4f0'

  const lineColor = hasFlag ? '#ef4444' : '#0ea5e9'
  const canExpand = points.length > 0

  return (
    <div className="border-b border-border last:border-b-0">

      {/* Summary row */}
      <div
        className={`flex items-center gap-3 px-3 py-[9px] transition-colors
          ${canExpand ? 'cursor-pointer hover:bg-accent/5' : ''}`}
        onClick={() => canExpand && setExpanded(e => !e)}
      >
        {/* Expand arrow */}
        <span
          className="text-[8px] text-muted shrink-0 transition-transform duration-150 w-[10px]"
          style={{
            display: 'inline-block',
            transform: expanded ? 'rotate(90deg)' : 'none',
            opacity: canExpand ? 1 : 0,
          }}>
          ▶
        </span>

        {/* Test name */}
        <div className="font-mono text-[11px] w-[160px] shrink-0 flex items-center gap-2">
          {testName}
          {hasFlag && (
            <span className="w-[6px] h-[6px] rounded-full bg-danger shadow-[0_0_4px_#ef4444] shrink-0" />
          )}
        </div>

        {/* Latest value */}
        <div className="font-mono text-[12px] font-semibold w-[80px] shrink-0"
          style={{ color: valColor }}>
          {latest?.value ?? '—'}
        </div>

        {/* Unit */}
        <div className="font-mono text-[11px] text-muted w-[60px] shrink-0">
          {unit || '—'}
        </div>

        {/* Reference */}
        <div className="font-mono text-[11px] text-muted w-[100px] shrink-0">
          {formatRef(refLow, refHigh)}
        </div>

        {/* Status */}
        <div className="w-[70px] shrink-0">
          <StatusBadge status={status} />
        </div>

        {/* Trend — only when multi-visit */}
        {hasTrend && (
          <div className="flex items-center gap-3 shrink-0">
            <SparkLine
              points={points}
              refLow={refLow}
              refHigh={refHigh}
              color={lineColor}
            />
            <DeltaBadge first={first?.value} last={latest?.value} />
            <div className="font-mono text-[9px] text-muted">
              {points.length} visit{points.length !== 1 ? 's' : ''}
            </div>
          </div>
        )}
      </div>

      {/* Expanded history */}
      {expanded && (
        <div className="bg-bg/50 border-t border-border px-[14px] py-[10px] animate-fade-up">
          {(refLow != null || refHigh != null) && (
            <div className="font-mono text-[9px] text-success mb-2">
              Reference: {formatRef(refLow, refHigh)} {unit}
            </div>
          )}
          <table className="w-full text-[11px] font-mono">
            <thead>
              <tr>
                {['Date', 'Result', 'Unit', 'Reference', 'Status'].map(h => (
                  <th key={h} className="text-left py-[4px] pr-4 text-[9px]
                    text-muted uppercase tracking-[0.08em] font-normal">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...points].reverse().map((p, i) => {
                const s  = getStatus(p.value, refLow, refHigh)
                const vc = s === 'high' ? '#ef4444' : s === 'low' ? '#f59e0b' : '#dde4f0'
                return (
                  <tr key={i} className="border-t border-border/40">
                    <td className="py-[5px] pr-4 text-accent2">{p.date || '—'}</td>
                    <td className="py-[5px] pr-4 font-semibold" style={{ color: vc }}>
                      {p.value ?? '—'}
                    </td>
                    <td className="py-[5px] pr-4 text-muted">{unit || '—'}</td>
                    <td className="py-[5px] pr-4 text-muted">
                      {formatRef(p.ref_low ?? refLow, p.ref_high ?? refHigh)}
                    </td>
                    <td className="py-[5px]">
                      <StatusBadge status={s} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function LabResultsTable({ results, timeline, labType }) {
  const { testMap, hasTrend, visitCount } = useMemo(() => {
    const map = {}

    // Prefer timeline (multi-visit) over flat results
    if (timeline && timeline.length > 0) {
      timeline.forEach(entry => {
        entry.results.forEach(r => {
          if (!map[r.test_name]) {
            map[r.test_name] = {
              unit:    r.unit,
              refLow:  r.reference_low,
              refHigh: r.reference_high,
              points:  [],
            }
          }
          const s =
            typeof r.value === 'number' || !isNaN(parseFloat(r.value))
              ? (r.reference_high != null && (typeof r.value === 'number' ? r.value : parseFloat(r.value)) > r.reference_high
                  ? 'high'
                  : r.reference_low != null && (typeof r.value === 'number' ? r.value : parseFloat(r.value)) < r.reference_low
                    ? 'low' : null)
              : null
          map[r.test_name].points.push({
            date:      entry.date,
            value:     r.value,
            flag:      s,
            ref_low:   r.reference_low,
            ref_high:  r.reference_high,
          })
        })
      })
      Object.values(map).forEach(t =>
        t.points.sort((a, b) => a.date.localeCompare(b.date))
      )
      return { testMap: map, hasTrend: true, visitCount: timeline.length }
    }

    // Fallback: flat single-visit results
    if (results && results.length > 0) {
      results.forEach(r => {
        map[r.test_name] = {
          unit:    r.unit,
          refLow:  r.reference_low,
          refHigh: r.reference_high,
          points:  [{ value: r.value, ref_low: r.reference_low, ref_high: r.reference_high }],
        }
      })
      return { testMap: map, hasTrend: false, visitCount: 1 }
    }

    return { testMap: {}, hasTrend: false, visitCount: 0 }
  }, [results, timeline])

  const entries = Object.entries(testMap)

  if (!entries.length) {
    return (
      <div className="p-5 text-muted font-mono text-[12px]">
        No {labType} results found for this patient.
      </div>
    )
  }

  const latestFlagged = entries.filter(([, d]) => {
    const latest = d.points[d.points.length - 1]
    const s = getStatus(latest?.value, d.refLow, d.refHigh)
    return s === 'high' || s === 'low'
  }).map(([name]) => name)

  return (
    <div className="p-[16px_20px]">

      {/* Section header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-muted">
            {labType.charAt(0).toUpperCase() + labType.slice(1)} Results
          </div>
          <span className="font-mono text-[10px] text-accent2">
            {visitCount} visit{visitCount !== 1 ? 's' : ''}
          </span>
          {latestFlagged.length > 0 && (
            <span className="font-mono text-[10px] text-danger flex items-center gap-1">
              <span className="w-[5px] h-[5px] rounded-full bg-danger" />
              {latestFlagged.length} abnormal
            </span>
          )}
        </div>
        <div className="font-mono text-[9px] text-muted">
          Click any row to expand history
        </div>
      </div>

      {/* Alert banner */}
      {latestFlagged.length > 0 && (
        <div className="flex items-center gap-[10px] px-[14px] py-[9px]
          bg-warning/10 border border-warning/25 rounded-[8px] mb-4
          text-[11px] text-warning font-mono">
          ⚠ {latestFlagged.length} value{latestFlagged.length > 1 ? 's' : ''} outside reference range:&nbsp;
          {latestFlagged.join(', ')}
        </div>
      )}

      {/* Table */}
      <div className="bg-card border border-border rounded-[10px] overflow-hidden">

        {/* Column headers */}
        <div className="flex items-center gap-3 px-3 py-[7px] border-b border-border bg-bg/50">
          <div className="w-[10px] shrink-0" />
          {[
            ['Test',      'w-[160px]'],
            ['Latest',    'w-[80px]'],
            ['Unit',      'w-[60px]'],
            ['Reference', 'w-[100px]'],
            ['Status',    'w-[70px]'],
          ].map(([label, w]) => (
            <div key={label}
              className={`font-mono text-[9px] uppercase tracking-[0.08em] text-muted font-normal shrink-0 ${w}`}>
              {label}
            </div>
          ))}
          {hasTrend && (
            <div className="font-mono text-[9px] uppercase tracking-[0.08em] text-muted font-normal">
              Trend
            </div>
          )}
        </div>

        {/* Rows */}
        {entries.map(([testName, data]) => (
          <TestRow
            key={testName}
            testName={testName}
            points={data.points}
            unit={data.unit}
            refLow={data.refLow}
            refHigh={data.refHigh}
            hasTrend={hasTrend}
          />
        ))}
      </div>

      {/* Legend */}
      {hasTrend && (
        <div className="flex items-center gap-4 mt-3 font-mono text-[9px] text-muted">
          <div className="flex items-center gap-1">
            <div className="w-[16px] h-[2px] bg-accent2" /> Normal trend
          </div>
          <div className="flex items-center gap-1">
            <div className="w-[16px] h-[2px] bg-danger" /> Abnormal
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm bg-success/10 border border-success/20" /> Ref band
          </div>
        </div>
      )}
    </div>
  )
}