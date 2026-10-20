import test from 'node:test'
import assert from 'node:assert/strict'
import { conversationContext, restoreMessages, readConversations, sourceKey, mergeConversationChanges } from '../src/lib/conversations.js'
import { citationPage, sourceDocumentUrl } from '../src/lib/sources.js'

test('restoring an unfinished response marks it interrupted', () => {
  const [message] = restoreMessages([{ role: 'clara', text: 'Partial', streaming: true, status: 'Reading' }])
  assert.equal(message.streaming, false)
  assert.equal(message.interrupted, true)
  assert.equal(message.status, null)
})
test('only completed exchanges become follow-up context', () => {
  const question = { role: 'doctor', text: 'Question' }
  assert.deepEqual(conversationContext([question, { role: 'clara', text: 'Answer' }, question, { role: 'clara', text: 'Partial', interrupted: true }]), [
    { role: 'doctor', content: 'Question' }, { role: 'clara', content: 'Answer' },
  ])
  assert.equal(conversationContext([question, { role: 'clara', text: 'Failure', error: true }]).length, 0)
})
test('context is bounded to ten complete exchanges', () => {
  assert.equal(conversationContext(Array.from({ length: 15 }, () => [{ role: 'doctor', text: 'Q' }, { role: 'clara', text: 'A' }]).flat()).length, 20)
})
test('invalid saved data is rejected rather than silently overwritten', () => {
  assert.throws(() => readConversations({ getItem: () => '{bad' }))
  assert.deepEqual(readConversations({ getItem: () => null }), [])
})
test('PDF URLs stay on the matching local service and patient', () => {
  const url = sourceDocumentUrl({ type: 'patient_pdf', source: '2026-01-01/report #1.pdf' }, '00001')
  assert.equal(url, '/api/backend/patientdata/00001/document?source=2026-01-01%2Freport+%231.pdf')
  assert.equal(sourceDocumentUrl({ type: 'unknown', source: 'https://example.com' }, '00001'), null)
  assert.equal(sourceDocumentUrl({ type: 'guideline', source: 'My guideline' }), '/api/llm/documents/guideline?source=My+guideline')
})
test('missing or invalid citation pages are never labeled exact pages', () => {
  for (const page of [null, undefined, 0, -1, 'text', 1.5]) assert.equal(citationPage({ page }), null)
  assert.equal(citationPage({ page: '2' }), 2)
  assert.notEqual(sourceKey({ source: 'a', page: 1 }), sourceKey({ source: 'a', page: 2 }))
})

test('saving one conversation preserves unrelated history from another tab', () => {
  const stored = [{ id: 'remote', updatedAt: 1 }, { id: 'local', updatedAt: 1 }]
  const local = [{ id: 'local', updatedAt: 2, title: 'Renamed' }]
  assert.deepEqual(mergeConversationChanges(stored, local, new Set(['local'])), [local[0], stored[0]])
  assert.deepEqual(mergeConversationChanges(stored, [], new Set(['local'])), [stored[0]])
})
