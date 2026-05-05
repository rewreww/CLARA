import { useState, useCallback, useRef } from 'react'
import { LLM_URL } from '../constants'

export function useChat(sessionId) {
  const [messages, setMessages] = useState([
    {
      role:       'clara',
      text:       'Hello, Doctor. Select a patient and ask me anything about their lab results, trends, or cardiovascular guidelines.',
      tools:      [],
      guidelines: false,
      flags:      [],
      emergency:  false,
    },
  ])
  const [loading,   setLoading]   = useState(false)
  const [ruleFlags, setRuleFlags] = useState([])
  const [isEmergency, setIsEmergency] = useState(false)

  const send = useCallback(async (message, patientId) => {
    if (!message.trim() || loading) return

    if (!patientId) {
      setMessages(m => [...m, {
        role: 'clara', text: 'Please select a patient first.',
        tools: [], guidelines: false, flags: [], emergency: false,
      }])
      return
    }

    setMessages(m => [...m, {
      role: 'doctor', text: message,
      tools: [], guidelines: false, flags: [], emergency: false,
    }])
    setLoading(true)

    try {
      const res = await fetch(`${LLM_URL}/chat`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          patient_id: patientId,
          message,
          session_id: sessionId,
        }),
      })
      const d = await res.json()

      if (d.rule_flags?.length) {
        setRuleFlags(d.rule_flags)
        setIsEmergency(d.is_emergency || false)
      }

      setMessages(m => [...m, {
        role:       'clara',
        text:       d.response || d.detail || 'No response received.',
        tools:      d.tools_called   || [],
        guidelines: d.guidelines_used || false,
        flags:      d.rule_flags     || [],
        emergency:  d.is_emergency   || false,
      }])
    } catch (e) {
      setMessages(m => [...m, {
        role:       'clara',
        text:       `Connection error: ${e.message}. Is the LLM service running on port 8001?`,
        tools:      [],
        guidelines: false,
        flags:      [],
        emergency:  false,
      }])
    }

    setLoading(false)
  }, [loading, sessionId])

  const clear = useCallback(async () => {
    setMessages([{
      role:       'clara',
      text:       'Chat cleared. How can I help you?',
      tools:      [],
      guidelines: false,
      flags:      [],
      emergency:  false,
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
  }, [sessionId])

  return { messages, loading, ruleFlags, isEmergency, send, clear }
}
