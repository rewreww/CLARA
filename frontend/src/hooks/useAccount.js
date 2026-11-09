import { useCallback, useEffect, useState } from 'react'

const BASE = '/api/backend/account'
async function readResponse(response) {
  let body = null
  try { body = await response.json() } catch {}
  if (!response.ok) {
    const error = new Error(body?.error || (response.status === 401 ? 'Invalid credentials or session expired.' : 'Account service unavailable.'))
    error.status = response.status
    error.code = body?.code
    throw error
  }
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
  const [state, setState] = useState({ loading: true, enabled: false, user: null, error: '', accountNotice: '' })
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
          if (!cancelled) setState({ loading: false, enabled: true, user: null, error: '', accountNotice: err.status === 423 ? err.message : '' })
        }
      } catch {
        if (!cancelled) setState({ loading: false, enabled: false, user: null, error: 'Could not verify CLARA account configuration. Check backend and gateway before continuing.' })
      }
    }
    load()
    return () => { cancelled = true }
  }, [])
  useEffect(() => {
    if (!state.enabled || !state.user) return
    let cancelled = false
    let checking = false
    const check = async () => {
      if (checking || document.visibilityState === 'hidden') return
      checking = true
      try {
        const user = await accountRequest('/me')
        if (!cancelled) setState(previous => previous.user ? { ...previous, user } : previous)
      } catch (error) {
        if (!cancelled && (error.status === 423 || error.status === 401)) {
          setState(previous => ({
            ...previous, user: null,
            accountNotice: error.status === 423 ? error.message : ''
          }))
        }
      } finally { checking = false }
    }
    const onFocus = () => { void check() }
    window.addEventListener('focus', onFocus)
    const interval = window.setInterval(check, 5000)
    return () => {
      cancelled = true
      window.removeEventListener('focus', onFocus)
      window.clearInterval(interval)
    }
  }, [state.enabled, state.user?.id])

  const login = useCallback(async (username, password) => {
    const user = await accountRequest('/login', { method: 'POST', data: { username, password } })
    setState({ loading: false, enabled: true, user, error: '' })
    return user
  }, [])
  const logout = useCallback(async () => {
    try { await accountRequest('/logout', { method: 'POST' }) }
    catch (error) {
      // Password change/recovery invalidates the old cookie before a later logout.
      // Keep the UI signed in when the request fails for any other reason.
      if (error.status !== 401) throw error
    }
    setState({ loading: false, enabled: true, user: null, error: '' })
  }, [])
  return { ...state, login, logout }
}
