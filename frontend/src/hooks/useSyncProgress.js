import { useCallback, useEffect, useRef, useState } from 'react'
import { BACKEND_URL } from '../constants'

const MAX_EVENTS = 6

export function useSyncProgress(patientId) {
  const [events, setEvents] = useState([])
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState(null)
  const lastSequence = useRef(0)

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
    setEvents(current => [...current, ...normalized].slice(-MAX_EVENTS))
  }, [])

  const poll = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/pdfingestion/sync/status?after=${lastSequence.current}`)
      if (!res.ok) throw new Error(`Sync status ${res.status}`)
      const json = await res.json()
      mergeEvents(json.events || json.Events || [])
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

  const triggerSync = useCallback(async () => {
    setSyncing(true)
    setError(null)
    try {
      const res = await fetch(`${BACKEND_URL}/pdfingestion/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folderName: patientId || null }),
      })
      if (!res.ok) throw new Error(`Sync failed ${res.status}`)
      await poll()
    } catch (err) {
      setError(err.message)
      setEvents(current => [...current, {
        sequence: Date.now(),
        level: 'error',
        message: err.message,
        patientId,
      }].slice(-MAX_EVENTS))
    } finally {
      setSyncing(false)
    }
  }, [patientId, poll])

  return { events, syncing, error, triggerSync }
}
