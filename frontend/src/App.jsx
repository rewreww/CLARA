import { useState, useCallback, useRef } from 'react'
import TopBar          from './components/TopBar'
import Sidebar         from './components/SideBar'
import MainContent     from './components/MainContent'
import ChatPanel       from './components/ChatPanel'
import SyncNotifications from './components/SyncNotifications'
import { useLabData }  from './hooks/useLabData'
import { useChat }     from './hooks/useChat'

export default function App() {
  const [activeApp,       setActiveApp]       = useState('patients')
  const [selectedPatient, setSelectedPatient] = useState(null)
  const [activeSection,   setActiveSection]   = useState('overview')
  const sessionId = useRef('session_' + Date.now()).current

  const { data: labData, loading: labLoading, error: labError, load, reset } = useLabData()
  const { messages, loading: chatLoading, send, clear } = useChat(sessionId)

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

  const handleSend = useCallback((message, section) => {
    send(message, selectedPatient?.id, section)
  }, [send, selectedPatient])

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg text-[#dde4f0]"
      style={{ fontFamily: 'Syne, sans-serif' }}>

      <TopBar />

      <div className="flex flex-1 overflow-hidden">

        <Sidebar
          activeApp={activeApp}
          onChangeApp={setActiveApp}
          selectedPatient={selectedPatient}
          onSelectPatient={handleSelectPatient}
          activeSection={activeSection}
          onSelectSection={handleSelectSection}
        />

        <>
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
              messages={messages}
              loading={chatLoading}
              onSend={handleSend}
              onClear={clear}
            />
          </div>
        </>

      </div>
      <SyncNotifications patient={selectedPatient} />
    </div>
  )
}
