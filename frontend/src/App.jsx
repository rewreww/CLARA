import { useState, useRef, useCallback, useEffect } from 'react'
import TopBar      from './components/TopBar'
import Sidebar     from './components/SideBar'
import MainContent from './components/MainContent'
import ChatPanel   from './components/ChatPanel'
import { useLabData }  from './hooks/useLabData'
import { useChat }     from './hooks/useChat'
import { usePatients } from './hooks/usePatients'

export default function App() {
  const [selectedPatient, setSelectedPatient] = useState(null)
  const [activeSection,   setActiveSection]   = useState('overview')
  const sessionId = useRef('session_' + Date.now()).current

  const { patients, loading: patientsLoading, error: patientsError } = usePatients()
  const { data: labData, loading: labLoading, error: labError, load, reset } = useLabData()
  const { messages, loading: chatLoading, ruleFlags, isEmergency, send, clear } = useChat(sessionId)

  useEffect(() => {
    if (!selectedPatient) return

    const currentPatient = patients.find(p => p.id === selectedPatient.id)
    if (currentPatient) {
      setSelectedPatient(currentPatient)
    } else if (!patientsLoading) {
      setSelectedPatient(null)
      setActiveSection('overview')
      reset()
    }
  }, [patients, patientsLoading, selectedPatient?.id, reset])

  const handleSelectPatient = useCallback((patient) => {
    if (selectedPatient?.id === patient.id) {
      setSelectedPatient(null)
      setActiveSection('overview')
      reset()
      return
    }
    setSelectedPatient(patient)
    setActiveSection('overview')
    reset()
  }, [selectedPatient?.id, reset])

  const handleSelectSection = useCallback((section) => {
    setActiveSection(section)
    if (selectedPatient) load(section, selectedPatient.id)
  }, [selectedPatient, load])

  const handleLoad = useCallback(() => {
    if (selectedPatient) load(activeSection, selectedPatient.id)
  }, [selectedPatient, activeSection, load])

  useEffect(() => {
    if (!selectedPatient || activeSection !== 'discharge') return undefined
    const intervalId = window.setInterval(() => {
      load('discharge', selectedPatient.id, { silent: true })
    }, 10000)
    return () => window.clearInterval(intervalId)
  }, [selectedPatient, activeSection, load])

  // ↓ activeSection is now passed to send so the backend knows what the doctor is viewing
  const handleSend = useCallback((message) => {
    send(message, selectedPatient?.id, activeSection)
  }, [send, selectedPatient, activeSection])

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg text-[#dde4f0]"
      style={{ fontFamily: 'Syne, sans-serif' }}>

      <TopBar />

      <div className="flex flex-1 overflow-hidden">

        <Sidebar
          patients={patients}
          loading={patientsLoading}
          error={patientsError}
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
            activeSection={activeSection}         
            ruleFlags={ruleFlags}
            isEmergency={isEmergency}
            messages={messages}
            loading={chatLoading}
            onSend={handleSend}
            onClear={clear}
          />
        </div>

      </div>
    </div>
  )
}