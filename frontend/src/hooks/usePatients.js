import { useCallback, useEffect, useState } from 'react'
import { LABS_URL } from '../constants'

export function usePatients() {
  const [patients, setPatients] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`${LABS_URL}/patients`)
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const json = await res.json()
      setPatients(json.patients || [])
    } catch (e) {
      setError(e.message)
      setPatients([])
    }

    setLoading(false)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return { patients, loading, error, reload: load }
}
