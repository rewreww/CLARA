import { useState, useRef, useCallback, Component } from 'react'
import TopBar       from './components/TopBar'
import Sidebar      from './components/SideBar'
import MainContent  from './components/MainContent'
import ChatPanel    from './components/ChatPanel'
import EcgRiskTool  from './components/EcgRiskTool'
import { useLabData } from './hooks/useLabData'
import { useChat }    from './hooks/useChat'

class EcgErrorBoundary extends Component {
  state = { crashed: false }
  static getDerivedStateFromError() { return { crashed: true } }
  render() {
    if (this.state.crashed) return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <div className="bg-panel border border-border rounded-[12px] p-6 font-mono text-[12px] text-center">
          <div className="text-warning mb-2">⚠ ECG Tool Error</div>
          <div className="text-muted mb-4">ML service is not running (port 8002).<br/>Start it with: <span className="text-accent2">python app.py</span></div>
          <button onClick={() => { this.setState({ crashed: false }); this.props.onClose() }}
            className="px-4 py-2 rounded-[6px] bg-card border border-border text-muted cursor-pointer hover:border-accent">
            Close
          </button>
        </div>
      </div>
    )
    return this.props.children
  }
}

export default function App() {
  const [selectedPatient, setSelectedPatient] = useState(null)
  const [activeSection,   setActiveSection]   = useState('overview')
  const [showEcgTool,     setShowEcgTool]     = useState(false)
  const sessionId = useRef('session_' + Date.now()).current

  const { data: labData, loading: labLoading, error: labError, load, reset } = useLabData()
  const { messages, loading: chatLoading, ruleFlags, isEmergency, send, clear } = useChat(sessionId)

  const handleSelectPatient = useCallback((patient) => {
    setSelectedPatient(patient)
    setActiveSection('overview')
    reset()
  }, [reset])

  const handleSelectSection = useCallback((section) => {
    setActiveSection(section)
    if (selectedPatient) load(section, selectedPatient.id)
  }, [selectedPatient, load])

  const handleLoad = useCallback(() => {
    if (selectedPatient) load(activeSection, selectedPatient.id)
  }, [selectedPatient, activeSection, load])

  const handleSend = useCallback((message) => {
    send(message, selectedPatient?.id)
  }, [send, selectedPatient])

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg text-[#dde4f0]"
      style={{ fontFamily: 'Syne, sans-serif' }}>

      <TopBar onOpenEcgTool={() => setShowEcgTool(true)} />

      <div className="flex flex-1 overflow-hidden">

        <Sidebar
          selectedPatient={selectedPatient}
          onSelectPatient={handleSelectPatient}
          activeSection={activeSection}
          onSelectSection={handleSelectSection}
        />

        <MainContent
          patient={selectedPatient}
          activeSection={activeSection}
          labData={labData}
          labLoading={labLoading}
          labError={labError}
          onLoad={handleLoad}
        />

        <div className="w-[340px] shrink-0">
          <ChatPanel
            patient={selectedPatient}
            ruleFlags={ruleFlags}
            isEmergency={isEmergency}
            messages={messages}
            loading={chatLoading}
            onSend={handleSend}
            onClear={clear}
          />
        </div>

      </div>

      {/* ECG Risk Tool — removable overlay, wrapped to prevent full-app crash */}
      {showEcgTool && (
        <EcgErrorBoundary onClose={() => setShowEcgTool(false)}>
          <EcgRiskTool onClose={() => setShowEcgTool(false)} />
        </EcgErrorBoundary>
      )}
    </div>
  )
}
