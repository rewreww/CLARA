import { useState } from 'react'

const URL = '/api/labs'

export function useGuidelines() {
  const [data,        setData]        = useState(null)
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState(null)
  const [queryResult, setQueryResult] = useState(null)
  const [querying,    setQuerying]    = useState(false)

  async function check(patientId) {
    setLoading(true); setError(null); setData(null)
    try {
      const r = await fetch(`${URL}/guidelines-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient: patientId }),
      })
      if (!r.ok) throw new Error(`Server error ${r.status}`)
      setData(await r.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function query(question, diagnosisHint = null) {
    setQuerying(true)
    try {
      const r = await fetch(`${URL}/guidelines-query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, diagnosis_hint: diagnosisHint }),
      })
      if (!r.ok) throw new Error(`Server error ${r.status}`)
      setQueryResult(await r.json())
    } catch (e) {
      setQueryResult({ error: e.message, chunks: [] })
    } finally {
      setQuerying(false)
    }
  }

  function reset() { setData(null); setError(null); setQueryResult(null) }

  return { data, loading, error, check, query, querying, queryResult, reset }
}