import { useState, useEffect } from 'react'

const ML_URL = '/api/ml'

export function useEcgRisk() {
  const [patients, setPatients] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)

  useEffect(() => {
    fetch(`${ML_URL}/demo-patients`)
      .then(r => {
        if (!r.ok) throw new Error(`ML service offline (${r.status})`)
        return r.json()
      })
      .then(d => {
        if (!Array.isArray(d)) throw new Error('Unexpected response from ML service')
        setPatients(d)
      })
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
