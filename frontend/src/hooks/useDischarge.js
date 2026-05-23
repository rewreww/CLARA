import { useState, useEffect } from 'react'

const LABS_URL = '/api/labs'

export function useDischarge(patientId) {
  const [discharge, setDischarge] = useState(null)
  const [loading,   setLoading]   = useState(false)

  useEffect(() => {
    if (!patientId) { setDischarge(null); return }
    setLoading(true)
    fetch(`${LABS_URL}/discharge-parsed`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ patient: patientId }),
    })
      .then(r => r.json())
      .then(d => setDischarge(d.found ? d : null))
      .catch(() => setDischarge(null))
      .finally(() => setLoading(false))
  }, [patientId])

  return { discharge, loading }
}