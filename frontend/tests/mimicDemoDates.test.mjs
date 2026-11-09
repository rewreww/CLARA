import test from 'node:test'
import assert from 'node:assert/strict'
import { demoDateText } from '../src/lib/mimicDemoDates.js'

test('a fixed UTC day offset preserves exact event intervals and timestamps', () => {
  const offset = Math.round((Date.UTC(2009, 0, 1) - Date.UTC(2153, 0, 1)) / 86400000)
  const first = demoDateText('2154-06-15T08:00:00', offset)
  const next = demoDateText('2154-06-18T11:15:00', offset)
  assert.equal(first, '2010-06-15T08:00:00')
  assert.equal(next, '2010-06-18T11:15:00')
  assert.equal(Date.parse(next) - Date.parse(first),
    Date.parse('2154-06-18T11:15:00Z') - Date.parse('2154-06-15T08:00:00Z'))
})

test('leap days and month boundaries are converted without truncating or guessing', () => {
  const offset = -365
  const t1 = demoDateText('2124-02-28T18:00:00', offset)
  const t2 = demoDateText('2124-02-29T18:00:00', offset)
  const t3 = demoDateText('2124-03-01T18:00:00', offset)
  assert.equal(Date.parse(t2 + 'Z') - Date.parse(t1 + 'Z'), 86400000)
  assert.equal(Date.parse(t3 + 'Z') - Date.parse(t2 + 'Z'), 86400000)
})

test('unknown anchors, non-dates and invalid dates remain unchanged', () => {
  const text = '2125-07-15T09:00:00 · invalid 2125-02-30 · 2125-01-01'
  assert.equal(demoDateText(text, null), text)
  assert.equal(demoDateText(text, 1.5), text)
  assert.equal(demoDateText('2125-02-30', -10000), '2125-02-30')
  assert.equal(demoDateText('Patient_10000032 admission 12345678', -10000),
    'Patient_10000032 admission 12345678')
  assert.equal(demoDateText('Dates: 2125-07-15 then 2125-07-16', -365),
    'Dates: 2124-07-15 then 2124-07-16')
})

test('record values are not mutated by presentation conversion', () => {
  const row = Object.freeze({ observed_at: '2154-06-15T08:00:00', cells: Object.freeze({ Date: '2154-06-15' }) })
  assert.notEqual(demoDateText(row.observed_at, -52600), row.observed_at)
  assert.equal(row.observed_at, '2154-06-15T08:00:00')
  assert.equal(row.cells.Date, '2154-06-15')
})
