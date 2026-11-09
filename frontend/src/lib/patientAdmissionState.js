// Only use admission metadata belonging to the currently highlighted patient.
export function currentAdmissionSummary(summary, patientId) {
  if (!summary || !patientId || summary.patientId !== patientId) return null
  return summary.data ?? null
}
