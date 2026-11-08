import { useState, useEffect } from 'react'
import { LABS_URL } from '../constants'

export function useVitals(patientId, refreshKey = 0) {
  const [vitals, setVitals] = useState(null)
  const [trends, setTrends] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setVitals(null)
    setTrends(null)
    if (!patientId) {
      setLoading(false)
      return
    }

    let active = true
    const controller = new AbortController()
    setLoading(true)

    const latest = fetch(`${LABS_URL}/vitals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient: patientId }),
      signal: controller.signal,
    })
      .then(r => {
        if (!r.ok) throw new Error(`Server error ${r.status}`)
        return r.json()
      })
      .then(d => { if (active) setVitals(d.found ? d : null) })
      .catch(() => { if (active) setVitals(null) })

    const timeline = fetch(`${LABS_URL}/vitals-timeline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient: patientId }),
      signal: controller.signal,
    })
      .then(r => {
        if (!r.ok) throw new Error(`Server error ${r.status}`)
        return r.json()
      })
      .then(d => { if (active) setTrends(d.timeline || []) })
      .catch(() => { if (active) setTrends(null) })

    Promise.all([latest, timeline]).finally(() => {
      if (active) setLoading(false)
    })

    return () => {
      active = false
      controller.abort()
    }
  }, [patientId, refreshKey])

  return { vitals, trends, loading }
}
