import test from 'node:test'
import assert from 'node:assert/strict'
import { currentAdmissionSummary } from '../src/lib/patientAdmissionState.js'

test('initial picker state has no admissions and does not dereference null', () => {
  assert.equal(currentAdmissionSummary(null, undefined), null)
  assert.equal(currentAdmissionSummary(null, null), null)
  assert.equal(currentAdmissionSummary(null, 'Patient_00000001'), null)
})

test('ignores stale admission summaries from a different patient', () => {
  const a = { patientId: 'Patient_00000001', data: { admissions: [{ id: '12345678' }] } }
  assert.equal(currentAdmissionSummary(a, 'Patient_00000002'), null)
  assert.equal(currentAdmissionSummary(a, undefined), null)
})

test('accepts only the highlighted patient summary', () => {
  const data = { admissions: [{ id: '12345678' }] }
  assert.equal(currentAdmissionSummary({ patientId: 'Patient_00000001', data }, 'Patient_00000001'), data)
  assert.equal(currentAdmissionSummary({ patientId: 'Patient_00000001' }, 'Patient_00000001'), null)
})
