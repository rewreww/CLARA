import { useState, useCallback, useEffect } from 'react'
import TopBar from './components/TopBar'
import Sidebar from './components/SideBar'
import WorkspaceSidebar from './components/WorkspaceSidebar'
import MainContent from './components/MainContent'
import ChatPanel from './components/ChatPanel'
import SyncProgressWatcher from './components/SyncProgressWatcher'
import TermsAgreementModal from './components/TermsAgreementModal'
import { useLabData } from './hooks/useLabData'
import { useChat } from './hooks/useChat'
import { usePatients } from './hooks/usePatients'
import { useConversations } from './hooks/useConversations'
import { newConversationId } from './lib/conversations'
import { LABS_URL, LLM_URL } from './constants'

function PatientChat(props) {
  const { messages, loading, send, stop } = useChat(props.conversationId, props.initialMessages)
  const { onSave, conversationId, patient, activeSection } = props
  useEffect(() => {
    if (patient) onSave({ id: conversationId, patientId: patient.id, activeSection, messages })
  }, [messages, conversationId, patient?.id, activeSection, onSave])
  return <ChatPanel {...props} messages={messages} loading={loading}
    onSend={(message, section) => send(message, props.patient?.id, section)} onClear={props.onNew} onStop={stop} />
}

export default function App() {
  const [agreementAccepted, setAgreementAccepted] = useState(false)
  return agreementAccepted
    ? <ClaraWorkspace />
    : <TermsAgreementModal onAccept={() => setAgreementAccepted(true)} />
}

function ClaraWorkspace() {
  const [activeApp, setActiveApp] = useState(() => window.location.hash === '#patients' ? 'patients' : 'home')
  const [selectedPatient, setSelectedPatient] = useState(null)
  const [activeSection, setActiveSection] = useState('overview')
  const [refreshKey, setRefreshKey] = useState(0)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [conversationId, setConversationId] = useState(newConversationId)
  const [historyNotice, setHistoryNotice] = useState('')
  const { conversations, storageError, save, rename, remove } = useConversations()
  const { patients, loading: patientsLoading, error: patientsError } = usePatients()
  const { data: labData, loading: labLoading, error: labError, load, reset } = useLabData()

  const closeSidebar = useCallback(() => setSidebarOpen(false), [])
  const navigate = useCallback(page => {
    setActiveApp(page)
    window.location.hash = page
    setSidebarOpen(false)
  }, [])

  useEffect(() => {
    const onHashChange = () => setActiveApp(window.location.hash === '#patients' ? 'patients' : 'home')
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const handleSelectPatient = useCallback(patient => {
    if (patient?.id !== selectedPatient?.id) {
      setSelectedPatient(patient)
      setConversationId(newConversationId())
      setHistoryNotice('')
      setActiveSection('overview')
      reset()
    }
    setSidebarOpen(false)
  }, [selectedPatient?.id, reset])

  const newChat = useCallback(() => { setConversationId(newConversationId()); setHistoryNotice(''); navigate('home') }, [navigate])
  const openConversation = useCallback(conversation => {
    const patient = patients.find(item => item.id === conversation.patientId)
    if (!patient) { setHistoryNotice('This conversation\'s patient record is currently unavailable.'); return }
    reset()
    setSelectedPatient(patient)
    setActiveSection(conversation.activeSection || 'overview')
    if (conversation.activeSection) load(conversation.activeSection, patient.id)
    setConversationId(conversation.id)
    setHistoryNotice('')
    navigate('home')
  }, [patients, load, reset, navigate])
  const deleteConversation = useCallback(id => {
    if (id === conversationId) setConversationId(newConversationId())
    remove(id)
    fetch(`${LLM_URL}/history/clear`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: id }) }).catch(() => {})
  }, [conversationId, remove])

  const handleSelectSection = useCallback(section => {
    setActiveSection(section)
    if (selectedPatient) load(section, selectedPatient.id)
  }, [selectedPatient, load])

  const handleLoad = useCallback((options = {}) => {
    if (selectedPatient) load(activeSection, selectedPatient.id, options)
  }, [selectedPatient, activeSection, load])

  const handleRefresh = useCallback(() => {
    setRefreshKey(key => key + 1)
  }, [])

  useEffect(() => {
    const handlePatientDataUpdated = event => {
      if (!selectedPatient?.id || event.detail?.patientId !== selectedPatient.id) return
      setRefreshKey(key => key + 1)
      fetch(`${LABS_URL}/patients`)
        .then(response => response.ok ? response.json() : null)
        .then(data => {
          const freshPatient = data?.patients?.find(patient => patient.id === selectedPatient.id)
          if (freshPatient) setSelectedPatient(freshPatient)
        })
        .catch(() => {})
    }
    window.addEventListener('clara:patient-data-updated', handlePatientDataUpdated)
    return () => window.removeEventListener('clara:patient-data-updated', handlePatientDataUpdated)
  }, [selectedPatient?.id])

  return (
    <div className="app-shell">
      <Sidebar activeApp={activeApp} onChangeApp={navigate} />
      <WorkspaceSidebar activeApp={activeApp} onChangeApp={navigate}
        selectedPatient={selectedPatient} onSelectPatient={handleSelectPatient}
        patients={patients} loading={patientsLoading} error={patientsError}
        conversations={conversations} activeConversationId={conversationId} onOpenConversation={openConversation}
        onNewConversation={newChat} onRenameConversation={rename} onDeleteConversation={deleteConversation}
        historyError={storageError || historyNotice}
        open={sidebarOpen} onClose={closeSidebar} />
      <div className="app-main">
        <TopBar activeApp={activeApp} patient={selectedPatient}
          onMenu={() => setSidebarOpen(true)} onNavigate={navigate} />
        <main className="app-views" id="main-content">
          <section className="view-pane" hidden={activeApp !== 'home'} aria-label="Home">
            <PatientChat key={conversationId} patient={selectedPatient}
              conversationId={conversationId} initialMessages={conversations.find(item => item.id === conversationId)?.messages}
              onSave={save} onNew={newChat}
              patients={patients} patientsLoading={patientsLoading} patientsError={patientsError}
              onSelectPatient={handleSelectPatient} activeSection={activeSection}
              isActive={activeApp === 'home'} onOpenRecord={() => navigate('patients')} />
          </section>
          <section className="view-pane patient-workspace" hidden={activeApp !== 'patients'} aria-label="Patient records">
            <MainContent patient={selectedPatient} activeSection={activeSection}
              labData={labData} labLoading={labLoading} labError={labError}
              onLoad={handleLoad} onRefresh={handleRefresh} refreshKey={refreshKey}
              onSelectSection={handleSelectSection} onBrowse={() => setSidebarOpen(true)} />
          </section>
        </main>
      </div>
      <SyncProgressWatcher />
    </div>
  )
}
