export const HISTORY_KEY = 'clara.conversations.v1'

export async function loadPrivateConversations(storage, fetcher = fetch) {
  // Clean existing browser history before displaying or reusing it. Retry when
  // another tab writes while the request is pending, rather than losing its edits.
  for (let attempt = 0; attempt < 3; attempt++) {
    const before = storage.getItem(HISTORY_KEY)
    const items = readConversations(storage)
    if (!items.length) return items
    const response = await fetcher('/api/llm/privacy/sanitize-history', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversations: items }),
    })
    if (!response.ok) throw new Error('Name cleanup is unavailable')
    const data = await response.json()
    if (!Array.isArray(data.conversations) || data.conversations.length !== items.length
      || data.conversations.some((item, i) => item.id !== items[i].id || item.patientId !== items[i].patientId
        || !Array.isArray(item.messages) || item.messages.length !== items[i].messages.length)) {
      throw new Error('Invalid name cleanup response')
    }
    const serialized = JSON.stringify(data.conversations)
    const sanitized = readConversations({ getItem: () => serialized })
    if (storage.getItem(HISTORY_KEY) !== before) continue
    if (serialized !== before) storage.setItem(HISTORY_KEY, serialized)
    return sanitized
  }
  throw new Error('History changed during name cleanup; retrying')
}

export function mergeConversationChanges(stored, local, changedIds) {
  const merged = new Map(stored.map(item => [item.id, item]))
  for (const id of changedIds) {
    const item = local.find(value => value.id === id)
    if (item) merged.set(id, item)
    else merged.delete(id)
  }
  return [...merged.values()].sort((a, b) => b.updatedAt - a.updatedAt)
}

export function newConversationId() {
  return 'session_' + (globalThis.crypto?.randomUUID?.() || `${Date.now()}_${Math.random().toString(36).slice(2)}`)
}

export function restoreMessages(messages = []) {
  return messages.filter(message => message && ['doctor', 'clara'].includes(message.role) && typeof message.text === 'string')
    .map(message => ({
      ...message,
      sources: Array.isArray(message.sources) ? message.sources.filter(source => source && typeof source.source === 'string') : [],
      actions: Array.isArray(message.actions) ? message.actions.filter(action => action && typeof action.label === 'string' && Number.isFinite(action.at)) : [],
      ...(message.streaming ? { streaming: false, interrupted: true, status: null, text: message.text || 'Response interrupted.' } : {}),
    }))
}

export function readConversations(storage) {
  const raw = storage.getItem(HISTORY_KEY)
  if (!raw) return []
  const parsed = JSON.parse(raw)
  if (!Array.isArray(parsed)) throw new Error('Invalid conversation history')
  return parsed.filter(item => item && typeof item.id === 'string' && typeof item.patientId === 'string'
    && typeof item.title === 'string' && Array.isArray(item.messages))
    .map(item => ({ ...item, messages: restoreMessages(item.messages),
      activeSection: ['overview', 'discharge', 'chemistry', 'hematology', 'microscopy', 'prescriptions', 'imaging'].includes(item.activeSection) ? item.activeSection : 'overview',
      updatedAt: Number.isFinite(item.updatedAt) ? item.updatedAt : 0,
    }))
}

export function conversationContext(messages) {
  const pairs = []
  for (let index = 0; index < messages.length - 1; index++) {
    const question = messages[index], answer = messages[index + 1]
    if (question.role === 'doctor' && answer.role === 'clara' && answer.text
      && !answer.streaming && !answer.interrupted && !answer.error) {
      pairs.push({ role: 'doctor', content: question.text }, { role: 'clara', content: answer.text })
      index++
    }
  }
  return pairs.slice(-20)
}

export function sourceKey(source) {
  return JSON.stringify([source.type, source.source, source.page ?? null])
}
