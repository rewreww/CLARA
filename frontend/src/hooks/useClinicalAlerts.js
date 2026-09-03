import { useState } from 'react'
import { LLM_URL } from '../constants'

export function useClinicalAlerts() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function check(patientId) {
    setLoading(true)
    setError(null)
    setData(null)
    try {
      const response = await fetch(`${LLM_URL}/clinical-alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient_id: patientId }),
      })
      if (!response.ok) throw new Error(`Clinical alerts returned ${response.status}`)
      setData(await response.json())
    } catch (err) {
      setError(err.message || 'Unable to check clinical alerts.')
    } finally {
      setLoading(false)
    }
  }

  return { data, loading, error, check }
}
