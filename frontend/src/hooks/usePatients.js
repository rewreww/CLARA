import { useState, useEffect } from 'react'

const LABS_URL = '/api/labs'

export function usePatients() {
  const [patients, setPatients] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)

  useEffect(() => {
    fetch(`${LABS_URL}/patients`)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.json()
      })
      .then(d => setPatients(d.patients || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return { patients, loading, error }
}