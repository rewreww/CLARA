import { useCallback, useEffect, useRef, useState } from 'react'
import { BACKEND_URL } from '../constants'

const PATIENT_DATA_UPDATED_EVENT = 'clara:patient-data-updated'

function isPdfSavedEvent(event) {
  return event.level === 'success' && /new data successfully saved/i.test(event.message)
}

function isDataChangedEvent(event) {
  return isPdfSavedEvent(event) || /deleted pdf data removed from database/i.test(event.message)
}

function emitPatientDataUpdated(event) {
  if (!isDataChangedEvent(event)) return
  window.dispatchEvent(new CustomEvent(PATIENT_DATA_UPDATED_EVENT, {
    detail: {
      patientId: event.patientId,
      fileName: event.fileName,
      sequence: event.sequence,
    },
  }))
}

export function useSyncProgress() {
  const [error, setError] = useState(null)
  const lastSequence = useRef(0)
  const initialized = useRef(false)
  const processedSequences = useRef(new Set())

  const mergeEvents = useCallback((incoming) => {
    if (!incoming?.length) return
    const normalized = incoming.map(event => ({
      sequence: event.sequence ?? event.Sequence,
      level: event.level ?? event.Level ?? 'info',
      message: event.message ?? event.Message ?? '',
      patientId: event.patientId ?? event.PatientId,
      fileName: event.fileName ?? event.FileName,
      timestampUtc: event.timestampUtc ?? event.TimestampUtc,
    })).filter(event => event.sequence && event.message)

    if (!normalized.length) return
    lastSequence.current = Math.max(lastSequence.current, ...normalized.map(event => event.sequence))

    normalized.forEach(event => {
      if (processedSequences.current.has(event.sequence)) return
      processedSequences.current.add(event.sequence)
      emitPatientDataUpdated(event)
    })
  }, [])

  const poll = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/pdfingestion/sync/status?after=${lastSequence.current}`)
      if (!res.ok) throw new Error(`Sync status ${res.status}`)
      const json = await res.json()
      const incoming = json.events || json.Events || []
      if (!initialized.current) {
        const sequences = incoming
          .map(event => event.sequence ?? event.Sequence)
          .filter(Boolean)
        if (sequences.length) {
          lastSequence.current = Math.max(lastSequence.current, ...sequences)
        }
        initialized.current = true
      } else {
        mergeEvents(incoming)
      }
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }, [mergeEvents])

  useEffect(() => {
    poll()
    const id = window.setInterval(poll, 2000)
    return () => window.clearInterval(id)
  }, [poll])

  return { error }
}
