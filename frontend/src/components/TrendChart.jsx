import { useState, useMemo } from 'react'

// ── Mini SVG sparkline ────────────────────────────────────────────────────────
function SparkLine({ points, color, width = 120, height = 36 }) {
  if (!points || points.length < 2) return null
  const vals = points.map(p => p.value)
  const max  = Math.max(...vals)
  const min  = Math.min(...vals)
  const range = max - min || 1

  const pts = points.map((p, i) => {
    const x = (i / (points.length - 1)) * (width - 8) + 4
    const y = height - 4 - ((p.value - min) / range) * (height - 12)
    return `${x},${y}`
  }).join(' ')

  const last = pts.split(' ').pop().split(',')

  return (
    <svg width={width} height={height} className="block">
      {/* Reference band */}
      {points[0]?.ref_low != null && points[0]?.ref_high != null && (() => {
        const yHigh = height - 4 - ((points[0].ref_high - min) / range) * (height - 12)
        const yLow  = height - 4 - ((points[0].ref_low  - min) / range) * (height - 12)
        return (
          <rect x={4} y={Math.min(yHigh, yLow)}
            width={width - 8}
            height={Math.abs(yHigh - yLow)}
            fill="rgba(16,185,129,0.08)"
            stroke="rgba(16,185,129,0.15)"
            strokeWidth={0.5}
          />
        )
      })()}
      <polyline points={pts} fill="none" stroke={color}
        strokeWidth="1.5" strokeLinejoin="round" />
      {/* Dots */}
      {pts.split(' ').map((pt, i) => {
        const [cx, cy] = pt.split(',')
        const isFlag = points[i]?.flag
        return (
          <circle key={i} cx={cx} cy={cy} r={isFlag ? 3.5 : 2}
            fill={isFlag ? '#ef4444' : color}
            stroke={isFlag ? 'rgba(239,68,68,0.3)' : 'none'}
            strokeWidth={isFlag ? 2 : 0}
          />
        )
      })}
      {/* Latest value label */}
      <text x={Number(last[0]) + 4} y={Number(last[1]) + 1}
        fontSize={8} fill={color} fontFamily="JetBrains Mono">
        {points[points.length - 1]?.value}
      </text>
    </svg>
  )
}

// ── Delta badge ───────────────────────────────────────────────────────────────
function DeltaBadge({ first, last }) {
  if (first == null || last == null || typeof first !== 'number') return null
  const delta = last - first
  const pct   = first !== 0 ? ((delta / Math.abs(first)) * 100).toFixed(1) : '—'
  if (delta === 0) return (
    <span className="text-[9px] font-mono px-[5px] py-[1px] rounded-[3px]
      bg-success/10 text-success">→ stable</span>
  )
  return (
    <span className={`text-[9px] font-mono px-[5px] py-[1px] rounded-[3px]
      ${delta > 0
        ? 'bg-danger/10 text-danger'
        : 'bg-blue-500/10 text-blue-400'}`}>
      {delta > 0 ? '↑' : '↓'} {Math.abs(pct)}%
    </span>
  )
}

