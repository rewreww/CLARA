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
