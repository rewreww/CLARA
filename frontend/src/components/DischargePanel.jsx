import { useState } from 'react'

const EMPTY_SECTION_TEXT = 'No extracted content'

function Section({ title, content, icon, defaultOpen = true, alwaysShow = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const body = content?.trim() || EMPTY_SECTION_TEXT

  if (!alwaysShow && body === EMPTY_SECTION_TEXT) return null

  return (
    <div className="border border-border rounded-[12px] overflow-hidden mb-3 bg-card">
      <div
        onClick={() => setOpen(o => !o)}
        className="flex items-center justify-between px-4 py-3 cursor-pointer
        hover:bg-accent/5 transition-colors select-none"
      >
        <div className="flex items-center gap-2 text-[13px] font-semibold text-accent2">
          <span className="text-[12px] font-mono">{icon}</span>
          {title}
        </div>

        <span
          className="text-[10px] text-muted transition-transform"
          style={{ transform: open ? 'rotate(90deg)' : 'none' }}
        >
          &gt;
        </span>
      </div>

      {open && (
        <div className="px-4 py-3 text-[13px] leading-[1.75] text-[#d7e2f0] bg-bg border-t border-border">
          {body}
        </div>
      )}
    </div>
  )
}

function DischargeLabs({ labs }) {
  if (!labs?.length) return null

  const flagged = labs.filter(l => l.flag)

  return (
    <div className="border border-border rounded-[12px] overflow-hidden mb-3 bg-card">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-accent2">
          <span className="text-[12px] font-mono">LAB</span>
          Structured Lab Items
        </div>

        {flagged.length > 0 && (
          <span className="text-[10px] px-2 py-1 rounded bg-danger/15 text-danger">
            {flagged.length} abnormal
          </span>
        )}
      </div>

      <div className="bg-bg overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-muted">
              {['Test', 'Value', 'Unit', 'Date', 'Flag'].map(h => (
                <th key={h} className="text-left px-4 py-2 text-[10px] uppercase">
                  {h}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {labs.map((lab, i) => {
              const isHigh = lab.flag === 'high'
              const isLow = lab.flag === 'low'

              return (
                <tr
                  key={`${lab.test || 'lab'}-${lab.date || 'no-date'}-${i}`}
                  className="border-t border-border hover:bg-accent/5"
                >
                  <td className="px-4 py-2">{lab.test}</td>
                  <td
                    className="px-4 py-2 font-semibold"
                    style={{
                      color: isHigh ? '#ef4444' : isLow ? '#f59e0b' : '#10b981',
                    }}
                  >
                    {lab.val}
                  </td>
                  <td className="px-4 py-2 text-muted">{lab.unit || '-'}</td>
                  <td className="px-4 py-2 text-muted">{lab.date || '-'}</td>
                  <td className="px-4 py-2">{lab.flag || 'normal'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function formatPhysicalExam(physicalExam) {
  if (!physicalExam) return ''

  return [physicalExam.vitals, physicalExam.findings]
    .filter(Boolean)
    .join(' ')
}

function HospitalCourse({ course }) {
  if (!course?.length) return null

  return (
    <div className="border border-border rounded-[12px] overflow-hidden mb-3 bg-card">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <span className="text-[12px] font-mono">CW</span>
        <div className="text-[13px] font-semibold text-accent2">
          Course in the Ward
        </div>
      </div>

      <div className="bg-bg">
        {course.map((entry, i) => (
          <div
            key={`${entry.date || 'day'}-${i}`}
            className="px-4 py-3 border-t border-border first:border-t-0"
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] uppercase tracking-wider text-accent2">
                {entry.label || 'Hospital Day'}
              </span>
              {entry.date && (
                <span className="text-[11px] text-muted">
                  {entry.date}
                </span>
              )}
            </div>
            <div className="text-[13px] leading-[1.75] text-[#d7e2f0]">
              {entry.content || EMPTY_SECTION_TEXT}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function patientDetailLine(header, patient) {
  const age = header.age || patient?.age
  const sex = header.sex || patient?.sex
  const ward = header.room_ward || patient?.ward

  return [
    header.hospital_no ? `Hospital No: ${header.hospital_no}` : patient?.id ? `ID: ${patient.id}` : null,
    age ? `${age}${String(age).match(/[a-z]/i) ? '' : 'y'}` : null,
    sex,
    header.civil_status,
    ward,
    header.service,
  ].filter(Boolean).join(' / ')
}

function HeaderMeta({ label, value }) {
  if (!value) return null

  return (
    <div className="min-w-0">
      <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted mb-[3px]">
        {label}
      </div>
      <div className="text-[12px] text-[#d7e2f0] truncate">
        {value}
      </div>
    </div>
  )
}

export default function DischargePanel({ data, patient }) {
  if (!data) {
    return (
      <div className="flex items-center justify-center h-full text-muted">
        Select Discharge to view summary
      </div>
    )
  }

  if (!data.found) {
    return (
      <div className="p-4 text-muted">
        No discharge summary found
      </div>
    )
  }

  const header = data.header || {}
  const documentTitle = header.document_title || 'Discharge Summary'
  const admissionDate = header.date_admitted
    ? `Admitted: ${header.date_admitted}${header.time_admitted ? ` ${header.time_admitted}` : ''}`
    : null
  const dischargeDate = header.date_discharged
    ? `Discharged: ${header.date_discharged}${header.time_discharged ? ` ${header.time_discharged}` : ''}`
    : null

  const summarySections = [
    {
      title: 'Condition Upon Discharge',
      icon: 'CD',
      content: data.condition_discharge,
    },
    {
      title: 'Admitting Diagnosis',
      icon: 'AD',
      content: data.admitting_dx,
    },
    {
      title: 'Final Diagnosis',
      icon: 'FD',
      content: data.final_dx,
    },
    {
      title: 'Chief Complaint',
      icon: 'CC',
      content: data.chief_complaint,
    },
    {
      title: 'History of Present Illness',
      icon: 'HPI',
      content: data.hpi,
    },
    {
      title: 'Past Medical History',
      icon: 'PMH',
      content: data.pmh,
    },
    {
      title: 'Physical Examination',
      icon: 'PE',
      content: formatPhysicalExam(data.physical_exam),
    },
    {
      title: 'Laboratory Data',
      icon: 'LAB',
      content: data.laboratory_data,
    },
  ]

  return (
    <div className="p-4 space-y-3">
      <div className="mb-4 border border-border bg-card rounded-[8px] overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-start justify-between gap-3">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-accent2">
              {documentTitle}
            </div>
            {header.facility && (
              <div className="text-[11px] text-muted mt-1">
                {header.facility}
              </div>
            )}
          </div>
          <div className="font-mono text-[10px] text-muted shrink-0">
            {patient?.id}
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 px-4 py-3 bg-bg">
          <HeaderMeta label="Patient Details" value={patientDetailLine(header, patient)} />
          <HeaderMeta label="Admission" value={admissionDate} />
          <HeaderMeta label="Discharge" value={dischargeDate} />
          <HeaderMeta label="Attending" value={header.attending_physician} />
        </div>
      </div>

      {summarySections.map(section => (
        <Section
          key={section.title}
          title={section.title}
          icon={section.icon}
          content={section.content}
          alwaysShow
        />
      ))}

      <DischargeLabs labs={data.labs} />
      <HospitalCourse course={data.hospital_course} />
    </div>
  )
}
