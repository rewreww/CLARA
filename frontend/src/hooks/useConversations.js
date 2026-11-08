import { useState, useCallback, useEffect, useRef } from 'react'
import { HISTORY_KEY, readConversations, mergeConversationChanges, loadPrivateConversations, restoreMessages } from '../lib/conversations'
import { accountRequest } from './useAccount'

const normalize = items => items.filter(item => item && typeof item.id === 'string' && Array.isArray(item.messages))
  .map(item => ({
    ...item, patientId: item.patientId || '', admissionId: item.admissionId || '',
    title: typeof item.title === 'string' ? item.title : 'Conversation',
    updatedAt: Number.isFinite(item.updatedAt) ? item.updatedAt : 0,
    messages: restoreMessages(item.messages),
  }))

// Authenticated history lives in PostgreSQL, always keyed to the server-authenticated account.
// Legacy demo history remains separate in browser storage and is never silently linked to a user.
export function useConversations(account = null) {
  const ownerId = account?.id || null
  const [conversations, setConversations] = useState([])
  const [storageError, setStorageError] = useState('')
  const [historyReady, setHistoryReady] = useState(false)
  const changedIds = useRef(new Set())
  const latest = useRef(conversations)
  latest.current = conversations
  const saving = useRef(false)
  const network = useRef(new AbortController())
  const followup = useRef(null)
  useEffect(() => {
    const controller = new AbortController()
    network.current = controller
    return () => { controller.abort(); clearTimeout(followup.current) }
  }, [ownerId])

  const persist = useCallback(async () => {
    if (!changedIds.current.size || !historyReady || saving.current || network.current.signal.aborted) return
    saving.current = true
    let failed = false
    try {
      if (ownerId) {
        const changed = [...changedIds.current]
        for (const id of changed) {
          const item = latest.current.find(value => value.id === id)
          if (item) {
            await accountRequest('/conversations/' + encodeURIComponent(id), {
              method: 'PUT', data: { id, title: item.title, conversation: item }, signal: network.current.signal,
            })
          } else {
            await accountRequest('/conversations/' + encodeURIComponent(id), { method: 'DELETE', signal: network.current.signal })
          }
          // If a streamed response changed while a request was pending, save it again.
          if (latest.current.find(value => value.id === id) === item) changedIds.current.delete(id)
        }
      } else {
        const merged = mergeConversationChanges(readConversations(localStorage), latest.current, changedIds.current)
        localStorage.setItem(HISTORY_KEY, JSON.stringify(merged))
        latest.current = merged
        setConversations(merged)
        changedIds.current.clear()
      }
      setStorageError('')
    } catch {
      failed = true
      if (!network.current.signal.aborted) setStorageError(ownerId ? 'Your account chat history could not be saved. Check the connection before signing out.'
        : 'History is not saved. Browser storage is unavailable or full.')
    } finally {
      saving.current = false
      // Resave any messages that changed while the previous request was in flight.
      if (!failed && ownerId && changedIds.current.size && !network.current.signal.aborted) {
        clearTimeout(followup.current)
        followup.current = setTimeout(persist, 700)
      }
    }
  }, [historyReady, ownerId])

  useEffect(() => {
    const timer = setTimeout(persist, 700)
    window.addEventListener('pagehide', persist)
    return () => { clearTimeout(timer); window.removeEventListener('pagehide', persist) }
  }, [conversations, persist])

  useEffect(() => {
    let cancelled = false
    let retry
    changedIds.current.clear()
    setConversations([])
    setHistoryReady(false)
    const restore = async () => {
      clearTimeout(retry)
      try {
        const items = ownerId
          ? normalize(await accountRequest('/conversations', { signal: network.current.signal }))
          : await loadPrivateConversations(localStorage)
        if (cancelled) return
        setConversations(local => mergeConversationChanges(items, local, changedIds.current))
        setHistoryReady(true)
        setStorageError('')
      } catch {
        if (cancelled) return
        setHistoryReady(false)
        setStorageError(ownerId ? 'Could not load private account chats. Retrying while preserving current messages.'
          : 'Saved chats are waiting for name cleanup. Start CLARA to restore them; existing history is preserved.')
        retry = setTimeout(restore, 5000)
      }
    }
    const sync = event => { if (!ownerId && event.key === HISTORY_KEY) restore() }
    restore()
    window.addEventListener('storage', sync)
    window.addEventListener('online', restore)
    return () => { cancelled = true; clearTimeout(retry); window.removeEventListener('storage', sync); window.removeEventListener('online', restore) }
  }, [ownerId])

  // Failed writes must be retried without switching accounts or discarding draft messages.
  useEffect(() => {
    if (!ownerId || !historyReady || !storageError) return
    const timer = setTimeout(persist, 5000)
    return () => clearTimeout(timer)
  }, [ownerId, historyReady, storageError, persist])

  const save = useCallback(conversation => {
    if (!conversation.messages.some(message => message.role === 'doctor')) return
    changedIds.current.add(conversation.id)
    setConversations(items => {
      const old = items.find(item => item.id === conversation.id)
      const title = old?.title || conversation.messages.find(message => message.role === 'doctor').text.slice(0, 100)
      return [{ ...old, ...conversation, title, updatedAt: Date.now() }, ...items.filter(item => item.id !== conversation.id)]
    })
  }, [])
  const rename = useCallback((id, title) => {
    if (!title.trim()) return
    changedIds.current.add(id)
    setConversations(items => items.map(item => item.id === id ? { ...item, title: title.trim().slice(0, 100), updatedAt: Date.now() } : item))
  }, [])
  const remove = useCallback(id => {
    changedIds.current.add(id)
    setConversations(items => items.filter(item => item.id !== id))
  }, [])

  const flush = useCallback(async () => {
    if (!historyReady || saving.current) return changedIds.current.size === 0
    await persist()
    return changedIds.current.size === 0
  }, [historyReady, persist])

  return { conversations, storageError, save, rename, remove, historyReady, flush }
}
