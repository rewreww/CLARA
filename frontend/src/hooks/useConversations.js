import { useState, useCallback, useEffect, useRef } from 'react'
import { HISTORY_KEY, readConversations, mergeConversationChanges, loadPrivateConversations } from '../lib/conversations'

export function useConversations() {
  const [conversations, setConversations] = useState([])
  const [storageError, setStorageError] = useState('')
  const [historyReady, setHistoryReady] = useState(false)
  const changedIds = useRef(new Set())
  const latest = useRef(conversations)
  latest.current = conversations
  const persist = useCallback(() => {
    if (!changedIds.current.size || !historyReady) return
    try {
      const merged = mergeConversationChanges(readConversations(localStorage), latest.current, changedIds.current)
      localStorage.setItem(HISTORY_KEY, JSON.stringify(merged))
      latest.current = merged
      setConversations(merged)
      setStorageError('')
      changedIds.current.clear()
    } catch { setStorageError('History is not saved. Browser storage is unavailable or full.') }
  }, [historyReady])

  useEffect(() => {
    const timer = setTimeout(persist, 300)
    window.addEventListener('pagehide', persist)
    return () => { clearTimeout(timer); window.removeEventListener('pagehide', persist) }
  }, [conversations, persist])

  useEffect(() => {
    let cancelled = false, retry, generation = 0
    const restore = async () => {
      const current = ++generation
      clearTimeout(retry)
      try {
        const stored = await loadPrivateConversations(localStorage)
        if (cancelled || current !== generation) return
        setConversations(items => mergeConversationChanges(stored, items, changedIds.current))
        setHistoryReady(true)
        setStorageError('')
      } catch {
        if (cancelled || current !== generation) return
        setHistoryReady(false)
        setStorageError('Saved chats are waiting for name cleanup. Start CLARA to restore them; existing history is preserved.')
        retry = setTimeout(restore, 5000)
      }
    }
    const sync = event => { if (event.key === HISTORY_KEY) restore() }
    restore()
    window.addEventListener('storage', sync)
    window.addEventListener('online', restore)
    return () => { cancelled = true; clearTimeout(retry); window.removeEventListener('storage', sync); window.removeEventListener('online', restore) }
  }, [])

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

  return { conversations, storageError, save, rename, remove }
}
