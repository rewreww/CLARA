import { Activity, Home, UsersRound } from 'lucide-react'

export default function Sidebar({ activeApp, onChangeApp }) {
  return <aside className="navigation-rail" aria-label="Workspace navigation">
    <a href="#home" onClick={() => onChangeApp('home')} className="brand-mark" aria-label="CLARA Home" title="CLARA Home"><Activity size={23} /></a>
    <nav aria-label="Main navigation">
      {[{ key: 'home', label: 'Home', Icon: Home }, { key: 'patients', label: 'Patients', Icon: UsersRound }].map(({ key, label, Icon }) =>
        <button key={key} className={`rail-button ${activeApp === key ? 'is-active' : ''}`} onClick={() => onChangeApp(key)}
          aria-label={label} aria-current={activeApp === key ? 'page' : undefined} title={label}>
          <Icon size={21} /><span className="rail-tooltip" aria-hidden="true">{label}</span>
        </button>)}
    </nav>
  </aside>
}
