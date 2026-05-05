import { useState } from 'react'
import { PATIENTS, FOLDER_SECTIONS, STATUS_COLOR } from '../constants'

const ICONS = [
  { key: 'patients',  icon: '👤', tip: 'Patients'   },
  { key: 'analytics', icon: '📊', tip: 'Analytics'  },
  { key: 'settings',  icon: '⚙',  tip: 'Settings'   },
]

export default function Sidebar({ selectedPatient, onSelectPatient, activeSection, onSelectSection }) {
  const [activeIcon,      setActiveIcon]      = useState('patients')
  const [secondaryOpen,   setSecondaryOpen]   = useState(true)
  const [expandedFolders, setExpandedFolders] = useState({ labs: true })
  const [search,          setSearch]          = useState('')

  const toggleIcon = (key) => {
    if (activeIcon === key) { setSecondaryOpen(o => !o) }
    else { setActiveIcon(key); setSecondaryOpen(true) }
  }

  const toggleFolder = (key) =>
    setExpandedFolders(f => ({ ...f, [key]: !f[key] }))

  const filtered = PATIENTS.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) || p.id.includes(search)
  )

  return (
    <div className="flex shrink-0 h-full">

      {/* ── Thin icon rail ── */}
      <div className="w-[52px] bg-panel border-r border-border flex flex-col items-center
        py-3 gap-1 shrink-0 z-10">
        {ICONS.map(s => (
          <button key={s.key} title={s.tip} onClick={() => toggleIcon(s.key)}
            className={`w-9 h-9 rounded-[9px] border-none flex items-center justify-center
              text-[16px] cursor-pointer transition-all
              ${activeIcon === s.key && secondaryOpen
                ? 'bg-accent/20 outline outline-1 outline-accent/40'
                : 'bg-transparent hover:bg-accent/10'}`}>
            {s.icon}
          </button>
        ))}
        <div className="flex-1" />
        <span className="font-mono text-[9px] text-border tracking-[0.15em]"
          style={{ writingMode: 'vertical-rl' }}>v0.1</span>
      </div>

      {/* ── Secondary panel — only for patients icon ── */}
      {secondaryOpen && activeIcon === 'patients' && (
        <div className="w-[220px] bg-card border-r border-border flex flex-col
          shrink-0 overflow-hidden animate-fade-up">

          {/* Search header */}
          <div className="px-[14px] py-3 border-b border-border shrink-0">
            <div className="font-mono text-[9px] tracking-[0.12em] uppercase text-muted mb-2">
              Patients
            </div>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search..."
              className="w-full bg-panel border border-border rounded-[6px] px-[10px] py-[6px]
                text-[11px] text-[#dde4f0] outline-none transition-colors
                focus:border-accent placeholder:text-muted"
            />
          </div>

          {/* Patient list */}
          <div className="flex-1 overflow-y-auto py-[6px]">
            {filtered.map(p => (
              <div key={p.id}>

                {/* Patient row */}
                <div
                  onClick={() => onSelectPatient(p)}
                  className="px-[14px] py-[9px] cursor-pointer transition-all"
                  style={{
                    borderLeft: `3px solid ${selectedPatient?.id === p.id ? STATUS_COLOR[p.status] : 'transparent'}`,
                    background: selectedPatient?.id === p.id ? 'rgba(37,99,235,0.08)' : 'transparent',
                  }}
                  onMouseEnter={e => { if (selectedPatient?.id !== p.id) e.currentTarget.style.background = 'rgba(37,99,235,0.05)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = selectedPatient?.id === p.id ? 'rgba(37,99,235,0.08)' : 'transparent' }}
                >
                  <div className="flex items-center justify-between mb-[2px]">
                    <span className={`text-[12px] font-semibold truncate
                      ${selectedPatient?.id === p.id ? 'text-[#dde4f0]' : 'text-[#a0aec0]'}`}>
                      {p.name}
                    </span>
                    <span className="text-[8px] px-[5px] py-[1px] rounded-[3px] font-mono font-semibold ml-1 shrink-0"
                      style={{
                        color: STATUS_COLOR[p.status],
                        background: `${STATUS_COLOR[p.status]}1e`,
                      }}>
                      {p.status}
                    </span>
                  </div>
                  <div className="font-mono text-[10px] text-muted">
                    {p.id} · {p.age}y {p.sex}
                  </div>
                </div>

                {/* Folder tree — only under selected patient */}
                {selectedPatient?.id === p.id && (
                  <div className="pb-[6px]">
                    {FOLDER_SECTIONS.map((sec, si) => (
                      <div key={sec.key}>

                        {/* Divider between sections */}
                        {si > 0 && (
                          <div className="h-px bg-border mx-[14px] my-[2px]" />
                        )}

                        {/* Section row */}
                        <div
                          onClick={() => sec.children ? toggleFolder(sec.key) : onSelectSection(sec.key)}
                          className="flex items-center justify-between px-[14px] py-[7px] pl-7
                            cursor-pointer transition-all"
                          style={{
                            background: activeSection === sec.key ? 'rgba(37,99,235,0.12)' : 'transparent',
                          }}
                          onMouseEnter={e => e.currentTarget.style.background = 'rgba(37,99,235,0.07)'}
                          onMouseLeave={e => e.currentTarget.style.background = activeSection === sec.key ? 'rgba(37,99,235,0.12)' : 'transparent'}
                        >
                          <div className={`flex items-center gap-[7px] text-[11px]
                            ${activeSection === sec.key ? 'text-accent2 font-semibold' : 'text-[#8899b0]'}`}>
                            <span className="text-[12px]">{sec.icon}</span>
                            {sec.label}
                          </div>
                          {sec.children && (
                            <span className="text-[9px] text-muted transition-transform duration-150"
                              style={{ display: 'inline-block', transform: expandedFolders[sec.key] ? 'rotate(90deg)' : 'none' }}>
                              ▶
                            </span>
                          )}
                        </div>

                        {/* Children */}
                        {sec.children && expandedFolders[sec.key] && (
                          <div>
                            {sec.children.map(child => (
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
                                onMouseEnter={e => e.currentTarget.style.color = '#0ea5e9'}
                                onMouseLeave={e => e.currentTarget.style.color = activeSection === child.key ? '#0ea5e9' : '#5a7090'}
                              >
                                <span className="text-[8px] opacity-50">—</span>
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
