import { useState, useCallback, useEffect, useRef } from 'react'
import { HISTORY_KEY, readConversations, mergeConversationChanges } from '../lib/conversations'

export function useConversations() {
  const [initial] = useState(() => {
    try { return { items: readConversations(localStorage), error: '' } }
    catch { return { items: [], error: 'Saved history could not be read. Existing storage has not been replaced.' } }
  })
  const [conversations, setConversations] = useState(initial.items)
  const [storageError, setStorageError] = useState(initial.error)
  const changedIds = useRef(new Set())
  const latest = useRef(conversations)
  latest.current = conversations
  const persist = useCallback(() => {
    if (!changedIds.current.size || initial.error) return
    try {
      const merged = mergeConversationChanges(readConversations(localStorage), latest.current, changedIds.current)
      localStorage.setItem(HISTORY_KEY, JSON.stringify(merged))
      latest.current = merged
      setConversations(merged)
      setStorageError('')
      changedIds.current.clear()
    } catch { setStorageError('History is not saved. Browser storage is unavailable or full.') }
  }, [initial.error])

  useEffect(() => {
    const timer = setTimeout(persist, 300)
    window.addEventListener('pagehide', persist)
    return () => { clearTimeout(timer); window.removeEventListener('pagehide', persist) }
  }, [conversations, persist])

  useEffect(() => {
    const sync = event => {
      if (event.key !== HISTORY_KEY) return
      try { setConversations(items => mergeConversationChanges(readConversations(localStorage), items, changedIds.current)) }
      catch { setStorageError('History changed in another tab but could not be read.') }
    }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
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
