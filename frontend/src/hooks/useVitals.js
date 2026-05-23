import { useState, useEffect } from 'react'

const LABS_URL = '/api/labs'

export function useVitals(patientId) {
  const [vitals,  setVitals]  = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!patientId) { setVitals(null); return }
    setLoading(true)
    fetch(`${LABS_URL}/vitals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient: patientId }),
    })
      .then(r => r.json())
      .then(d => setVitals(d.found ? d : null))
      .catch(() => setVitals(null))
      .finally(() => setLoading(false))
  }, [patientId])

  return { vitals, loading }
}