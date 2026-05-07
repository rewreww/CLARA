import { useEffect } from 'react'
import { STATUS_COLOR } from '../constants'
import OverviewPanel  from './OverviewPanel'
import LabTable       from './LabTable'
import TrendChart     from './TrendChart'
import DischargePanel from './DischargePanel'
import { useTrends }  from '../hooks/useTrends'

const LAB_TYPES = ['chemistry', 'hematology', 'microscopy']

export default function MainContent({
  patient, activeSection,
  labData, labLoading, labError, onLoad
}) {
  const {
    data: trendData,
    loading: trendLoading,
    error: trendError,
    load: loadTrend,
    reset: resetTrend,
  } = useTrends()

  const isLabSection = LAB_TYPES.includes(activeSection)

  // Automatically load trends whenever a lab section is selected
  useEffect(() => {
    if (isLabSection && patient) {
      loadTrend(patient.id, activeSection)
    } else {
      resetTrend()
    }
  }, [activeSection, patient?.id])

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-bg">

      {/* Header */}
      <div className="px-5 py-3 border-b border-border flex items-center
        justify-between bg-panel shrink-0">
        <div>
          {patient ? (
            <div className="flex items-center gap-3">
              <div className="w-[34px] h-[34px] rounded-[9px] bg-accent/15
                border border-accent/30 flex items-center justify-center
                font-mono text-[11px] font-semibold text-[#60a5fa]">
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
            <div className="font-mono text-[13px] text-muted">
              ← Select a patient to begin
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <button onClick={onLoad}
            className="px-[14px] py-[6px] rounded-[6px] text-[11px] font-medium
              bg-card border border-border text-[#dde4f0] cursor-pointer
              transition-colors hover:border-accent">
            ↺ Refresh
          </button>
          <button onClick={() => {
              onLoad()
              if (isLabSection && patient) loadTrend(patient.id, activeSection)
            }}
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

        ) : activeSection === 'discharge' ? (
          labLoading ? (
            <div className="p-6 text-muted font-mono text-[12px] flex items-center gap-2">
              <span className="animate-spin-slow inline-block">⟳</span>
              Loading discharge summary...
            </div>
          ) : (
            <DischargePanel
              data={labData?.type === 'discharge' ? labData : null}
              patient={patient}
            />
          )

        ) : isLabSection ? (
          trendLoading ? (
            <div className="p-6 text-muted font-mono text-[12px] flex items-center gap-2">
              <span className="animate-spin-slow inline-block">⟳</span>
              Loading {activeSection} trends...
            </div>

          ) : trendData && trendData.lab_type === activeSection ? (
            // ── Trend chart — shown when date folders exist ──
            <TrendChart
              timeline={trendData.timeline}
              labType={activeSection}
              patient={patient}
            />

          ) : trendError === 'no_date_folders' ? (
            // ── No date folders yet — show flat lab table + setup hint ──
            <div>
              {labLoading ? (
                <div className="p-6 text-muted font-mono text-[12px] flex items-center gap-2">
                  <span className="animate-spin-slow inline-block">⟳</span>
                  Loading {activeSection}...
                </div>
              ) : labError ? (
                <div className="m-5 px-4 py-3 bg-danger/5 border border-danger/20
                  rounded-[8px] text-[12px] text-danger font-mono">
                  ✗ {labError}
                </div>
              ) : labData ? (
                <LabTable results={labData.results} type={labData.type} />
              ) : null}

              <div className="mx-5 mt-2 px-4 py-3 bg-warning/5 border border-warning/20
                rounded-[8px] font-mono text-[11px] text-warning">
                <div className="font-semibold mb-1">📅 No trend data — single visit detected</div>
                <div className="text-muted text-[10px] leading-[1.6]">
                  To enable trends, organise lab PDFs into date subfolders:
                  <div className="mt-2 bg-bg rounded p-2 text-[10px]">
                    labs/<br />
                    &nbsp;&nbsp;2025-01-15/<br />
                    &nbsp;&nbsp;&nbsp;&nbsp;{activeSection}.pdf<br />
                    &nbsp;&nbsp;2025-03-02/<br />
                    &nbsp;&nbsp;&nbsp;&nbsp;{activeSection}.pdf
                  </div>
                </div>
              </div>
            </div>

          ) : trendError ? (
            <div className="m-5 px-4 py-3 bg-danger/5 border border-danger/20
              rounded-[8px] text-[12px] text-danger font-mono">
              ✗ {trendError}
              <div className="text-[10px] text-muted mt-1">
                Make sure all Python services are running (port 8000, 8001).
              </div>
            </div>

          ) : (
            <div className="p-6 text-muted font-mono text-[12px]">
              Click "Load Data" to fetch {activeSection} results.
            </div>
          )

        ) : (
          // ── Catch-all: encounters, imaging, prescriptions ──
          <div className="p-[16px_20px]">
            <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-muted mb-3">
              {activeSection.charAt(0).toUpperCase() + activeSection.slice(1)}
            </div>
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <div className="text-[32px] opacity-30">📂</div>
              <div className="font-mono text-[12px] text-muted">
                {activeSection.charAt(0).toUpperCase() + activeSection.slice(1)} — coming soon
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}