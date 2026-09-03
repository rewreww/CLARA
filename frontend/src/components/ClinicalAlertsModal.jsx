import { useEffect } from 'react'
import { useClinicalAlerts } from '../hooks/useClinicalAlerts'

function AlertRow({ flag }) {
  const urgent = flag.startsWith('EMERGENCY:')
  const text = flag.replace(/^(EMERGENCY|WARNING):\s*/, '')

  return (
    <div className={`border-l-2 px-3 py-2 ${urgent
      ? 'border-[#ef4444] bg-[#ef4444]/8'
      : 'border-[#f59e0b] bg-[#f59e0b]/8'}`}>
      <div className={`mb-1 font-mono text-[9px] uppercase tracking-[0.1em] ${urgent ? 'text-[#ef4444]' : 'text-[#f59e0b]'}`}>
        {urgent ? 'Urgent' : 'Review'}
      </div>
      <p className="text-[12px] leading-[1.55] text-[#c9d4e3]">{text}</p>
    </div>
  )
}

export default function ClinicalAlertsModal({ patient, onClose }) {
  const { data, loading, error, check } = useClinicalAlerts()

  useEffect(() => {
    check(patient.id)
  }, [patient.id])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4" role="dialog" aria-modal="true" aria-label="Clinical alerts">
      <div className="max-h-[80vh] w-full max-w-[560px] overflow-y-auto rounded-[8px] border border-border bg-[#0d1526] shadow-2xl">
        <div className="sticky top-0 flex items-start justify-between border-b border-border bg-[#0d1526] px-5 py-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[#f59e0b]">Clinical Alerts</div>
            <div className="mt-1 text-[15px] font-semibold text-[#dde4f0]">{patient.name}</div>
            <div className="mt-[2px] font-mono text-[10px] text-muted">{patient.id}</div>
          </div>
          <button type="button" onClick={onClose} aria-label="Close clinical alerts" className="px-2 py-1 font-mono text-[16px] leading-none text-muted hover:text-[#dde4f0]">x</button>
        </div>

        <div className="space-y-3 p-5">
          {loading && <div className="font-mono text-[11px] text-muted">Checking extracted laboratory results...</div>}
          {error && <div className="border-l-2 border-[#ef4444] bg-[#ef4444]/8 px-3 py-2 font-mono text-[11px] text-[#ef4444]">{error}</div>}

          {data?.is_emergency && (
            <div className="border border-[#ef4444]/40 bg-[#ef4444]/10 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.08em] text-[#ef4444]">
              Urgent rule-engine alert detected
            </div>
          )}

          {data && !data.flags.length && (
            <div className="border border-[#10b981]/30 bg-[#10b981]/8 px-3 py-3 text-[12px] text-[#b8d8ca]">
              No clinical alerts were triggered from the extracted laboratory results.
            </div>
          )}

          {data?.flags.map((flag, index) => <AlertRow key={`${flag}-${index}`} flag={flag} />)}

          {data && (
            <div className="font-mono text-[9px] uppercase tracking-[0.08em] text-muted">
              {data.lab_results_checked} extracted results checked
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
