import { useEffect, useMemo, useRef, useState } from 'react'
import { vitalSeries } from '../lib/mimicOverview'

const format = value => Number.isInteger(value) ? value : value.toFixed(1)
function Trend({ points, label }) {
  const scroller = useRef(null)
  const [graphWidth, setGraphWidth] = useState(240)
  useEffect(() => {
    const element = scroller.current
    const showLatest = () => {
      setGraphWidth(Math.max(1, element.firstElementChild.clientWidth))
      element.scrollLeft = element.scrollWidth
    }
    showLatest()
    const observer = new ResizeObserver(showLatest)
    observer.observe(element)
    observer.observe(element.firstElementChild)
    return () => observer.disconnect()
  }, [points])
  const numbers = points.flatMap(p => p.secondary == null ? [p.value] : [p.value, p.secondary])
  const low = numbers.reduce((a, b) => Math.min(a, b), Infinity), high = numbers.reduce((a, b) => Math.max(a, b), -Infinity)
  const start = Date.parse(points[0].at), end = Date.parse(points.at(-1).at)
  const x = point => start === end ? graphWidth / 2 : 8 + (Date.parse(point.at) - start) / (end - start) * (graphWidth - 16)
  const y = value => high === low ? 32 : 56 - (value - low) / (high - low) * 44
  const latest = points.at(-1)
  return <div className="mimic-trend">
    <div ref={scroller} className="mimic-trend-scroll" tabIndex={0} role="region" aria-label={`${label} graph, scroll horizontally for earlier readings`}>
    <div className="mimic-trend-track" style={{ '--trend-mobile-width': `${Math.max(280, Math.min(points.length * 14, 1200))}px` }}>
    <svg viewBox={`0 0 ${graphWidth} 64`} preserveAspectRatio="none" role="img" aria-label={`${label} trend. Recorded range ${format(low)} to ${format(high)}`}>
      <line x1="8" x2={graphWidth - 8} y1="56" y2="56" stroke="currentColor" opacity=".15" />
      <polyline points={points.map(p => `${x(p)},${y(p.value)}`).join(' ')} fill="none" stroke="currentColor" strokeWidth="1.8" />
      {latest.secondary != null && <polyline points={points.map(p => `${x(p)},${y(p.secondary)}`).join(' ')} fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity=".6" />}
      <circle cx={x(latest)} cy={y(latest.value)} r="4"><title>{latest.at.replace('T',' ')} · {format(latest.value)}{latest.secondary != null ? ` / ${format(latest.secondary)}` : ''}</title></circle>
      {latest.secondary != null && <circle cx={x(latest)} cy={y(latest.secondary)} r="3" opacity=".6" />}
    </svg>
    <div className="mimic-trend-dates"><small>{points[0].at.replace('T',' ').slice(5,16)}</small><small>{latest.at.replace('T',' ').slice(5,16)}</small></div>
    </div>
    </div>
    <small>{latest.secondary == null ? `Recorded range ${format(low)}–${format(high)}` : <>
      Sys {format(points.reduce((a,p) => Math.min(a,p.value), Infinity))}–{format(points.reduce((a,p) => Math.max(a,p.value), -Infinity))}
      {' · '}Dia {format(points.reduce((a,p) => Math.min(a,p.secondary), Infinity))}–{format(points.reduce((a,p) => Math.max(a,p.secondary), -Infinity))}
    </>}</small>
  </div>
}
export default function MimicOverview({ values, onOpen }) {
  const seriesList = useMemo(() => vitalSeries(values), [values])
  return <section className="mimic-overview" aria-labelledby="mimic-overview-title">
    <h2 id="mimic-overview-title">Overview</h2>
    <div className="mimic-vitals">{seriesList.map(series => {
      const last = series.points.at(-1)
      return <article key={series.label} className="mimic-vital">
        <div className="mimic-vital-summary"><h3>{series.label}</h3>
        <div className="mimic-vital-value">{last ? <button onClick={() => onOpen(last.source, last.page)} title={`Open source · ${last.at.replace('T',' ')}${last.method ? ` · ${last.method}` : ''}`}>
          {format(last.value)}{last.secondary != null ? ` / ${format(last.secondary)}` : ''}</button> : '—'} <small>{series.unit}</small></div>
        {last ? <time title={last.at}>{last.at.replace('T',' ').slice(0,16)}</time> : <small>No recorded value</small>}
        </div>
        {last && <Trend points={series.points} label={series.label} />}
      </article>
    })}</div>
  </section>
}
