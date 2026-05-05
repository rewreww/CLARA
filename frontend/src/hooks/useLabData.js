import { useState, useCallback } from 'react'
import { LABS_URL } from '../constants'

export function useLabData() {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const load = useCallback(async (section, patientId) => {
    if (!patientId) return
    setData(null)
    setError(null)
    setLoading(true)

    try {
      if (['chemistry', 'hematology', 'microscopy'].includes(section)) {
        const res = await fetch(`${LABS_URL}/${section}-results`, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ patient: patientId, labs: section }),
        })
        if (!res.ok) throw new Error(`Server error ${res.status}`)
        const json = await res.json()
        setData({ type: section, results: json.results || [] })

      } else if (section === 'discharge') {
        const res = await fetch(`${LABS_URL}/categorize`, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ patient: patientId, labs: 'labs' }),
        })
        if (!res.ok) throw new Error(`Server error ${res.status}`)
        const json = await res.json()
        setData({ type: 'discharge', text: json.discharge || '' })

      } else {
        setData(null)
      }
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