// ── Single test trend row ─────────────────────────────────────────────────────
function TestTrendRow({ testName, points, unit, refLow, refHigh }) {
  const [expanded, setExpanded] = useState(false)

  const hasFlag = points.some(p => p.flag)
  const latest  = points[points.length - 1]?.value
  const first   = points[0]?.value

  const lineColor = hasFlag ? '#ef4444' : '#0ea5e9'

  return (
    <div className="border-b border-border last:border-b-0">
      {/* Summary row */}
      <div
        className="flex items-center gap-3 px-3 py-[9px] cursor-pointer
          transition-colors hover:bg-accent/5"
        onClick={() => setExpanded(e => !e)}
      >
        {/* Expand arrow */}
        <span className="text-[8px] text-muted transition-transform duration-150 shrink-0"
          style={{ display: 'inline-block', transform: expanded ? 'rotate(90deg)' : 'none' }}>
          ▶
        </span>

        {/* Test name */}
        <div className="font-mono text-[11px] w-[160px] shrink-0 flex items-center gap-2">
          {testName}
          {hasFlag && (
            <span className="w-[6px] h-[6px] rounded-full bg-danger
              shadow-[0_0_4px_#ef4444] shrink-0" />
          )}
        </div>

        {/* Sparkline */}
        <div className="shrink-0">
          <SparkLine points={points} color={lineColor} />
        </div>

        {/* Latest value */}
        <div className="font-mono text-[12px] font-semibold w-[80px] shrink-0"
          style={{ color: hasFlag ? '#ef4444' : '#10b981' }}>
          {latest} <span className="text-[9px] text-muted font-normal">{unit}</span>
        </div>

        {/* Delta */}
        <DeltaBadge first={first} last={latest} />

        {/* Point count */}
        <div className="ml-auto font-mono text-[9px] text-muted shrink-0">
          {points.length} visit{points.length > 1 ? 's' : ''}
        </div>
      </div>

      {/* Expanded date-by-date table */}
      {expanded && (
        <div className="bg-bg/50 border-t border-border px-[14px] py-[10px]
          animate-fade-up">
          {/* Ref range */}
          {(refLow != null || refHigh != null) && (
            <div className="font-mono text-[9px] text-success mb-2">
              Reference range:{' '}
              {refLow != null && refHigh != null
                ? `${refLow} – ${refHigh} ${unit}`
                : refHigh != null ? `< ${refHigh} ${unit}`
                : `> ${refLow} ${unit}`}
            </div>
          )}

          <table className="w-full text-[11px] font-mono">
            <thead>
              <tr>
                {['Date', 'Value', 'Unit', 'Status'].map(h => (
                  <th key={h} className="text-left py-[4px] pr-4 text-[9px]
                    text-muted uppercase tracking-[0.08em] font-normal">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {points.map((p, i) => (
                <tr key={i} className="border-t border-border/40">
                  <td className="py-[5px] pr-4 text-accent2">{p.date}</td>
                  <td className="py-[5px] pr-4 font-semibold"
                    style={{ color: p.flag ? '#ef4444' : '#dde4f0' }}>
                    {p.value}
                  </td>
                  <td className="py-[5px] pr-4 text-muted">{unit}</td>
                  <td className="py-[5px]">
                    {p.flag === 'high' && (
                      <span className="px-[5px] py-[1px] rounded-[3px]
                        bg-danger/15 text-danger text-[9px]">HIGH</span>
                    )}
                    {p.flag === 'low' && (
                      <span className="px-[5px] py-[1px] rounded-[3px]
                        bg-warning/15 text-warning text-[9px]">LOW</span>
                    )}
                    {!p.flag && (
                      <span className="px-[5px] py-[1px] rounded-[3px]
                        bg-success/15 text-success text-[9px]">NORMAL</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Main TrendChart component ─────────────────────────────────────────────────
export default function TrendChart({ timeline, labType, patient }) {
  const [selectedDate, setSelectedDate] = useState('all')

  // Build per-test timeline: { testName → [{date, value, unit, flag, ref_low, ref_high}] }
  const testMap = useMemo(() => {
    const map = {}
    const datesToUse = selectedDate === 'all'
      ? timeline
      : timeline.filter(e => e.date === selectedDate)

    datesToUse.forEach(entry => {
      entry.results.forEach(r => {
        if (!map[r.test_name]) map[r.test_name] = {
          unit:    r.unit,
          refLow:  r.reference_low,
          refHigh: r.reference_high,
          points:  [],
        }
        let flag = null
        if (typeof r.value === 'number') {
          if (r.reference_high && r.value > r.reference_high) flag = 'high'
          else if (r.reference_low && r.value < r.reference_low) flag = 'low'
        }
        map[r.test_name].points.push({
          date:     entry.date,
          value:    r.value,
          unit:     r.unit,
          flag,
          ref_low:  r.reference_low,
          ref_high: r.reference_high,
        })
      })
    })

    // Sort points by date within each test
    Object.values(map).forEach(t => t.points.sort((a, b) => a.date.localeCompare(b.date)))
    return map
  }, [timeline, selectedDate])

  const dates     = timeline.map(e => e.date)
  const flagCount = Object.values(testMap).filter(t => t.points.some(p => p.flag)).length

  return (
    <div className="p-[16px_20px] overflow-y-auto h-full">

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-muted mb-1">
            Lab Trends — {labType.charAt(0).toUpperCase() + labType.slice(1)}
          </div>
          <div className="flex items-center gap-3">
            <span className="font-mono text-[11px] text-accent2">
              {dates.length} visit{dates.length > 1 ? 's' : ''} found
            </span>
            {flagCount > 0 && (
              <span className="font-mono text-[11px] text-danger flex items-center gap-1">
                <span className="w-[6px] h-[6px] rounded-full bg-danger" />
                {flagCount} test{flagCount > 1 ? 's' : ''} with abnormal values
              </span>
            )}
          </div>
        </div>

        {/* Date filter */}
        <div className="flex items-center gap-2">
          <span className="font-mono text-[9px] text-muted uppercase tracking-wider">Filter:</span>
          <div className="flex gap-1 flex-wrap">
            <button
              onClick={() => setSelectedDate('all')}
              className={`font-mono text-[10px] px-[8px] py-[4px] rounded-[4px]
                border transition-all cursor-pointer
                ${selectedDate === 'all'
                  ? 'bg-accent/20 border-accent text-accent2'
                  : 'bg-card border-border text-muted hover:border-accent2 hover:text-accent2'}`}>
              All dates
            </button>
            {dates.map(d => (
              <button key={d}
                onClick={() => setSelectedDate(d)}
                className={`font-mono text-[10px] px-[8px] py-[4px] rounded-[4px]
                  border transition-all cursor-pointer
                  ${selectedDate === d
                    ? 'bg-accent/20 border-accent text-accent2'
                    : 'bg-card border-border text-muted hover:border-accent2 hover:text-accent2'}`}>
                {d}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mb-3 font-mono text-[9px] text-muted">
        <div className="flex items-center gap-1">
          <div className="w-[20px] h-[2px] bg-accent2" />
          Normal range
        </div>
        <div className="flex items-center gap-1">
          <div className="w-[20px] h-[2px] bg-danger" />
          Abnormal value
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm bg-success/10 border border-success/20" />
          Reference band
        </div>
        <div className="ml-auto">Click any row to expand date-by-date values</div>
      </div>

      {/* Test rows */}
      <div className="bg-card border border-border rounded-[10px] overflow-hidden">
        {/* Table header */}
        <div className="flex items-center gap-3 px-3 py-[7px] border-b border-border
          bg-bg/50">
          {['', 'Test', 'Trend', 'Latest', 'Change', ''].map((h, i) => (
            <div key={i} className={`font-mono text-[9px] uppercase tracking-[0.08em]
              text-muted font-normal
              ${i === 0 ? 'w-[14px] shrink-0' : ''}
              ${i === 1 ? 'w-[160px] shrink-0' : ''}
              ${i === 2 ? 'w-[120px] shrink-0' : ''}
              ${i === 3 ? 'w-[80px] shrink-0' : ''}
              ${i === 5 ? 'ml-auto' : ''}`}>
              {h}
            </div>
          ))}
        </div>

        {/* Rows */}
        {Object.entries(testMap).map(([testName, data]) => (
          <TestTrendRow
            key={testName}
            testName={testName}
            points={data.points}
            unit={data.unit}
            refLow={data.refLow}
            refHigh={data.refHigh}
          />
        ))}
      </div>

    </div>
  )
}