import { useEffect, useState } from 'react'

export default function TopBar() {
  const [clock, setClock] = useState('')

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString('en-PH', { hour12: false }))
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="flex items-center justify-between px-5 h-[50px] bg-panel border-b border-border shrink-0 z-10">

      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 bg-accent rounded-[7px] flex items-center justify-center
          text-white text-[13px] font-bold font-mono">
          C
        </div>
        <span className="font-mono text-[14px] font-medium tracking-widest">
          CLARA <span className="text-accent2">SYSTEM</span>
        </span>
      </div>

      {/* Status */}
      <div className="flex items-center gap-3 font-mono text-[11px] text-muted">
        <span className="w-[7px] h-[7px] rounded-full bg-success shadow-[0_0_6px_#10b981] animate-pulse-dot" />
        All services online
        <span>·</span>
        <span>{clock}</span>
      </div>

      {/* User */}
      <div className="flex items-center gap-2 text-[13px]">
        <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center
          text-white text-[11px] font-semibold">
          DR
        </div>
        Dr. Reyes
      </div>

    </div>
  )
}
