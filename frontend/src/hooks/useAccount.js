import { useCallback, useEffect, useState } from 'react'

const BASE = '/api/backend/account'
async function readResponse(response) {
  let body = null
  try { body = await response.json() } catch {}
  if (!response.ok) throw new Error(body?.error || (response.status === 401 ? 'Invalid credentials or session expired.' : 'Account service unavailable.'))
  return body
}
export async function accountRequest(path, { method = 'GET', data, signal } = {}) {
  const response = await fetch(BASE + path, {
    method, credentials: 'same-origin', cache: 'no-store', signal,
    headers: { ...(data ? { 'Content-Type': 'application/json' } : {}) },
    ...(data ? { body: JSON.stringify(data) } : {}),
  })
  return readResponse(response)
}
export function useAccount() {
  const [state, setState] = useState({ loading: true, enabled: false, user: null, error: '' })
  useEffect(() => {
    // Explicit opt-in avoids disrupting the existing Vercel demo while a local
    // gateway/backend is still on an older deployment. This is not a security
    // boundary: clinical APIs enforce authentication independently.
    if (import.meta.env.VITE_CLARA_AUTH_ENABLED !== 'true') {
      setState({ loading: false, enabled: false, user: null, error: '' })
      return
    }
    let cancelled = false
    const load = async () => {
      try {
        const config = await accountRequest('/config')
        if (cancelled) return
        if (!config.enabled) { setState({ loading: false, enabled: false, user: null, error: '' }); return }
        try {
          const user = await accountRequest('/me')
          if (!cancelled) setState({ loading: false, enabled: true, user, error: '' })
        } catch (err) {
          if (!cancelled) setState({ loading: false, enabled: true, user: null, error: '' })
        }
      } catch {
        if (!cancelled) setState({ loading: false, enabled: false, user: null, error: 'Could not verify CLARA account configuration. Check backend and gateway before continuing.' })
      }
    }
    load()
    return () => { cancelled = true }
  }, [])
  const login = useCallback(async (username, password) => {
    const user = await accountRequest('/login', { method: 'POST', data: { username, password } })
    setState({ loading: false, enabled: true, user, error: '' })
    return user
  }, [])
  const logout = useCallback(async () => {
    try { await accountRequest('/logout', { method: 'POST' }) }
    finally { setState({ loading: false, enabled: true, user: null, error: '' }) }
  }, [])
  return { ...state, login, logout }
}
