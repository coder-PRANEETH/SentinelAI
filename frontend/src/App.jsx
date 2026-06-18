import { useState } from 'react'

const API_BASE = ''

function App() {
  const [transcript, setTranscript] = useState('')
  const [voiceFile, setVoiceFile] = useState(null)
  const [voiceTranscript, setVoiceTranscript] = useState('')
  const [voiceStatus, setVoiceStatus] = useState('')
  const [voiceError, setVoiceError] = useState('')
  const [incident, setIncident] = useState(null)
  const [moduleDispatch, setModuleDispatch] = useState(null)
  const [reportStatus, setReportStatus] = useState('')
  const [reportError, setReportError] = useState('')
  const [chatQuestion, setChatQuestion] = useState('')
  const [chatAnswer, setChatAnswer] = useState('')
  const [chatStatus, setChatStatus] = useState('')
  const [chatError, setChatError] = useState('')

  const handleAnalyze = async () => {
    if (!transcript.trim()) {
      setReportError('Please enter an incident transcript.')
      return
    }

    setReportError('')
    setReportStatus('Analyzing...')
    setIncident(null)
    setModuleDispatch(null)
    setChatAnswer('')
    setChatError('')

    try {
      const response = await fetch(`${API_BASE}/report-incident`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: transcript.trim() })
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || 'Failed to analyze incident')
      }

      const data = await response.json()
      setIncident(data.incident || null)
      setModuleDispatch(data.module_dispatch || null)
      setReportStatus('Incident analyzed successfully')
    } catch (error) {
      setReportError(error.message || 'Unexpected error while analyzing incident')
      setReportStatus('')
    }
  }

  const handleVoiceAnalyze = async () => {
    if (!voiceFile) {
      setVoiceError('Please select an audio file to upload.')
      return
    }

    setVoiceStatus('Analyzing voice incident...')
    setVoiceError('')
    setIncident(null)
    setModuleDispatch(null)
    setChatAnswer('')
    setChatError('')
    setVoiceTranscript('')

    try {
      console.log('Selected audio file:', voiceFile)

      const formData = new FormData()
      formData.append('audio', voiceFile)

      const response = await fetch(`${API_BASE}/voice-report-audio`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const errorText = await response.text().catch(() => '')
        console.error('Voice API error response:', errorText)
        throw new Error(errorText || 'Failed to analyze voice incident')
      }

      const data = await response.json()
      console.log('Voice API response:', data)
      setVoiceTranscript(data.transcript || '')
      setIncident(data.incident || null)
      setModuleDispatch(data.module_dispatch || null)
      setVoiceStatus('Voice incident analyzed successfully')
    } catch (error) {
      console.error('Voice analyze failed:', error)
      setVoiceError(error.message || 'Unexpected error while analyzing voice incident')
      setVoiceStatus('')
    }
  }

  const handleAsk = async () => {
    if (!incident) {
      setChatError('Analyze an incident first before asking questions.')
      return
    }
    if (!chatQuestion.trim()) {
      setChatError('Please enter a question for the AI Copilot.')
      return
    }

    setChatError('')
    setChatStatus('Getting answer...')
    setChatAnswer('')

    try {
      const response = await fetch(`${API_BASE}/incident-chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: chatQuestion.trim(), incident })
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || 'Failed to fetch AI answer')
      }

      const data = await response.json()
      setChatAnswer(data.answer || 'No answer returned')
      setChatStatus('Answer received')
    } catch (error) {
      setChatError(error.message || 'Unexpected error while asking question')
      setChatStatus('')
    }
  }

  return (
    <div className="page-shell">
      <header className="page-header">
        <div>
          <h1>SentinelAI Incident Copilot</h1>
          <p>Control-room demo for incident analysis, dispatch status, and chat assistance.</p>
        </div>
      </header>

      <main className="container">
        <section className="panel">
          <h2>Incident Input</h2>
          <textarea
            value={transcript}
            onChange={(event) => setTranscript(event.target.value)}
            placeholder="Type or paste an incident report here..."
            rows={6}
          />
          <button className="primary-button" onClick={handleAnalyze}>
            Analyze Incident
          </button>
          {reportStatus && <div className="status success">{reportStatus}</div>}
          {reportError && <div className="status error">{reportError}</div>}
        </section>

        <section className="panel">
          <h2>Voice Incident Upload</h2>
          <div className="file-row">
            <input
              type="file"
              accept=".m4a,.mp3,.wav,.webm"
              onChange={(event) => {
                setVoiceFile(event.target.files?.[0] || null)
                setVoiceStatus('')
                setVoiceError('')
              }}
            />
          </div>
          <button className="primary-button" onClick={handleVoiceAnalyze}>
            Analyze Voice Incident
          </button>
          {voiceStatus && <div className="status success">{voiceStatus}</div>}
          {voiceError && <div className="status error">{voiceError}</div>}
          {voiceTranscript && (
            <div className="voice-transcript">
              <strong>Returned Transcript</strong>
              <p>{voiceTranscript}</p>
            </div>
          )}
        </section>

        <section className="panel">
          <h2>Result Dashboard</h2>
          {incident ? (
            <div className="grid">
              <DashboardItem label="Incident ID" value={incident.incident_id || 'N/A'} />
              <DashboardItem label="Event Type" value={incident.event_type || 'N/A'} />
              <DashboardItem label="Vehicle Type" value={incident.vehicle_type || 'N/A'} />
              <DashboardItem label="Location Name" value={incident.location_name || 'N/A'} />
              <DashboardItem label="Latitude" value={incident.latitude ?? 'N/A'} />
              <DashboardItem label="Longitude" value={incident.longitude ?? 'N/A'} />
              <DashboardItem label="Severity" value={incident.severity || 'N/A'} />
              <DashboardItem label="Confidence" value={incident.confidence ?? 'N/A'} />
              <div className="dashboard-full">
                <strong>Summary</strong>
                <p>{incident.summary || 'No summary available yet.'}</p>
              </div>
            </div>
          ) : (
            <p className="empty-state">Submit an incident to see structured details.</p>
          )}
        </section>

        <section className="panel">
          <h2>Module Dispatch Status</h2>
          {moduleDispatch ? (
            <div className="dispatch-grid">
              {['city_memory_engine', 'risk_intelligence_engine', 'resource_command_center'].map((key) => (
                <div key={key} className="dispatch-card">
                  <strong>{formatLabel(key)}</strong>
                  <span className={`dispatch-status ${moduleDispatch[key]?.status || 'unknown'}`}>
                    {moduleDispatch[key]?.status || 'unknown'}
                  </span>
                  <p>{moduleDispatch[key]?.message || 'No message received.'}</p>
                </div>
              ))}
            </div>
          ) : incident ? (
            <p className="empty-state">Dispatch not available for this response.</p>
          ) : (
            <p className="empty-state">Dispatch status will appear after incident analysis.</p>
          )}
        </section>

        <section className="panel">
          <h2>Incident Chat</h2>
          <input
            type="text"
            value={chatQuestion}
            onChange={(event) => setChatQuestion(event.target.value)}
            placeholder="Ask the AI Copilot about the incident..."
          />
          <button className="primary-button" onClick={handleAsk} disabled={!incident}>
            Ask AI Copilot
          </button>
          {chatStatus && <div className="status success">{chatStatus}</div>}
          {chatError && <div className="status error">{chatError}</div>}
          {chatAnswer && (
            <div className="chat-answer">
              <strong>Copilot Answer</strong>
              <p>{chatAnswer}</p>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

function DashboardItem({ label, value }) {
  return (
    <div className="dashboard-item">
      <strong>{label}</strong>
      <span>{value}</span>
    </div>
  )
}

function formatLabel(key) {
  return key
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export default App
