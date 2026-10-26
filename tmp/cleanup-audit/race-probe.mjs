import fs from 'node:fs/promises'
import vm from 'node:vm'
import assert from 'node:assert/strict'

// Exercise the actual hook implementation with controllable requests.
const source = (await fs.readFile('frontend/src/hooks/useLabData.js', 'utf8'))
  .replace(/^import .*\r?\n/gm, '')
  .replace('export function useLabData', 'function useLabData')
const state = []
let cursor = 0
const pending = new Map()
const context = vm.createContext({
  useState(initial) {
    const index = cursor++
    state[index] = initial
    return [initial, value => { state[index] = value }]
  },
  useCallback: fn => fn,
  LABS_URL: '/audit',
  fetch: (_url, options) => new Promise(resolve => {
    pending.set(JSON.parse(options.body).patient, resolve)
  })
})
const hook = vm.runInContext(`${source}\nuseLabData()`, context)
const first = hook.load('chemistry', 'synthetic-A')
hook.reset()
const second = hook.load('chemistry', 'synthetic-B')
pending.get('synthetic-B')({ ok: true, json: async () => ({ results: [{ test_name: 'synthetic-B' }] }) })
await second
assert.equal(state[0].results[0].test_name, 'synthetic-B')
pending.get('synthetic-A')({ ok: true, json: async () => ({ results: [{ test_name: 'synthetic-A' }] }) })
await first
assert.equal(state[0].results[0].test_name, 'synthetic-A')
console.log('REPRODUCED: the previous patient response overwrites the current patient lab state.')
