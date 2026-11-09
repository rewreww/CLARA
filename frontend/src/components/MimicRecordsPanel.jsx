import { useEffect, useRef, useState } from 'react'
import MimicOverview from './MimicOverview'
import { admissionDates, admissionDemographics, dateParts } from '../lib/mimicOverview'
import { LABS_URL } from '../constants'
import PdfPreview from './PdfPreview'

export const MIMIC_CATEGORIES = {
  overview: 'Overview', chemistry: 'Chemistry', hematology: 'Hematology', blood_gas: 'Blood gas',
  diagnoses: 'Diagnoses', prescriptions: 'Prescriptions', medication_administration: 'Medication administration',
  microbiology: 'Microbiology', measurements: 'Measurements', icu_records: 'ICU records / vitals',
  procedures: 'Procedures', orders: 'Provider orders', care_movements: 'Care movements', administrative: 'Administrative',
}

export function MimicAdmissionSelector({ patient, admission, onChange, refreshKey }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [csvDemographics, setCsvDemographics] = useState(null)
  const [demographicsError, setDemographicsError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    setData(null); setError('')
    fetch(`${LABS_URL}/${encodeURIComponent(patient.id)}/mimic/summary`, { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error('Unable to load admissions'); return r.json() })
      .then(result => {
        if (controller.signal.aborted) return
        if (result.patient !== patient.id) throw new Error('Patient summary did not match the selected patient')
        setData(result)
      }).catch(e => { if (e.name !== 'AbortError' && !controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [patient.id, refreshKey])
  useEffect(() => {
    setCsvDemographics(null)
    setDemographicsError('')
    if (!/^\\d{8}$/.test(admission || '')) return
    const controller = new AbortController()
    fetch(`${LABS_URL}/${encodeURIComponent(patient.id)}/mimic/demographics?${new URLSearchParams({ admission })}`,
      { signal: controller.signal })
      .then(async response => {
        if (!response.ok) {
          const body = await response.json().catch(() => null)
          const reason = typeof body?.error === 'string' ? body.error : 'Unable to load CSV demographics.'
          throw new Error(`${reason} (HTTP ${response.status})`)
        }
        return response.json()
      })
      .then(result => {
        if (controller.signal.aborted) return
        if (result.patient !== patient.id || result.admission !== admission || !Array.isArray(result.fields)) {
          throw new Error('Demographics response does not match the selected patient and admission.')
        }
        setCsvDemographics({ scope: `${patient.id}/${admission}`, fields: result.fields })
      })
      .catch(e => {
        if (!controller.signal.aborted) {
          setDemographicsError(e.message === 'Failed to fetch'
            ? 'Cannot reach the demographics backend. Restart CLARA after pulling backend updates.'
            : e.message)
        }
      })
    return () => controller.abort()
  }, [patient.id, admission, refreshKey])
  const strip = useRef(null)
  const drag = useRef(null)
  const current = data?.patient === patient.id ? data : null
  const dates = admissionDates(current)
  const pdfDemographics = admissionDemographics(current, patient.id, admission)
  const csvCurrent = csvDemographics?.scope === `${patient.id}/${admission}` ? csvDemographics : null
  const demographics = csvCurrent || pdfDemographics
  return <>
  <div className="mimic-date-navigation">
    <button aria-label="Earlier admission dates" onClick={() => strip.current.scrollBy({ left: -240, behavior: 'smooth' })}>‹</button>
    <div ref={strip} className="mimic-date-strip" aria-label="Admission dates"
      onPointerDown={e => { if (e.pointerType === 'mouse') drag.current = { x: e.clientX, scroll: strip.current.scrollLeft, moved: false } }}
      onPointerMove={e => { if (drag.current && e.buttons === 1) { const distance = e.clientX - drag.current.x; if (Math.abs(distance) > 5) drag.current.moved = true; strip.current.scrollLeft = drag.current.scroll - distance } }}
      onPointerLeave={() => { drag.current = null }}
      onClickCapture={e => { if (drag.current?.moved) { e.preventDefault(); e.stopPropagation() } drag.current = null }}>
      {dates.map(item => {
        const parts = dateParts(item.date)
        return <button key={item.id} aria-pressed={admission === item.id}
          aria-label={item.date ? `Admission ${item.date}, ${item.id}` : item.id === 'unlinked' ? 'Unlinked records' : `Undated admission ${item.id}`}
          title={item.date ? `${item.date} · ${item.id}` : item.id}
          onClick={() => onChange(item.id)}>{parts ? <><span>{parts.month}</span><strong>{parts.day}</strong><span>{parts.year}</span></> : <span>{item.id === 'unlinked' ? 'Unlinked' : 'Undated'}</span>}</button>
      })}
      {!data && !error && <span role="status">Loading dates…</span>}
    </div>
    <button aria-label="Later admission dates" onClick={() => strip.current.scrollBy({ left: 240, behavior: 'smooth' })}>›</button>
    {error && <span role="alert">{error}</span>}
  </div>
  {admission && <section className="mimic-demographics" aria-label="Selected admission demographics">
    <div className="mimic-demographics-heading">
      <h2>Demographics</h2>
      <span>{admission === 'unlinked' ? 'Unlinked records' : `Admission ${admission}`}</span>
    </div>
    {!current && !error ? <p role="status">Loading demographic information…</p>
      : error ? <p role="alert">Demographics could not be loaded for this patient.</p>
      : demographics ? <>
        <dl className="mimic-demographics-grid">
          {demographics.fields.map(field => <div key={field.label}>
            <dt>{field.label}</dt>
            <dd>{field.value || 'Not recorded'}</dd>
          </div>)}
        </dl>
        <p className="mimic-demographics-note">{csvCurrent
          ? 'Source: patient-specific MIMIC-IV CSV exports, matched by subject ID and admission ID. Age is the reference-year age.'
          : 'Source: selected admission overview PDF only. CSV demographics have not been loaded.'}</p>
        {demographicsError && admission !== 'unlinked' &&
          <p className="mimic-demographics-error" role="alert">CSV demographics unavailable: {demographicsError}</p>}
      </> : <p>No demographic information available for this admission.</p>}
  </section>}
  </>
}

export default function MimicRecordsPanel({ patient, admission, activeSection, onSelectSection, refreshKey, onRefresh, onAdmissionChange }) {
  const [data, setData] = useState(null)
  const [vitals, setVitals] = useState(null)
  const [vitalError, setVitalError] = useState('')
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [mode, setMode] = useState('records')
  const [source, setSource] = useState(null)
  const category = activeSection !== 'overview' && MIMIC_CATEGORIES[activeSection] ? activeSection : 'chemistry'
  const scope = `${patient.id}/${admission}`
  const requestKey = `${scope}/${category}/${mode}/${page}/${mode === 'records' ? search : ''}`
  const currentVitals = vitals?.scope === scope ? vitals.values : []
  useEffect(() => {
    setVitalError(''); setVitals(null)
    if (!admission) return
    const controller = new AbortController()
    fetch(`${LABS_URL}/${encodeURIComponent(patient.id)}/mimic/vitals?${new URLSearchParams({ admission })}`, { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error('Unable to load vitals'); return r.json() })
      .then(result => setVitals({ scope, values: result.values }))
      .catch(e => { if (e.name !== 'AbortError') setVitalError(e.message) })
    return () => controller.abort()
  }, [patient.id, admission, refreshKey])
  useEffect(() => { setPage(1); setSource(null); setQuery(''); setSearch('') }, [patient.id, admission, category, mode])
  useEffect(() => {
    setData(null); setError('')
    if (!admission) return
    const controller = new AbortController()
    const params = new URLSearchParams({ admission, category, page: String(page) })
    if (mode === 'records' && search) params.set('search', search)
    fetch(`${LABS_URL}/${encodeURIComponent(patient.id)}/mimic/${mode}?${params}`, { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(`Unable to load ${mode === 'documents' ? 'documents' : 'results'} (HTTP ${response.status}).`)
        return response.json()
      })
      .then(result => {
        if (controller.signal.aborted) return
        if (!result || typeof result !== 'object' || !Array.isArray(result[mode === 'documents' ? 'documents' : 'rows'])) {
          throw new Error(`The server returned an unexpected ${mode === 'documents' ? 'documents' : 'results'} response.`)
        }
        setData({ ...result, scope, requestKey: `${scope}/${category}/${mode}/${page}/${mode === 'records' ? search : ''}` })
      })
      .catch(e => { if (e.name !== 'AbortError' && !controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [patient.id, admission, category, mode, page, search, refreshKey])
  function open(source, page = 1) { setSource({ type: 'patient_pdf', source, page, title: source.split('/').pop() }) }
  return <div className="mimic-workspace">
    <header><h1>{patient.name}</h1><button onClick={onRefresh}>Refresh records</button></header>
    <MimicAdmissionSelector key={patient.id} patient={patient} admission={admission} onChange={onAdmissionChange} refreshKey={refreshKey} />
    <div className={`mimic-admission-content ${admission && ((!vitals && !vitalError) || (!data && !error)) ? 'is-retrieving' : ''}`} aria-busy={!!admission && ((!vitals && !vitalError) || (!data && !error))}>
    <MimicOverview values={currentVitals} onOpen={open} />
    {vitalError && <p role="alert">{vitalError}</p>}
    <nav className="mimic-categories" aria-label="MIMIC record categories">
      {Object.entries(MIMIC_CATEGORIES).filter(([key]) => key !== 'overview').map(([key, title]) => <button key={key} aria-pressed={category === key}
        onClick={() => { setPage(1); onSelectSection(key) }}>{title}</button>)}
    </nav>
    {!admission ? <p>Choose a date to view the record.</p> : <>
      <div className="mimic-toolbar">
        <button aria-pressed={mode === 'records'} onClick={() => setMode('records')}>Results</button>
        <button aria-pressed={mode === 'documents'} onClick={() => setMode('documents')}>Documents</button>
        {mode === 'records' && <form onSubmit={e => { e.preventDefault(); setPage(1); setSearch(query) }}>
          <input aria-label="Search extracted rows" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search this category" maxLength={120} />
          <button type="submit">Search</button>
        </form>}
      </div>
      {error ? <p role="alert">{error}</p> : !data || data.requestKey !== requestKey ? <p role="status">Loading…</p> : <>
        {mode === 'records' ? <RecordTables rows={data.rows} onOpen={open} groupByTime={category === 'chemistry'} /> : <ul className="mimic-documents">{data.documents.map((doc, index) => <li key={`${doc.source || 'document'}-${index}`}><button disabled={!doc.source} onClick={() => open(doc.source)}>{doc.source || 'Unnamed PDF'}</button><span>{doc.pages ?? 'Unknown'} pages</span></li>)}</ul>}
        {data.total === 0 && <p>No extracted {mode === 'records' ? 'rows' : 'PDFs'} in this category and admission.</p>}
        <div className="mimic-toolbar"><button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</button>
          <span>{data.page} / {Math.max(1, Math.ceil(data.total / 50))}</span>
          <button disabled={page * 50 >= data.total} onClick={() => setPage(p => p + 1)}>Next</button></div>
      </>}
    </>}
    </div>
    {source && <aside className="mimic-preview"><button onClick={() => setSource(null)}>Close PDF</button><PdfPreview source={source} patientId={patient.id} /></aside>}
  </div>
}

function RecordTables({ rows, onOpen, groupByTime = false }) {
  const groups = new Map()
  for (const row of rows) {
    const cells = JSON.parse(row.cells)
    // Keep unknown timestamps separate by document instead of implying that
    // undated results were recorded together.
    const id = JSON.stringify([groupByTime ? row.observed_at || row.source : null, Object.keys(cells)])
    if (!groups.has(id)) groups.set(id, { headers: Object.keys(cells), rows: [],
      timestamp: row.observed_at,
      hasDate: groupByTime || Object.keys(cells).some(h => /date|time/i.test(h)) })
    groups.get(id).rows.push({ ...row, cells })
  }
  return <div className="mimic-tables">{[...groups.entries()].map(([key, group]) => <div key={key} className="mimic-table-scroll" tabIndex={0} aria-label="Patient results">
    <table>
      {groupByTime && <caption className="mimic-time-heading">{group.timestamp ? <time dateTime={group.timestamp}>{group.timestamp.replace('T', ' ')}</time> : 'Time not recorded'}</caption>}
      <thead><tr>{!group.hasDate && <th>Date</th>}{group.headers.map(header => <th key={header}>{header.replaceAll('\n', ' ')}</th>)}<th>Source</th></tr></thead>
      <tbody>{group.rows.map(row => <tr key={row.id}>
        {!group.hasDate && <td>{row.observed_at?.replace('T', ' ') || '—'}</td>}
        {group.headers.map(header => <td key={header}>{row.cells[header] || '—'}</td>)}
        <td><button onClick={() => onOpen(row.source, row.page)} aria-label={`Open source PDF, page ${row.page}`}>PDF ↗</button></td>
      </tr>)}</tbody></table>
  </div>)}</div>
}
