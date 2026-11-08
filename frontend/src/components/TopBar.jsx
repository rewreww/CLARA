import { ArrowUpRight, Menu, MessageSquare } from 'lucide-react'

export default function TopBar({ activeApp, patient, onMenu, onNavigate }) {
  return (
    <header className={`topbar ${activeApp === "home" ? "topbar-home" : ""}`}>
      <div className="topbar-heading">
        <button className="icon-button mobile-menu" onClick={onMenu} aria-label={activeApp === 'home' ? 'Open conversation history' : 'Open patient directory'} title={activeApp === 'home' ? 'Conversation history' : 'Patient directory'}><Menu size={21} /></button>
        {activeApp === 'patients' && <><span>Patients</span><span className="workspace-label">Clinical workspace</span></>}
      </div>
      {activeApp === 'patients' ? (
        <button className="text-button" onClick={() => onNavigate('home')}><MessageSquare size={16} />Ask CLARA<ArrowUpRight size={15} /></button>
      ) : null}
    </header>
  )
}
