import { useState, useEffect } from 'react'

const LABS_URL = '/api/labs'

export function useVitals(patientId) {
  const [vitals,   setVitals]   = useState(null)
  const [trends,   setTrends]   = useState(null)
  const [loading,  setLoading]  = useState(false)

  useEffect(() => {
    if (!patientId) { setVitals(null); setTrends(null); return }
    setLoading(true)

    const latest = fetch(`${LABS_URL}/vitals`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ patient: patientId }),
    }).then(r => r.json()).then(d => setVitals(d.found ? d : null)).catch(() => setVitals(null))

    const timeline = fetch(`${LABS_URL}/vitals-timeline`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ patient: patientId }),
    }).then(r => r.json()).then(d => setTrends(d.timeline || [])).catch(() => setTrends(null))

    Promise.all([latest, timeline]).finally(() => setLoading(false))
  }, [patientId])

  return { vitals, trends, loading }
}