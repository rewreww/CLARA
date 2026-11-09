import test from 'node:test'
import assert from 'node:assert/strict'
import { recordTableLabel } from '../src/lib/mimicTableLabels.js'

const row = (source, record_type = 'labevents', cells = {}) => ({ source, record_type, cells })

test('chemistry tables show actual fluid labels from their source paths', () => {
  assert.equal(recordTableLabel([row('Patient_10000032/Admission_12345678/Chemistry/Blood/chemistry.pdf')], 'chemistry'),
    'Blood · Laboratory results')
  assert.equal(recordTableLabel([row('Patient_10000032/Admission_12345678/Chemistry/Urine/chemistry.pdf')], 'chemistry'),
    'Urine · Laboratory results')
  assert.equal(recordTableLabel([row('Patient_10000032/Admission_12345678/Blood_Gas/Arterial Blood/results.pdf')], 'blood_gas'),
    'Arterial Blood · Laboratory results')
})

test('all non-lab categories display explicit record subtype', () => {
  assert.equal(recordTableLabel([row('P/Admission_12345678/ICU_Records/chartevents/a.pdf', 'chartevents')], 'icu_records'),
    'Chart observations')
  assert.equal(recordTableLabel([row('P/Admission_12345678/Medication_Administration/emar/a.pdf', 'emar')], 'medication_administration'),
    'Medication administration')
  assert.equal(recordTableLabel([row('P/Admission_12345678/Diagnoses/diagnoses_icd/a.pdf', 'diagnoses_icd')], 'diagnoses'),
    'Diagnoses')
})

test('explicit specimen cells are used only when every row agrees', () => {
  const path = 'Patient_10000032/Admission_12345678/Microbiology/microbiologyevents/results.pdf'
  assert.equal(recordTableLabel([row(path, 'microbiologyevents', {'Specimen type': 'Urine'})], 'microbiology'),
    'Urine · Microbiology results')
  assert.equal(recordTableLabel([row(path, 'microbiologyevents', {'Specimen type': 'Blood'}),
    row(path, 'microbiologyevents', {'Specimen type': 'Urine'})], 'microbiology'), 'Microbiology results')
})

test('never guess a blood or urine specimen from a test name', () => {
  assert.equal(recordTableLabel([row('P/Admission_12345678/Chemistry/a.pdf', 'labevents', {Test: 'Urine glucose'})], 'chemistry'),
    'Laboratory results')
  assert.equal(recordTableLabel([], 'chemistry'), 'Records')
})
