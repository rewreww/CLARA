import { useEffect, useRef, useState } from 'react'
import { CalendarDays, ChevronRight, Search, UserRound, X } from 'lucide-react'
import { LABS_URL } from '../constants'
import { admissionDates } from '../lib/mimicOverview'
import { demoDateText } from '../lib/mimicDemoDates'
import { currentAdmissionSummary } from '../lib/patientAdmissionState'

export default function PatientAdmissionPicker({
  patients, patientsLoading, patientsError, selectedPatient, selectedAdmission,
  onSelect, onClose,
}) {
  const dialogRef = useRef(null)
  const searchRef = useRef(null)
  const [search, setSearch] = useState('')
  const [focusedPatient, setFocusedPatient] = useState(selectedPatient || null)
  const [patientPicked, setPatientPicked] = useState(false)
  const [summary, setSummary] = useState(null)
  const [loadingAdmissions, setLoadingAdmissions] = useState(false)
  const [admissionsError, setAdmissionsError] = useState('')

  useEffect(() => {
    const previouslyFocused = document.activeElement
    searchRef.current?.focus()
    const closeOutside = event => {
      if (dialogRef.current && !dialogRef.current.contains(event.target)
        && !event.target.closest?.('.composer-patient-button')) onClose()
    }
    document.addEventListener('pointerdown', closeOutside)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      if (previouslyFocused?.isConnected) previouslyFocused.focus?.()
    }
  }, [onClose])

  const handlePanelKeyDown = event => {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      onClose()
    }
  }

  useEffect(() => {
    setSummary(null)
    setAdmissionsError('')
    setLoadingAdmissions(false)

    if (!focusedPatient?.id?.startsWith('Patient_')) return

    const controller = new AbortController()
    setLoadingAdmissions(true)

    fetch(`${LABS_URL}/${encodeURIComponent(focusedPatient.id)}/mimic/summary`, {
      signal: controller.signal,
    })
      .then(response => {
        if (!response.ok) throw new Error('Unable to load admission dates.')
        return response.json()
      })
      .then(result => {
        if (controller.signal.aborted) return
        if (result.patient !== focusedPatient.id) throw new Error('Patient summary did not match.')
        setSummary({ patientId: focusedPatient.id, data: result })
      })
      .catch(error => {
        if (!controller.signal.aborted) setAdmissionsError(error.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingAdmissions(false)
      })

    return () => controller.abort()
  }, [focusedPatient?.id])

  const filteredPatients = patients.filter(item =>
    `${item.name || ''} ${item.id || ''}`.toLowerCase().includes(search.trim().toLowerCase())
  )

  // A previously loaded patient's admissions must never appear while switching.
  const currentSummary = currentAdmissionSummary(summary, focusedPatient?.id)
  let admissions = []
  if (currentSummary) {
    try {
      admissions = admissionDates(currentSummary)
    } catch {
      // Keep verified admission IDs visible even if date metadata is malformed.
      // Never guess missing dates.
      admissions = (currentSummary.admissions || [])
        .filter(item => /^(?:\d{8}|unlinked)$/.test(String(item.id || '')))
        .map(item => ({ ...item, date: null }))
    }
  }

  const choose = (patient, admission = '') => {
    onSelect(patient, admission)
    onClose()
  }

  // X confirms an explicitly highlighted patient without choosing an admission.
  // Simply opening and closing the picker must not clear an existing admission.
  const closeFromButton = () => {
    if (patientPicked && focusedPatient) {
      choose(focusedPatient, '')
    } else {
      onClose()
    }
  }

  return (
    <section ref={dialogRef} className="patient-admission-dialog patient-admission-inline"
      aria-label="Patient and admission picker" onKeyDown={handlePanelKeyDown}>
      <div className="patient-admission-shell">
        <header className="patient-admission-header">
          <div>
            <h2 id="patient-admission-title">Choose patient</h2>
            <p>Select a patient, or choose an admission date to scope its clinical records.</p>
          </div>
          <button type="button" className="patient-admission-close" onClick={closeFromButton}
            aria-label="Close patient picker"><X size={18} /></button>
        </header>

        <div className="patient-admission-search">
          <Search size={17} aria-hidden="true" />
          <input ref={searchRef} value={search} onChange={event => setSearch(event.target.value)}
            placeholder="Search patients by name or ID" aria-label="Search patients" />
        </div>

        <div className="patient-admission-columns">
          <section className="patient-admission-patients" aria-label="Patients">
            <div className="patient-admission-column-label">PATIENTS</div>
            <button type="button" className="patient-admission-row"
              onClick={() => choose(null)} aria-label="Continue without a patient">
              <UserRound size={18} /><span className="patient-admission-row-main"><strong>General chat</strong>
                <small>No patient record</small></span>
            </button>
            {patientsLoading && <p className="patient-admission-info" role="status">Loading patients…</p>}
            {patientsError && <p className="patient-admission-info" role="alert">Patient directory unavailable.</p>}
            {!patientsLoading && !patientsError && filteredPatients.length === 0 &&
              <p className="patient-admission-info">No patients match your search.</p>}
            {!patientsLoading && !patientsError && filteredPatients.map(item => (
              <button type="button" key={item.id}
                className={`patient-admission-row ${focusedPatient?.id === item.id ? 'is-selected' : ''}`}
                aria-pressed={focusedPatient?.id === item.id}
                onClick={() => { setFocusedPatient(item); setPatientPicked(true) }}>
                <UserRound size={18} aria-hidden="true" />
                <span className="patient-admission-row-main"><strong>{item.name || item.id}</strong>
                  <small>{item.id}</small></span>
                <ChevronRight size={17} aria-hidden="true" />
              </button>
            ))}
          </section>

          <section className="patient-admission-dates" aria-label="Admissions">
            <div className="patient-admission-column-label">ADMISSION DATES</div>
            {!focusedPatient && <div className="patient-admission-empty">
              <CalendarDays size={25} aria-hidden="true" />
              <p>Select a patient on the left to view admissions.</p>
            </div>}
            {focusedPatient && !focusedPatient.id.startsWith('Patient_') && (
              <div className="patient-admission-legacy">
                <p>This record does not use MIMIC-IV admission dates.</p>
                <button type="button" className="patient-admission-primary"
                  onClick={() => choose(focusedPatient)}>Use this patient</button>
              </div>
            )}
            {focusedPatient?.id?.startsWith('Patient_') && <>
              <p className="patient-admission-scope">Admissions for <strong>{focusedPatient.name || focusedPatient.id}</strong></p>
              {loadingAdmissions && <p className="patient-admission-info" role="status">Loading admission dates…</p>}
              {admissionsError && <p className="patient-admission-info" role="alert">{admissionsError}</p>}
              {!loadingAdmissions && !admissionsError && currentSummary && admissions.length === 0 &&
                <p className="patient-admission-info">No available admissions for this patient.</p>}
              {!loadingAdmissions && !admissionsError && currentSummary && admissions.map(item => (
                <button type="button" key={item.id}
                  className={`patient-admission-date-row ${selectedPatient?.id === focusedPatient.id && selectedAdmission === item.id ? 'is-selected' : ''}`}
                  onClick={() => choose(focusedPatient, item.id)}>
                  <CalendarDays size={18} aria-hidden="true" />
                  <span><strong>{demoDateText(item.date, currentSummary?.demo_date_offset_days) || (item.id === 'unlinked' ? 'Unlinked records' : 'Date unavailable')}</strong>
                    <small>{item.id === 'unlinked' ? 'Records without admission ID' : `Admission ${item.id}`}</small></span>
                  <ChevronRight size={16} aria-hidden="true" />
                </button>
              ))}
            </>}
          </section>
        </div>
      </div>
    </section>
  )
}
