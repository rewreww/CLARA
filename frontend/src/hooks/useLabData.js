import { useState, useCallback, useEffect, useRef } from 'react'
import { LABS_URL } from '../constants'
import { createLatestRequestGuard } from '../lib/latestRequest'

export function useLabData() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const requests = useRef(null)
  if (!requests.current) requests.current = createLatestRequestGuard()

  useEffect(() => () => requests.current.invalidate(), [])

  const load = useCallback(async (section, patientId, options = {}) => {
    if (!patientId) {
      requests.current.invalidate()
      setData(null)
      setError(null)
      setLoading(false)
      return
    }

    const request = requests.current.begin()
    const silent = options.silent === true
    if (!silent) setData(null)
    setError(null)
    if (!silent) setLoading(true)

    try {
      if (['chemistry', 'hematology', 'microscopy'].includes(section)) {
        const res = await fetch(`${LABS_URL}/${section}-results`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ patient: patientId, labs: section }),
          signal: request.signal,
        })
        if (!res.ok) throw new Error(`Server error ${res.status}`)
        const json = await res.json()
        if (!request.isCurrent()) return
        setData({ type: section, results: json.results || [] })

      } else if (section === 'discharge') {
        const res = await fetch(`${LABS_URL}/discharge-parsed`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ patient: patientId }),
          signal: request.signal,
        })
        if (!res.ok) throw new Error(`Server error ${res.status}`)
        const json = await res.json()
        if (!request.isCurrent()) return
        setData({
          type: 'discharge',
          found: json.found,
          header: json.header || {},
          condition_discharge: json.condition_discharge,
          chief_complaint: json.chief_complaint,
          admitting_dx: json.admitting_dx,
          final_dx: json.final_dx,
          hpi: json.hpi,
          pmh: json.pmh,
          physical_exam: json.physical_exam,
          laboratory_data: json.laboratory_data,
          labs: json.labs || [],
          hospital_course: json.hospital_course || [],
          raw_text: json.raw_text,
        })

      } else if (request.isCurrent()) {
        setData(null)
      }
    } catch (e) {
      if (request.isCurrent() && e.name !== 'AbortError') setError(e.message)
    } finally {
      if (request.isCurrent() && !silent) setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    requests.current.invalidate()
    setData(null)
    setError(null)
    setLoading(false)
  }, [])

  return { data, loading, error, load, reset }
}
