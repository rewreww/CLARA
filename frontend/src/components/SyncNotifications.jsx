import { useSyncProgress } from '../hooks/useSyncProgress'

const LEVEL_STYLE = {
  working: { color: '#0ea5e9', border: 'rgba(14,165,233,0.35)', bg: 'rgba(14,165,233,0.08)' },
  success: { color: '#10b981', border: 'rgba(16,185,129,0.35)', bg: 'rgba(16,185,129,0.08)' },
  error:   { color: '#ef4444', border: 'rgba(239,68,68,0.35)',   bg: 'rgba(239,68,68,0.08)' },
  info:    { color: '#94a3b8', border: 'rgba(148,163,184,0.28)', bg: 'rgba(148,163,184,0.08)' },
}

function levelLabel(level) {
  if (level === 'working') return 'SYNC'
  if (level === 'success') return 'SAVED'
  if (level === 'error') return 'ERROR'
  return 'INFO'
}

export default function SyncNotifications({ patient }) {
  const { events, syncing, error, triggerSync } = useSyncProgress(patient?.id)
  const visibleEvents = events.filter(event => event.message).slice(-4).reverse()

  return (
    <div className="fixed right-4 bottom-4 z-50 flex flex-col items-end gap-2 pointer-events-none">
      {visibleEvents.map(event => {
        const style = LEVEL_STYLE[event.level] || LEVEL_STYLE.info
        return (
          <div
            key={event.sequence}
            className="w-[300px] border rounded-[8px] bg-card/95 shadow-[0_12px_35px_rgba(0,0,0,0.32)]
              backdrop-blur px-3 py-2 pointer-events-auto"
            style={{ borderColor: style.border, background: `linear-gradient(90deg, ${style.bg}, rgba(13,21,38,0.96))` }}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                <span
                  className={`w-[7px] h-[7px] rounded-full shrink-0 ${event.level === 'working' ? 'animate-pulse' : ''}`}
                  style={{ background: style.color }}
                />
                <span className="font-mono text-[9px] tracking-[0.12em]" style={{ color: style.color }}>
                  {levelLabel(event.level)}
                </span>
              </div>
              {(event.patientId || event.fileName) && (
                <div className="font-mono text-[9px] text-muted truncate max-w-[150px]">
                  {event.patientId}{event.fileName ? ` / ${event.fileName}` : ''}
                </div>
              )}
            </div>
            <div className="mt-1 text-[12px] leading-[1.45] text-[#d7e2f0]">
              {event.message}
            </div>
          </div>
        )
      })}

      <div className="pointer-events-auto flex items-center gap-2">
        {error && (
          <span className="font-mono text-[10px] text-danger bg-card border border-danger/25 rounded-[6px] px-2 py-[5px]">
            Sync status offline
          </span>
        )}
        <button
          onClick={triggerSync}
          disabled={syncing}
          className="px-3 py-[7px] rounded-[7px] text-[11px] font-mono
            bg-accent text-white border border-accent/40 shadow-[0_10px_25px_rgba(0,0,0,0.28)]
            hover:bg-blue-700 disabled:opacity-60 disabled:cursor-wait transition-colors"
        >
          {syncing ? 'Syncing...' : patient?.id ? 'Sync Patient PDFs' : 'Sync PDFs'}
        </button>
      </div>
    </div>
  )
}
