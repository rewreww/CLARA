import { STATUS_COLOR } from '../constants'
import OverviewPanel from './OverviewPanel'
import LabTable from './LabTable'

export default function MainContent({ patient, activeSection, labData, labLoading, labError, onLoad }) {
  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-bg">

      {/* Header */}
      <div className="px-5 py-3 border-b border-border flex items-center justify-between
        bg-panel shrink-0">
        <div>
          {patient ? (
            <div className="flex items-center gap-3">
              <div className="w-[34px] h-[34px] rounded-[9px] bg-accent/15 border border-accent/30
                flex items-center justify-center font-mono text-[11px] font-semibold text-[#60a5fa]">
                {patient.id}
              </div>
              <div>
                <div className="text-[14px] font-semibold">{patient.name}</div>
                <div className="font-mono text-[10px] text-muted">
                  {patient.age}y · {patient.sex} · {patient.ward} ·{' '}
                  <span style={{ color: STATUS_COLOR[patient.status] }}>
                    {patient.status.toUpperCase()}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="font-mono text-[13px] text-muted">← Select a patient to begin</div>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={onLoad}
            className="px-[14px] py-[6px] rounded-[6px] text-[11px] font-medium
              bg-card border border-border text-[#dde4f0] cursor-pointer
              transition-colors hover:border-accent">
            ↺ Refresh
          </button>
          <button
            onClick={onLoad}
            className="px-[14px] py-[6px] rounded-[6px] text-[11px] font-medium
              bg-accent text-white border-none cursor-pointer
              transition-colors hover:bg-blue-700">
            Load Data
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {!patient ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-border">
            <div className="text-[48px] opacity-30">⊕</div>
            <div className="font-mono text-[12px] tracking-[0.12em] uppercase">
              Select a patient from the sidebar
            </div>
          </div>

        ) : activeSection === 'overview' ? (
          <OverviewPanel patient={patient} />

        ) : labLoading ? (
          <div className="p-6 text-muted font-mono text-[12px] flex items-center gap-2">
            <span className="animate-spin-slow inline-block">⟳</span>
            Loading {activeSection}...
          </div>

        ) : labError ? (
          <div className="m-5 px-4 py-3 bg-danger/5 border border-danger/20 rounded-[8px]
            text-[12px] text-danger font-mono">
            ✗ Could not load data: {labError}
            <div className="text-[10px] text-muted mt-1">
              Make sure all Python services are running (port 8000 and 8001).
            </div>
          </div>

        ) : labData?.type === 'discharge' ? (
          <div className="p-[16px_20px]">
            <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-muted mb-3">
              Discharge Summary
            </div>
            <div className="text-[13px] leading-[1.75] bg-card border border-border
              rounded-[10px] p-[16px_18px] whitespace-pre-wrap font-mono">
              {labData.text || 'No discharge summary found.'}
            </div>
          </div>

        ) : labData ? (
          <LabTable results={labData.results} type={labData.type} />

        ) : (
          <div className="p-6 text-muted font-mono text-[12px]">
            {patient
              ? `Click "Load Data" to fetch ${activeSection} results.`
              : 'Select a patient first.'}
          </div>
        )}
      </div>
    </div>
  )
}
