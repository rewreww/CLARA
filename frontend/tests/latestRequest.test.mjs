import test from 'node:test'
import assert from 'node:assert/strict'
import { createLatestRequestGuard } from '../src/lib/latestRequest.js'

test('switching patients invalidates an earlier in-flight response', () => {
  const guard = createLatestRequestGuard()
  const patientA = guard.begin()
  const patientB = guard.begin()
  assert.equal(patientA.signal.aborted, true)
  assert.equal(patientA.isCurrent(), false)
  assert.equal(patientB.isCurrent(), true)
})

test('reset and unmount invalidate pending responses', () => {
  const guard = createLatestRequestGuard()
  const pending = guard.begin()
  guard.invalidate()
  assert.equal(pending.signal.aborted, true)
  assert.equal(pending.isCurrent(), false)
})

test('only the newest request can commit even if older work completes late', async () => {
  const guard = createLatestRequestGuard()
  const updates = []
  let releaseA
  const doneA = new Promise(resolve => { releaseA = resolve })

  const a = guard.begin()
  const slowResponse = doneA.then(() => {
    if (a.isCurrent()) updates.push('patient A')
  })

  const b = guard.begin()
  if (b.isCurrent()) updates.push('patient B')
  releaseA()
  await slowResponse
  assert.deepEqual(updates, ['patient B'])
})
