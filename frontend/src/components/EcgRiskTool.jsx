/**
 * CLARA — ECG Cardiovascular Risk Predictor
 * DEMO COMPONENT — can be removed by deleting this file,
 * useEcgRisk.js, and the button that opens it in App.jsx.
 */

import { useState } from 'react'
import { useEcgRisk } from '../hooks/useEcgRisk'

const RISK_COLOR = { high: '#ef4444', moderate: '#f59e0b', low: '#10b981' }
const RISK_BG    = { high: 'bg-danger/10 border-danger/25', moderate: 'bg-warning/10 border-warning/25', low: 'bg-success/10 border-success/25' }

// ── Risk bar ─────────────────────────────────────────────────────────────────
function RiskBar({ label, probability, risk }) {
  const pct   = Math.round(probability * 100)
  const color = RISK_COLOR[risk]
  return (
    <div className="mb-[10px]">
      <div className="flex justify-between items-center mb-[4px]">
        <span className="font-mono text-[10px] text-[#dde4f0]">{label}</span>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[9px] uppercase tracking-wide"
            style={{ color }}>{risk}</span>
          <span className="font-mono text-[11px] font-semibold" style={{ color }}>
            {pct}%
          </span>
        </div>
      </div>
      <div className="h-[5px] bg-border rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  )
}

// ── ECG value chip ────────────────────────────────────────────────────────────
function EcgChip({ label, value, unit, normal }) {
  const isAbnormal = !normal
  return (
    <div className={`rounded-[6px] px-[10px] py-[7px] border
      ${isAbnormal ? 'bg-warning/5 border-warning/20' : 'bg-card border-border'}`}>
      <div className="font-mono text-[8px] uppercase tracking-[0.1em] text-muted mb-[2px]">{label}</div>
      <div className={`font-mono text-[14px] font-semibold ${isAbnormal ? 'text-warning' : 'text-[#dde4f0]'}`}>
        {value ?? '—'}
        <span className="text-[9px] font-normal text-muted ml-[2px]">{unit}</span>
      </div>
    </div>
  )
}

// ── Patient list row ──────────────────────────────────────────────────────────
function PatientRow({ patient, selected, onClick }) {
  const risk  = patient.overall_risk
  const color = risk >= 0.55 ? '#ef4444' : risk >= 0.30 ? '#f59e0b' : '#10b981'
  const label = risk >= 0.55 ? 'HIGH' : risk >= 0.30 ? 'MOD' : 'LOW'
  return (
    <div
      onClick={onClick}
      className={`px-3 py-[9px] cursor-pointer border-b border-border
        transition-colors hover:bg-accent/5
        ${selected ? 'bg-accent/10 border-l-2 border-l-accent' : ''}`}
    >
      <div className="flex justify-between items-center">
        <div>
          <div className="font-mono text-[11px] font-semibold">{patient.name}</div>
          <div className="font-mono text-[9px] text-muted">
            {patient.age}{patient.sex[0]} · {patient.id}
          </div>
        </div>
        <span className="font-mono text-[8px] px-[5px] py-[2px] rounded-[3px]"
          style={{ color, backgroundColor: `${color}18` }}>
          {label}
        </span>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function EcgRiskTool({ onClose }) {
  const { patients, loading, error } = useEcgRisk()
  const [selected, setSelected]      = useState(null)

  const patient = selected !== null ? patients[selected] : null

  // ECG chip normal ranges (AHA guidelines)
  const ecgNormal = patient ? {
    ventricular_rate: patient.ecg_values.ventricular_rate >= 60 && patient.ecg_values.ventricular_rate <= 100,
    atrial_rate:      patient.ecg_values.atrial_rate <= 130,
    pr_interval:      patient.ecg_values.pr_interval >= 120 && patient.ecg_values.pr_interval <= 200,
    qrs_duration:     patient.ecg_values.qrs_duration <= 120,
    qt_corrected:     patient.ecg_values.qt_corrected <= 460,
  } : {}

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-[900px] max-h-[85vh] bg-bg border border-border rounded-[14px]
        shadow-2xl flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3
          border-b border-border bg-panel shrink-0">
          <div>
            <div className="flex items-center gap-3">
              <div className="font-mono text-[13px] font-semibold">
                ECG Cardiovascular Risk Predictor
              </div>
              <span className="font-mono text-[8px] px-[6px] py-[2px] rounded-[4px]
                bg-warning/15 text-warning border border-warning/25 tracking-wider uppercase">
                Demo · Research Only
              </span>
            </div>
            <div className="font-mono text-[9px] text-muted mt-[2px]">
              XGBoost · Trained on EchoNext 100k dataset · AUROC 0.760–0.789
            </div>
          </div>
          <button onClick={onClose}
            className="font-mono text-[11px] px-3 py-[5px] rounded-[6px]
              bg-card border border-border text-muted cursor-pointer
              hover:border-accent hover:text-[#dde4f0] transition-colors">
            ✕ Close
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">

          {/* Patient list */}
          <div className="w-[200px] border-r border-border overflow-y-auto shrink-0 bg-panel">
            <div className="px-3 py-[6px] font-mono text-[8px] uppercase tracking-[0.12em]
              text-muted border-b border-border bg-bg/50">
              Demo Patients
            </div>
            {loading && (
              <div className="p-4 font-mono text-[11px] text-muted">Loading...</div>
            )}
            {error && (
              <div className="p-3 font-mono text-[10px] text-danger">
                ML service offline (port 8002)
              </div>
            )}
            {patients.map((p, i) => (
              <PatientRow
                key={p.id}
                patient={p}
                selected={selected === i}
                onClick={() => setSelected(i)}
              />
            ))}
          </div>

          {/* Detail panel */}
          <div className="flex-1 overflow-y-auto p-5">
            {!patient ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-border">
                <div className="text-[40px] opacity-30">⚡</div>
                <div className="font-mono text-[11px] tracking-[0.12em] uppercase">
                  Select a patient to view ECG risk analysis
                </div>
              </div>
            ) : (
              <>
                {/* Patient header */}
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="text-[15px] font-semibold">{patient.name}</div>
                    <div className="font-mono text-[10px] text-muted mt-[2px]">
                      {patient.age}y · {patient.sex} · {patient.ward}
                    </div>
                    <div className="font-mono text-[10px] text-accent2 mt-[4px]">
                      {patient.clinical_note}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-[9px] text-muted uppercase tracking-wider mb-1">
                      Overall Risk
                    </div>
                    <div className="font-mono text-[22px] font-bold"
                      style={{ color: RISK_COLOR[patient.overall_risk >= 0.55 ? 'high' : patient.overall_risk >= 0.30 ? 'moderate' : 'low'] }}>
                      {Math.round(patient.overall_risk * 100)}%
                    </div>
                  </div>
                </div>

                {/* ECG values */}
                <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-accent mb-2">
                  ● ECG Input Values
                </div>
                <div className="grid grid-cols-5 gap-2 mb-5">
                  <EcgChip label="Vent. Rate"  value={patient.ecg_values.ventricular_rate} unit="bpm"
                    normal={ecgNormal.ventricular_rate} />
                  <EcgChip label="Atrial Rate" value={patient.ecg_values.atrial_rate}      unit="bpm"
                    normal={ecgNormal.atrial_rate} />
                  <EcgChip label="PR Interval" value={patient.ecg_values.pr_interval}      unit="ms"
                    normal={ecgNormal.pr_interval} />
                  <EcgChip label="QRS Duration" value={patient.ecg_values.qrs_duration}   unit="ms"
                    normal={ecgNormal.qrs_duration} />
                  <EcgChip label="QTc"          value={patient.ecg_values.qt_corrected}   unit="ms"
                    normal={ecgNormal.qt_corrected} />
                </div>

                {/* Risk predictions */}
                <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-accent mb-2">
                  ● Predicted Echo Risk
                </div>
                <div className="bg-card border border-border rounded-[10px] p-4 mb-4">
                  {patient.predictions.map(pred => (
                    <RiskBar
                      key={pred.key}
                      label={pred.label}
                      probability={pred.probability}
                      risk={pred.risk}
                    />
                  ))}
                </div>

                {/* Disclaimer */}
                <div className="font-mono text-[9px] text-muted leading-[1.6]
                  border border-border/50 rounded-[6px] px-3 py-2 bg-card/30">
                  ⚠ Research demonstration only. Predictions are generated by a model trained
                  on the EchoNext dataset (Mayo Clinic, USA). Not validated on Philippine patients.
                  Not for clinical use. Always confirm with echocardiography.
                </div>
              </>
            )}
          </div>
        </div>

        {/* Footer model metrics */}
        <div className="px-5 py-[6px] border-t border-border bg-panel shrink-0
          flex gap-5 font-mono text-[9px] text-muted">
          <span>Model: XGBoost multi-output</span>
          <span>Train set: 72,475 ECGs</span>
          <span>Reduced EF AUROC: 0.789</span>
          <span>Structural HD AUROC: 0.760</span>
        </div>
      </div>
    </div>
  )
}
