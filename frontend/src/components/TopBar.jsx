import { ArrowUpRight, Menu, MessageSquare, UsersRound } from 'lucide-react'

export default function TopBar({ activeApp, patient, onMenu, onNavigate }) {
  return (
    <header className="topbar">
      <div className="topbar-heading">
        <button className="icon-button mobile-menu" onClick={onMenu} aria-label={activeApp === 'home' ? 'Open conversation history' : 'Open patient directory'} title={activeApp === 'home' ? 'Conversation history' : 'Patient directory'}><Menu size={21} /></button>
        <span>{activeApp === 'home' ? 'CLARA Assistant' : 'Patients'}</span>
        <span className="workspace-label">Clinical workspace</span>
      </div>
      {activeApp === 'patients' ? (
        <button className="text-button" onClick={() => onNavigate('home')}><MessageSquare size={16} />Ask CLARA<ArrowUpRight size={15} /></button>
      ) : patient && (
        <button className="text-button" onClick={() => onNavigate('patients')}><UsersRound size={16} />Open patient record<ArrowUpRight size={15} /></button>
      )}
    </header>
  )
}
