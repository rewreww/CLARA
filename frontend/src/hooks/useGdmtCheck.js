import { useState } from 'react'

export function useGdmtCheck() {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  async function check(patientId) {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch('/api/labs/gdmt-check', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ patient: patientId }),
      })
      if (!r.ok) throw new Error(`Server error ${r.status}`)
      setData(await r.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function reset() { setData(null); setError(null) }

  return { data, loading, error, check, reset }
}