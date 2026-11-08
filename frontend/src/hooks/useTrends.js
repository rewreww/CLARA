import { useState, useCallback, useEffect, useRef } from 'react'
import { LABS_URL } from '../constants'
import { createLatestRequestGuard } from '../lib/latestRequest'

export function useTrends() {
  const [data, setData] = useState(null) // { patient, lab_type, timeline: [{date, results}] }
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const requests = useRef(null)
  if (!requests.current) requests.current = createLatestRequestGuard()

  useEffect(() => () => requests.current.invalidate(), [])

  const load = useCallback(async (patientId, labType = 'chemistry') => {
    if (!patientId) {
      requests.current.invalidate()
      setData(null)
      setError(null)
      setLoading(false)
      return
    }

    const request = requests.current.begin()
    setData(null)
    setError(null)
    setLoading(true)

    try {
      const res = await fetch(`${LABS_URL}/labs-timeline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient: patientId, lab_type: labType }),
        signal: request.signal,
      })

      if (!request.isCurrent()) return
      if (res.status === 404) {
        setError('no_date_folders')
        return
      }
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const json = await res.json()
      if (request.isCurrent()) setData(json)
    } catch (e) {
      if (request.isCurrent() && e.name !== 'AbortError') setError(e.message)
    } finally {
      if (request.isCurrent()) setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    requests.current.invalidate()
    setData(null)
    setError(null)
    setLoading(false)
  }, [])

  return { data, loading, error, load, reset }
}
