import { useState, useCallback, useRef } from 'react'
import { LLM_URL } from '../constants'

const WORD_DELAY_MS = 45

export function useChat(sessionId) {
  const [messages,    setMessages]    = useState([{
    role: 'clara',
    text: 'Hello, Doctor. Select a patient and ask me anything about their lab results, trends, or cardiovascular guidelines.',
    tools: [], guidelines: false, flags: [], emergency: false,
  }])
  const [loading,     setLoading]     = useState(false)
  const [ruleFlags,   setRuleFlags]   = useState([])
  const [isEmergency, setIsEmergency] = useState(false)

  const abortRef      = useRef(null)
  const wordQueueRef  = useRef([])
  const wordBufferRef = useRef('')
  const wordTimerRef  = useRef(null)
  const streamDoneRef = useRef(false)

  const updateLastMessage = useCallback((updater) => {
    setMessages(m => {
      if (!m.length) return m
      const updated = [...m]
      const last = { ...updated[updated.length - 1] }
      updater(last)
      updated[updated.length - 1] = last
      return updated
    })
  }, [])

  const stopWordTimer = useCallback(() => {
    if (wordTimerRef.current) {
      clearTimeout(wordTimerRef.current)
      wordTimerRef.current = null
    }
  }, [])

  const resetWordStream = useCallback(() => {
    stopWordTimer()
    wordQueueRef.current  = []
    wordBufferRef.current = ''
    streamDoneRef.current = false
  }, [stopWordTimer])

  const completeStreaming = useCallback(() => {
    updateLastMessage(last => { last.streaming = false })
    setLoading(false)
  }, [updateLastMessage])

  const flushWords = useCallback(() => {
    if (wordTimerRef.current) return

    const tick = () => {
      const nextWord = wordQueueRef.current.shift()

      if (nextWord) {
        updateLastMessage(last => {
          last.text = (last.text || '') + nextWord
        })
        wordTimerRef.current = setTimeout(tick, WORD_DELAY_MS)
        return
      }

      wordTimerRef.current = null
      if (streamDoneRef.current && !wordBufferRef.current) {
        completeStreaming()
      }
    }

    tick()
  }, [completeStreaming, updateLastMessage])

  const enqueueText = useCallback((text) => {
    wordBufferRef.current += text

    while (true) {
      const match = wordBufferRef.current.match(/^(\s*\S+\s+)/)
      if (!match) break
      wordQueueRef.current.push(match[1])
      wordBufferRef.current = wordBufferRef.current.slice(match[1].length)
    }

    flushWords()
  }, [flushWords])

  const finishTextStream = useCallback(() => {
    if (wordBufferRef.current) {
      wordQueueRef.current.push(wordBufferRef.current)
      wordBufferRef.current = ''
    }
    streamDoneRef.current = true
    flushWords()
  }, [flushWords])

  // ↓ activeSection added as third parameter
  const send = useCallback(async (message, patientId, activeSection = null) => {
    if (!message.trim() || loading) return

    if (!patientId) {
      setMessages(m => [...m, {
        role: 'clara', text: 'Please select a patient first.',
        tools: [], guidelines: false, flags: [], emergency: false,
      }])
      return
    }

    resetWordStream()

    setMessages(m => [...m, {
      role: 'doctor', text: message,
      tools: [], guidelines: false, flags: [], emergency: false,
    }])

    setMessages(m => [...m, {
      role: 'clara', text: '',
      tools: [], guidelines: false, flags: [], emergency: false,
      streaming: true,
    }])

    setLoading(true)

    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await fetch(`${LLM_URL}/chat/stream`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id:     patientId,
          message,
          session_id:     sessionId,
          active_section: activeSection,   // ← added
        }),
        signal: controller.signal,
      })

      if (!res.ok)   throw new Error(`LLM service returned ${res.status}`)
      if (!res.body) throw new Error('LLM service did not return a stream')

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          let event
          try { event = JSON.parse(raw) } catch { continue }

          if (event.type === 'meta') {
            setRuleFlags(event.rule_flags || [])
            setIsEmergency(event.is_emergency || false)
            updateLastMessage(last => {
              last.tools      = event.tools_called    || []
              last.guidelines = event.guidelines_used || false
              last.flags      = event.rule_flags      || []
              last.emergency  = event.is_emergency    || false
            })
          }

          if (event.type === 'token') enqueueText(event.token || '')

          if (event.type === 'done') finishTextStream()

          if (event.type === 'error') {
            resetWordStream()
            updateLastMessage(last => {
              last.text      = `Error: ${event.message}`
              last.streaming = false
            })
            setLoading(false)
          }
        }
      }

      if (!streamDoneRef.current) finishTextStream()

    } catch (e) {
      resetWordStream()
      if (e.name === 'AbortError') { setLoading(false); return }
      updateLastMessage(last => {
        last.text      = `Connection error: ${e.message}`
        last.streaming = false
      })
      setLoading(false)
    }
  }, [
    enqueueText,
    finishTextStream,
    loading,
    resetWordStream,
    sessionId,
    updateLastMessage,
  ])

  const clear = useCallback(async () => {
    if (abortRef.current) abortRef.current.abort()
    resetWordStream()
    setLoading(false)
    setMessages([{
      role: 'clara', text: 'Chat cleared. How can I help you?',
      tools: [], guidelines: false, flags: [], emergency: false,
    }])
    setRuleFlags([])
    setIsEmergency(false)
    try {
      await fetch(`${LLM_URL}/history/clear`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ session_id: sessionId }),
      })
    } catch (_) {}
  }, [resetWordStream, sessionId])

  return { messages, loading, ruleFlags, isEmergency, send, clear }
}