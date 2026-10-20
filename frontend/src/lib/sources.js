import { LABS_URL, LLM_URL } from '../constants.js'

export function sourceDocumentUrl(source, patientId) {
  if (!source?.source) return null
  const query = new URLSearchParams({ source: source.source })
  if (source.type === 'patient_pdf' && patientId) return `${LABS_URL}/${encodeURIComponent(patientId)}/document?${query}`
  if (source.type === 'guideline') return `${LLM_URL}/documents/guideline?${query}`
  return null
}

export function citationPage(source) {
  const page = Number(source?.page)
  return Number.isInteger(page) && page > 0 ? page : null
}
