import { useState } from 'react'
import { FOLDER_SECTIONS, STATUS_COLOR } from '../constants'

const ICONS = [
  { key: 'patients', icon: '👤', tip: 'Patients' },
  { key: 'analytics', icon: '📊', tip: 'Analytics' },
  { key: 'settings', icon: '⚙', tip: 'Settings' },
]

const DEFAULT_PATIENT_COLOR = '#2563eb'

function patientColor(patient) {
  return STATUS_COLOR[patient.status] || DEFAULT_PATIENT_COLOR
}

function formatAge(age) {
  if (!age) return null
  return String(age).match(/[a-z]/i) ? age : `${age}y`
}

export default function Sidebar({
  patients = [],
  loading = false,
  error = null,
  selectedPatient,
  onSelectPatient,
  activeSection,
  onSelectSection,
}) {
  const [activeIcon, setActiveIcon] = useState('patients')
  const [secondaryOpen, setSecondaryOpen] = useState(true)
  const [expandedFolders, setExpandedFolders] = useState({ labs: true })
  const [search, setSearch] = useState('')

  const toggleIcon = (key) => {
    if (activeIcon === key) setSecondaryOpen(open => !open)
    else {
      setActiveIcon(key)
      setSecondaryOpen(true)
    }
  }

  const toggleFolder = (key) =>
    setExpandedFolders(folders => ({ ...folders, [key]: !folders[key] }))

  const filtered = patients.filter(patient =>
    patient.name.toLowerCase().includes(search.toLowerCase()) ||
    patient.id.includes(search)
  )

  return (
    <div className="flex shrink-0 h-full">
      <div className="w-[52px] bg-panel border-r border-border flex flex-col items-center
        py-3 gap-1 shrink-0 z-10">
        {ICONS.map(item => (
          <button key={item.key} title={item.tip} onClick={() => toggleIcon(item.key)}
            className={`w-9 h-9 rounded-[9px] border-none flex items-center justify-center
              text-[16px] cursor-pointer transition-all
              ${activeIcon === item.key && secondaryOpen
                ? 'bg-accent/20 outline outline-1 outline-accent/40'
                : 'bg-transparent hover:bg-accent/10'}`}>
            {item.icon}
          </button>
        ))}
        <div className="flex-1" />
        <span className="font-mono text-[9px] text-border tracking-[0.15em]"
          style={{ writingMode: 'vertical-rl' }}>v0.1</span>
      </div>

      {secondaryOpen && activeIcon === 'patients' && (
        <div className="w-[220px] bg-card border-r border-border flex flex-col
          shrink-0 overflow-hidden animate-fade-up">
          <div className="px-[14px] py-3 border-b border-border shrink-0">
            <div className="font-mono text-[9px] tracking-[0.12em] uppercase text-muted mb-2">
              Patients
            </div>
            <input
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="Search..."
              className="w-full bg-panel border border-border rounded-[6px] px-[10px] py-[6px]
                text-[11px] text-[#dde4f0] outline-none transition-colors
                focus:border-accent placeholder:text-muted"
            />
          </div>

          <div className="flex-1 overflow-y-auto py-[6px]">
            {loading && (
              <div className="px-[14px] py-[10px] text-[11px] text-muted font-mono">
                Loading patient folders...
              </div>
            )}

            {error && (
              <div className="px-[14px] py-[10px] text-[11px] text-danger font-mono leading-[1.5]">
                {error}
              </div>
            )}

            {!loading && !error && filtered.length === 0 && (
              <div className="px-[14px] py-[10px] text-[11px] text-muted font-mono leading-[1.5]">
                No patient folders found
              </div>
            )}

            {filtered.map(patient => (
              <div key={patient.id}>
                <div
                  onClick={() => onSelectPatient(patient)}
                  className="px-[14px] py-[9px] cursor-pointer transition-all"
                  style={{
                    borderLeft: `3px solid ${selectedPatient?.id === patient.id ? patientColor(patient) : 'transparent'}`,
                    background: selectedPatient?.id === patient.id ? 'rgba(37,99,235,0.08)' : 'transparent',
                  }}
                  onMouseEnter={event => {
                    if (selectedPatient?.id !== patient.id) {
                      event.currentTarget.style.background = 'rgba(37,99,235,0.05)'
                    }
                  }}
                  onMouseLeave={event => {
                    event.currentTarget.style.background = selectedPatient?.id === patient.id
                      ? 'rgba(37,99,235,0.08)'
                      : 'transparent'
                  }}
                >
                  <div className="flex items-center justify-between mb-[2px]">
                    <span className={`text-[12px] font-semibold truncate
                      ${selectedPatient?.id === patient.id ? 'text-[#dde4f0]' : 'text-[#a0aec0]'}`}>
                      {patient.name}
                    </span>
                    {patient.status && (
                      <span className="text-[8px] px-[5px] py-[1px] rounded-[3px] font-mono font-semibold ml-1 shrink-0"
                        style={{
                          color: patientColor(patient),
                          background: `${patientColor(patient)}1e`,
                        }}>
                        {patient.status}
                      </span>
                    )}
                  </div>
                  <div className="font-mono text-[10px] text-muted">
                    {[patient.id, formatAge(patient.age), patient.sex].filter(Boolean).join(' · ')}
                  </div>
                </div>

                {selectedPatient?.id === patient.id && (
                  <div className="pb-[6px]">
                    {FOLDER_SECTIONS.map((section, sectionIndex) => (
                      <div key={section.key}>
                        {sectionIndex > 0 && (
                          <div className="h-px bg-border mx-[14px] my-[2px]" />
                        )}

                        <div
                          onClick={() => section.children ? toggleFolder(section.key) : onSelectSection(section.key)}
                          className="flex items-center justify-between px-[14px] py-[7px] pl-7
                            cursor-pointer transition-all"
                          style={{
                            background: activeSection === section.key ? 'rgba(37,99,235,0.12)' : 'transparent',
                          }}
                          onMouseEnter={event => { event.currentTarget.style.background = 'rgba(37,99,235,0.07)' }}
                          onMouseLeave={event => {
                            event.currentTarget.style.background = activeSection === section.key
                              ? 'rgba(37,99,235,0.12)'
                              : 'transparent'
                          }}
                        >
                          <div className={`flex items-center gap-[7px] text-[11px]
                            ${activeSection === section.key ? 'text-accent2 font-semibold' : 'text-[#8899b0]'}`}>
                            <span className="text-[12px]">{section.icon}</span>
                            {section.label}
                          </div>
                          {section.children && (
                            <span className="text-[9px] text-muted transition-transform duration-150"
                              style={{ display: 'inline-block', transform: expandedFolders[section.key] ? 'rotate(90deg)' : 'none' }}>
                              ▶
                            </span>
                          )}
                        </div>

                        {section.children && expandedFolders[section.key] && (
                          <div>
                            {section.children.map(child => (
                              <div key={child.key}
                                onClick={() => onSelectSection(child.key)}
                                className="text-[11px] py-[6px] cursor-pointer transition-all flex items-center gap-[6px]"
                                style={{
                                  paddingLeft: 44,
                                  marginLeft: 26,
                                  color: activeSection === child.key ? '#0ea5e9' : '#5a7090',
                                  background: activeSection === child.key ? 'rgba(37,99,235,0.1)' : 'transparent',
                                  borderLeft: activeSection === child.key ? '2px solid #2563eb' : '2px solid transparent',
                                }}
                                onMouseEnter={event => { event.currentTarget.style.color = '#0ea5e9' }}
                                onMouseLeave={event => {
                                  event.currentTarget.style.color = activeSection === child.key ? '#0ea5e9' : '#5a7090'
                                }}
                              >
                                <span className="text-[8px] opacity-50">-</span>
                                {child.label}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
