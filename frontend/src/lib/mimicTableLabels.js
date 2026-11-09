// Labels are derived only from explicit PDF source folders and row cells.
// Never infer a specimen (blood, urine, etc.) from a test name or category alone.
const CATEGORY_FOLDERS = {
  chemistry: 'Chemistry', hematology: 'Hematology', blood_gas: 'Blood_Gas',
  diagnoses: 'Diagnoses', prescriptions: 'Prescriptions',
  medication_administration: 'Medication_Administration', microbiology: 'Microbiology',
  measurements: 'Other_Measurements', icu_records: 'ICU_Records',
  procedures: 'Procedures', orders: 'Provider_Orders',
  care_movements: 'Care_Movements', administrative: 'Administrative',
}
const DISPLAY_NAMES = {
  labevents: 'Laboratory results',
  chartevents: 'Chart observations',
  outputevents: 'Output events',
  inputevents: 'Input events',
  datetimeevents: 'Dated ICU events',
  procedureevents: 'ICU procedures',
  microbiologyevents: 'Microbiology results',
  prescriptions: 'Prescriptions',
  pharmacy: 'Pharmacy orders',
  emar: 'Medication administration',
  emar_detail: 'Medication administration details',
  diagnosesicd: 'Diagnoses',
  proceduresicd: 'Procedures',
  emardetail: 'Medication administration details',
  transfers: 'Transfers',
  services: 'Clinical services',
  admissions: 'Admission details',
  patients: 'Patient information',
}
const norm = value => String(value || '').trim().toLowerCase().replace(/[^a-z0-9]/g, '')
const readable = value => String(value || '').replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim()
  .replace(/\b\w/g, letter => letter.toUpperCase())
const SPECIMEN_KEYS = new Set(['specimen', 'specimentype', 'specimendescription', 'fluid', 'fluidtype', 'bodysite'])
function specimenFromCells(cells) {
  for (const [field, value] of Object.entries(cells || {})) {
    if (SPECIMEN_KEYS.has(norm(field)) && typeof value === 'string' && value.trim()) return value.trim()
  }
  return null
}
export function recordTableLabel(rows, category) {
  if (!Array.isArray(rows) || !rows.length) return 'Records'
  const first = rows[0]
  const source = String(first.source || '').replaceAll('\\', '/').split('/').filter(Boolean)
  const categoryFolder = CATEGORY_FOLDERS[category]
  const index = source.findIndex(segment => segment.toLowerCase() === categoryFolder?.toLowerCase())
  const child = index >= 0 ? source[index + 1] : null
  const isLab = ['chemistry', 'hematology', 'blood_gas'].includes(category)
  const sourceSpecimen = isLab && child && !/\.pdf$/i.test(child) ? child : null
  const explicitSpecimens = [...new Set(rows.map(row => specimenFromCells(row.cells)).filter(Boolean))]
  const explicit = explicitSpecimens.length === 1 && rows.every(row => specimenFromCells(row.cells) === explicitSpecimens[0])
    ? explicitSpecimens[0] : null
  const specimen = sourceSpecimen || explicit
  if (specimen) {
    const title = readable(specimen)
    return isLab ? `${title} · Laboratory results` : `${title} · ${DISPLAY_NAMES[norm(first.record_type)] || readable(first.record_type || category)}`
  }
  const type = norm(first.record_type)
  if (DISPLAY_NAMES[type]) return DISPLAY_NAMES[type]
  if (!isLab && child && !/\.pdf$/i.test(child)) return readable(child)
  return readable(first.record_type || category) || 'Records'
}
