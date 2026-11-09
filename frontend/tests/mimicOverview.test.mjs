import test from 'node:test'
import assert from 'node:assert/strict'
import { admissionDates, admissionDemographics, dateParts, vitalSeries } from '../src/lib/mimicOverview.js'

test('admission dates use printed dates rather than IDs and preserve shifted years', () => {
  const data = { admissions: [{ id: '2' }, { id: '1' }, { id: 'unlinked' }], overview: [
    { admission: '2', metadata: JSON.stringify({ 'Admission details': [{ 'Admission date and time / type': '2125-08-15 13:00:00' }] }) },
    { admission: '1', metadata: JSON.stringify({ 'Admission details': [{ 'Admission date and\ntime / type': '2125-07-15\n09:00:00' }] }) },
  ] }
  assert.deepEqual(admissionDates(data).map(x => x.id), ['1', '2', 'unlinked'])
  assert.deepEqual(dateParts('2125-07-15'), { month: 'Jul', day: 15, year: '25' })
  assert.equal(dateParts(null), null)
})
test('vitals normalize known units and pair BP only at the same time and method', () => {
  const row = (label, value, unit, at = '2125-07-15T10:00:00') => ({ label, value, unit, at })
  const series = vitalSeries([
    row('Non Invasive Blood Pressure systolic', 120, 'mmHg'),
    row('Non Invasive Blood Pressure diastolic', 80, 'mmHg'),
    row('Non Invasive Blood Pressure systolic', 150, 'mmHg', '2125-07-15T11:00:00'),
    row('Temperature Fahrenheit', 98.6, '°F'),
    row('Heart Rate', 99, 'unknown'), row('Respiratory Rate', 18, 'insp/min'),
  ])
  assert.equal(series[0].points.length, 1)
  assert.equal(series[0].points[0].secondary, 80)
  assert.equal(series[1].points.length, 0)
  assert.equal(series[2].points[0].value, 18)
  assert.ok(Math.abs(series[4].points[0].value - 37) < .001)
  assert.ok(vitalSeries([]).every(x => x.points.length === 0))
})

test('demographics are scoped to exactly the selected patient and admission', () => {
  const summary = { patient: 'Patient_10014729', overview: [
    { admission: '12345678', source: 'Patient_10014729/Admission_12345678/overview.pdf',
      metadata: JSON.stringify({ 'Anchor age': '64', 'Gender': 'F', 'Insurance': 'Medicare' }) },
    { admission: '87654321', source: 'Patient_10014729/Admission_87654321/overview.pdf',
      metadata: JSON.stringify({ 'Anchor age': '28', 'Gender': 'M' }) },
  ] }
  const result = admissionDemographics(summary, 'Patient_10014729', '12345678')
  assert.equal(result.fields.find(row => row.label === 'Sex').value, 'F')
  assert.equal(result.fields.find(row => row.label === 'Age (reference year)').value, '64')
  assert.equal(result.fields.find(row => row.label === 'Marital status').value, null)
  assert.deepEqual(result.sources, ['Patient_10014729/Admission_12345678/overview.pdf'])
  assert.equal(admissionDemographics(summary, 'Patient_10014729', '87654321').fields.find(row => row.label === 'Sex').value, 'M')
  assert.equal(admissionDemographics(summary, 'Patient_99999999', '12345678'), null)
  assert.equal(admissionDemographics(summary, 'Patient_10014729', ''), null)
})
test('malformed and conflicting overview metadata cannot leak or fabricate demographics', () => {
  const summary = { patient: 'Patient_10014729', overview: [
    { admission: '12345678', metadata: '{invalid' },
    { admission: '12345678', metadata: '{"Gender":"F","Age":"69"}' },
    { admission: '12345678', metadata: '{"Gender":"M","Age":"69"}' },
    { admission: '87654321', metadata: '{"Gender":"Other"}' },
  ] }
  const fields = admissionDemographics(summary, 'Patient_10014729', '12345678').fields
  assert.equal(fields.find(row => row.label === 'Sex').value, null)
  assert.equal(fields.find(row => row.label === 'Age (reference year)').value, '69')
})
