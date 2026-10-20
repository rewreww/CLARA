import { useEffect } from 'react'
import { Activity, ClipboardList, FlaskConical, FolderOpen, Microscope, Pill, RefreshCw, ScanLine, UsersRound } from 'lucide-react'
import OverviewPanel from './OverviewPanel'
import DischargePanel from './DischargePanel'
import { useTrends } from '../hooks/useTrends'
import LabResultsTable from './LabResultsTable'
import PrescriptionsPanel from './PrescriptionsPanel'

const LAB_TYPES = ['chemistry', 'hematology', 'microscopy']
const SECTIONS = [
  { key: 'overview', label: 'Overview', Icon: Activity },
  { key: 'discharge', label: 'Discharge', Icon: ClipboardList },
  { key: 'chemistry', label: 'Chemistry', Icon: FlaskConical },
  { key: 'hematology', label: 'Hematology', Icon: Activity },
  { key: 'microscopy', label: 'Microscopy', Icon: Microscope },
  { key: 'prescriptions', label: 'Prescriptions', Icon: Pill },
  { key: 'imaging', label: 'Imaging', Icon: ScanLine },
]

export default function MainContent({ patient, activeSection, labData, labLoading, labError,
  onLoad, onRefresh, refreshKey, onSelectSection, onBrowse }) {
  const { data: trendData, loading: trendLoading, error: trendError, load: loadTrend, reset: resetTrend } = useTrends()
  const isLabSection = LAB_TYPES.includes(activeSection)

  useEffect(() => {
    if (isLabSection && patient) loadTrend(patient.id, activeSection)
    else resetTrend()
  }, [activeSection, patient?.id, refreshKey])

  useEffect(() => {
    if (!patient || !refreshKey) return
    if (isLabSection || activeSection === 'discharge') onLoad({ silent: true })
  }, [refreshKey, patient?.id, activeSection, isLabSection, onLoad])

  if (!patient) return (
    <div className="patient-empty">
      <span className="empty-icon"><UsersRound size={30} /></span>
      <h1>Patient records</h1>
      <p>No patient selected</p>
      <button className="primary-button" onClick={onBrowse}><UsersRound size={17} />Browse patients</button>
    </div>
  )

  const age = patient.age ? (/[a-z]/i.test(String(patient.age)) ? patient.age : `${patient.age} years`) : null
  return (
    <div className="patient-page">
      <header className="patient-header">
        <div className="patient-identity">
          <span className="record-avatar"><UserInitial name={patient.name} /></span>
          <div><span className="record-eyebrow">Patient record / {patient.id}</span>
            <h1>{patient.name}</h1>
            <p>{[age, patient.sex, patient.ward].filter(Boolean).join(' / ')}
              {patient.status && <span className={`record-status status-${patient.status}`}>{patient.status}</span>}
            </p>
          </div>
        </div>
        <button className="icon-button refresh-record" onClick={onRefresh} disabled={labLoading || trendLoading}
          aria-label="Refresh patient record" title="Refresh patient record"><RefreshCw size={18} className={labLoading || trendLoading ? 'spin-icon' : ''} /></button>
      </header>
      <nav className="record-tabs" aria-label="Patient sections">
        {SECTIONS.map(({ key, label, Icon }) => (
          <button key={key} className={activeSection === key ? 'is-active' : ''}
            aria-current={activeSection === key ? 'page' : undefined} onClick={() => onSelectSection(key)}>
            <Icon size={16} />{label}
          </button>
        ))}
      </nav>
      <div className="patient-content-scroll">
        <div className="patient-content">
          {activeSection === 'overview' ? <OverviewPanel patient={patient} refreshKey={refreshKey} />
            : activeSection === 'discharge' ? <DischargePanel data={labData?.type === 'discharge' ? labData : null} patient={patient} refreshKey={refreshKey} />
            : activeSection === 'prescriptions' ? <PrescriptionsPanel patient={patient} refreshKey={refreshKey} />
            : isLabSection ? (
              (trendLoading || labLoading) ? <div className="record-state" role="status"><RefreshCw size={18} className="spin-icon" />Loading {activeSection}...</div>
              : (trendError && trendError !== 'no_date_folders') || labError ? (
                <div className="record-state error-text" role="alert"><p>Unable to load {activeSection} results.</p>
                  <button className="text-button" onClick={onRefresh}><RefreshCw size={16} />Try again</button></div>
              ) : labData || trendData ? <LabResultsTable results={labData?.type === activeSection ? labData.results : null}
                  timeline={trendData?.lab_type === activeSection ? trendData.timeline : null} labType={activeSection} />
              : <div className="record-state"><p>No results loaded.</p><button className="text-button" onClick={() => onLoad()}><RefreshCw size={16} />Load results</button></div>
            ) : <div className="record-state"><FolderOpen size={28} /><p>Imaging is not yet available.</p></div>}
        </div>
      </div>
    </div>
  )
}

function UserInitial({ name }) {
  return name?.charAt(0).toUpperCase() || 'P'
}
