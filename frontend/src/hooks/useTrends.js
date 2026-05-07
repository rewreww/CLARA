import { useState, useCallback } from 'react'
import { LABS_URL } from '../constants'

export function useTrends() {
  const [data,    setData]    = useState(null)   // { patient, lab_type, timeline: [{date, results}] }
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const load = useCallback(async (patientId, labType = 'chemistry') => {
    if (!patientId) return
    setData(null)
    setError(null)
    setLoading(true)

    try {
      const res = await fetch(`${LABS_URL}/labs-timeline`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ patient: patientId, lab_type: labType }),
      })

      if (res.status === 404) {
        setError('no_date_folders')
        setLoading(false)
        return
      }

      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const json = await res.json()
      setData(json)
    } catch (e) {
      setError(e.message)
    }

    setLoading(false)
  }, [])

  const reset = useCallback(() => {
    setData(null)
    setError(null)
  }, [])

  return { data, loading, error, load, reset }
}