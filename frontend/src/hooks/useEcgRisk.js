import { useState, useEffect } from 'react'

const ML_URL = '/api/ml'

export function useEcgRisk() {
  const [patients, setPatients] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)

  useEffect(() => {
    fetch(`${ML_URL}/demo-patients`)
      .then(r => r.json())
      .then(d  => setPatients(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function predict(ecgInput) {
    const res = await fetch(`${ML_URL}/predict`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(ecgInput),
    })
    return res.json()
  }

  return { patients, loading, error, predict }
}
