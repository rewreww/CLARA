const key = value => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '')
export function admissionDates(data) {
  return (data?.admissions || []).map(item => {
    const overview = data.overview.find(row => row.admission === item.id)
    const metadata = overview ? JSON.parse(overview.metadata) : {}
    const details = metadata['Admission details'] || []
    const raw = details.flatMap(row => Object.entries(row))
      .find(([label, value]) => key(label) === 'admissiondateandtimetype' && /\d{4}-\d{2}-\d{2}/.test(value))?.[1]
    const date = raw?.match(/\d{4}-\d{2}-\d{2}/)?.[0]
    return { ...item, date }
  }).sort((a, b) => (a.date || '9999').localeCompare(b.date || '9999') || a.id.localeCompare(b.id))
}
export function dateParts(date) {
  if (!date) return null
  const [year, month, day] = date.split('-')
  return { month: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(month) - 1], day: Number(day), year: year.slice(-2) }
}
export function vitalSeries(values = []) {
  const byLabel = name => values.filter(row => key(row.label) === name && Number.isFinite(row.value) && row.at)
  const pressure = ['noninvasive', 'arterial'].map(kind => {
    const dia = new Map(byLabel(kind + 'bloodpressurediastolic').filter(r => key(r.unit) === 'mmhg').map(r => [r.at, r]))
    return byLabel(kind + 'bloodpressuresystolic').filter(r => key(r.unit) === 'mmhg' && dia.has(r.at))
      .map(r => ({ ...r, secondary: dia.get(r.at).value, method: kind === 'arterial' ? 'Arterial' : 'Non-invasive' }))
  })
  const temperature = [...byLabel('temperaturecelsius').filter(r => ['c','degc'].includes(key(r.unit))),
    ...byLabel('temperaturefahrenheit').filter(r => ['f','degf'].includes(key(r.unit))).map(r => ({ ...r, value: (r.value - 32) * 5 / 9 }))]
  const series = [
    { label: 'Blood pressure', unit: 'mmHg', points: pressure[0].length ? pressure[0] : pressure[1] },
    { label: 'Heart rate', unit: 'bpm', points: byLabel('heartrate').filter(r => ['bpm','beatsmin'].includes(key(r.unit))) },
    { label: 'Respiration', unit: '/min', points: byLabel('respiratoryrate').filter(r => ['inspmin','breathsmin','min'].includes(key(r.unit))) },
    { label: 'Oxygen', unit: '%', points: byLabel('o2saturationpulseoxymetry').filter(r => String(r.unit).trim() === '%') },
    { label: 'Temperature', unit: '°C', points: temperature },
  ]
  return series.map(series => ({ ...series, points: series.points.sort((a, b) => a.at.localeCompare(b.at)) }))
}


/**
 * Only read demographic cells from overview PDFs belonging to this admission.
 * Never infer values from admission IDs, shifted dates, or another admission.
 * Disagreeing overview PDFs leave the corresponding field unavailable.
 */
export function admissionDemographics(summary, patientId, admissionId) {
  if (!patientId || !admissionId || summary?.patient !== patientId) return null
  const overview = (summary.overview || []).filter(row =>
    row.admission === (admissionId === 'unlinked' ? null : admissionId))
  const definitions = [
    { label: 'Age (reference year)', keys: ['anchorage', 'ageatreferenceyear', 'ageinreferenceyear', 'patientage', 'age'] },
    { label: 'Sex', keys: ['sex', 'gender', 'patientsex', 'patientgender'] },
    { label: 'Race / ethnicity', keys: ['race', 'ethnicity', 'raceethnicity', 'patientrace'] },
    { label: 'Insurance', keys: ['insurance', 'insurancetype', 'insuranceprovider'] },
    { label: 'Marital status', keys: ['maritalstatus'] },
    { label: 'Language', keys: ['language', 'preferredlanguage'] },
  ]
  const data = new Map()
  for (const row of overview) {
    let metadata
    try { metadata = typeof row.metadata === 'string' ? JSON.parse(row.metadata) : row.metadata }
    catch { continue }
    if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) continue
    const normalized = new Map(Object.entries(metadata).filter(([, value]) => typeof value === 'string')
      .map(([name, value]) => [key(name), value.trim()]))
    for (const definition of definitions) {
      const value = definition.keys.map(name => normalized.get(name))
        .find(value => value && !/^(?:unknown|not recorded|n\/a|na|null|none|-)$/i.test(value))
      if (!value) continue
      const values = data.get(definition.label) || new Set()
      values.add(value)
      data.set(definition.label, values)
    }
  }
  return {
    admission: admissionId,
    fields: definitions.map(({ label }) => ({
      label,
      value: data.get(label)?.size === 1 ? [...data.get(label)][0] : null,
    })),
    sources: overview.map(row => row.source).filter(Boolean),
  }
}
