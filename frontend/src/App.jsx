import { useRef, useState } from 'react'

const API_BASE = ''
const FIRST_CALL_QUESTION = 'Please describe the traffic incident.'
const COMPLETE_MESSAGE = 'Incident details are complete. The incident has been created and dispatched.'
const UNCLEAR_MESSAGE = 'I could not hear that clearly. Please click Speak Answer and repeat.'
const RECORDING_SECONDS = 5

function App() {
  const [transcript, setTranscript] = useState('')
  const [incident, setIncident] = useState(null)
  const [moduleDispatch, setModuleDispatch] = useState(null)
  const [reportStatus, setReportStatus] = useState('')
  const [reportError, setReportError] = useState('')
  const [chatQuestion, setChatQuestion] = useState('')
  const [chatAnswer, setChatAnswer] = useState('')
  const [chatStatus, setChatStatus] = useState('')
  const [chatError, setChatError] = useState('')
  const [callSessionId, setCallSessionId] = useState('')
  const [callActive, setCallActive] = useState(false)
  const [callStatus, setCallStatus] = useState('Ready')
  const [callError, setCallError] = useState('')
  const [callQuestion, setCallQuestion] = useState('')
  const [callConversation, setCallConversation] = useState([])
  const [callIncident, setCallIncident] = useState({})
  const [aiVoiceEnabled, setAiVoiceEnabled] = useState(true)
  const [isAiSpeaking, setIsAiSpeaking] = useState(false)
  const [recordingSecondsLeft, setRecordingSecondsLeft] = useState(0)

  const mediaRecorderRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const audioChunksRef = useRef([])
  const recordingTimerRef = useRef(null)
  const countdownTimerRef = useRef(null)
  const shouldProcessRecordingRef = useRef(false)
  const callActiveRef = useRef(false)
  const callCompleteRef = useRef(false)
  const callIncidentRef = useRef({})
  const sessionIdRef = useRef('')

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

  const speakAIQuestion = (text, listenAfter = true) => {
    if (!text) return

    if (!aiVoiceEnabled || !window.speechSynthesis || !window.SpeechSynthesisUtterance) {
      setIsAiSpeaking(false)
      if (callCompleteRef.current) {
        setCallStatus('Complete')
      } else if (listenAfter && callActiveRef.current) {
        setCallStatus('Waiting for answer')
      }
      return
    }

    window.speechSynthesis.cancel()

    const utterance = new SpeechSynthesisUtterance(text)
    const voices = window.speechSynthesis.getVoices()
    const englishVoice = voices.find((voice) => voice.lang?.toLowerCase().startsWith('en'))

    if (englishVoice) {
      utterance.voice = englishVoice
    }

    utterance.lang = englishVoice?.lang || 'en-US'
    utterance.rate = 0.95
    utterance.pitch = 1
    utterance.volume = 1
    utterance.onend = () => {
      setIsAiSpeaking(false)
      if (callCompleteRef.current) {
        setCallStatus('Complete')
      } else if (listenAfter && callActiveRef.current) {
        setCallStatus('Waiting for answer')
      }
    }
    utterance.onerror = () => {
      setIsAiSpeaking(false)
      if (callCompleteRef.current) {
        setCallStatus('Complete')
      } else if (listenAfter && callActiveRef.current) {
        setCallStatus('Waiting for answer')
      }
    }

    setIsAiSpeaking(true)
    setCallStatus('AI Speaking')
    window.speechSynthesis.speak(utterance)
  }

  const handleStartCall = () => {
    const sessionId = sessionIdRef.current || callSessionId || createSessionId()
    sessionIdRef.current = sessionId
    setCallSessionId(sessionId)
    callActiveRef.current = true
    callCompleteRef.current = false
    setCallActive(true)
    setCallError('')
    setCallQuestion(FIRST_CALL_QUESTION)
    setCallConversation((items) => [...items, { speaker: 'AI', text: FIRST_CALL_QUESTION }])
    speakAIQuestion(FIRST_CALL_QUESTION)
  }

  const handleSpeakAnswer = async () => {
    if (!callActiveRef.current || callCompleteRef.current || isAiSpeaking || callStatus === 'Processing') {
      return
    }

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setCallError('Audio recording is not supported in this browser.')
      setCallStatus('Waiting for answer')
      return
    }

    try {
      stopAudioRecording(false)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = getSupportedAudioMimeType()
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)

      mediaStreamRef.current = stream
      mediaRecorderRef.current = recorder
      audioChunksRef.current = []
      shouldProcessRecordingRef.current = true

      recorder.ondataavailable = (event) => {
        if (event.data?.size) {
          audioChunksRef.current.push(event.data)
        }
      }

      recorder.onstop = () => {
        const chunks = audioChunksRef.current
        const recordingType = recorder.mimeType || mimeType || 'audio/webm'
        cleanupRecording()

        if (!shouldProcessRecordingRef.current) {
          return
        }

        const audioBlob = new Blob(chunks, { type: recordingType })
        if (!audioBlob.size) {
          handleEmptyAudioTurn()
          return
        }

        processRecordedAudio(audioBlob)
      }

      setRecordingSecondsLeft(RECORDING_SECONDS)
      setCallStatus('Listening')
      setCallError('')
      setCallQuestion(`Listening... speak now (${RECORDING_SECONDS}s)`)

      recorder.start()

      countdownTimerRef.current = window.setInterval(() => {
        setRecordingSecondsLeft((seconds) => {
          const nextSeconds = Math.max(seconds - 1, 0)
          setCallQuestion(nextSeconds > 0 ? `Listening... speak now (${nextSeconds}s)` : 'Processing...')
          return nextSeconds
        })
      }, 1000)
      recordingTimerRef.current = window.setTimeout(() => {
        stopAudioRecording(true)
      }, RECORDING_SECONDS * 1000)
    } catch (error) {
      cleanupRecording()
      setCallStatus('Waiting for answer')
      setCallError(error.message || 'Could not access the microphone. Please allow microphone access and try again.')
    }
  }

  const processRecordedAudio = async (audioBlob) => {
    setCallStatus('Processing')
    setCallError('')
    setCallQuestion('Processing...')

    const formData = new FormData()
    formData.append('audio', audioBlob, 'interactive-answer.webm')
    formData.append('session_id', sessionIdRef.current || callSessionId)
    formData.append('current_incident_json', JSON.stringify(callIncidentRef.current || {}))

    try {
      const response = await fetch(`${API_BASE}/interactive-voice-audio-turn`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || 'Failed to process voice call turn')
      }

      const data = await response.json()
      const callerTranscript = data.transcript?.trim()

      if (!callerTranscript) {
        handleEmptyAudioTurn(data.current_incident)
        return
      }

      setCallConversation((items) => [...items, { speaker: 'Caller', text: callerTranscript }])

      const updatedIncident = data.current_incident || {}
      callIncidentRef.current = updatedIncident
      setCallIncident(updatedIncident)

      if (data.complete) {
        callCompleteRef.current = true
        callActiveRef.current = false
        setCallActive(false)
        setIncident(data.incident || null)
        setModuleDispatch(data.module_dispatch || null)
        setChatAnswer('')
        setChatError('')
        setCallQuestion(COMPLETE_MESSAGE)
        setCallConversation((items) => [...items, { speaker: 'AI', text: COMPLETE_MESSAGE }])
        setCallStatus('Complete')
        speakAIQuestion(COMPLETE_MESSAGE, false)
        return
      }

      const nextQuestion = data.next_question || UNCLEAR_MESSAGE
      setCallQuestion(nextQuestion)
      setCallConversation((items) => [...items, { speaker: 'AI', text: nextQuestion }])
      speakAIQuestion(nextQuestion)
    } catch (error) {
      const retryMessage = error.message || UNCLEAR_MESSAGE
      setCallError(retryMessage)
      setCallQuestion(UNCLEAR_MESSAGE)
      setCallConversation((items) => [...items, { speaker: 'AI', text: UNCLEAR_MESSAGE }])
      speakAIQuestion(UNCLEAR_MESSAGE)
    }
  }

  const handleEmptyAudioTurn = (currentIncident = callIncidentRef.current || {}) => {
    callIncidentRef.current = currentIncident || {}
    setCallIncident(currentIncident || {})
    setCallQuestion(UNCLEAR_MESSAGE)
    setCallConversation((items) => [
      ...items,
      { speaker: 'Caller', text: 'No clear speech detected' },
      { speaker: 'AI', text: UNCLEAR_MESSAGE }
    ])
    speakAIQuestion(UNCLEAR_MESSAGE)
  }

  const handleEndCall = () => {
    callActiveRef.current = false
    setCallActive(false)
    stopAudioRecording(false)
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel()
    }
    setIsAiSpeaking(false)
    setCallStatus('Ended')
  }

  const handleResetCall = () => {
    callActiveRef.current = false
    callCompleteRef.current = false
    callIncidentRef.current = {}
    sessionIdRef.current = ''
    stopAudioRecording(false)
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel()
    }
    setCallSessionId('')
    setCallActive(false)
    setCallStatus('Ready')
    setCallError('')
    setCallQuestion('')
    setCallConversation([])
    setCallIncident({})
    setIsAiSpeaking(false)
    setRecordingSecondsLeft(0)
    setIncident(null)
    setModuleDispatch(null)
    setChatAnswer('')
    setChatError('')
  }

  const stopAudioRecording = (shouldProcess) => {
    shouldProcessRecordingRef.current = shouldProcess
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    } else {
      cleanupRecording()
    }
  }

  const cleanupRecording = () => {
    if (recordingTimerRef.current) {
      window.clearTimeout(recordingTimerRef.current)
      recordingTimerRef.current = null
    }
    if (countdownTimerRef.current) {
      window.clearInterval(countdownTimerRef.current)
      countdownTimerRef.current = null
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop())
      mediaStreamRef.current = null
    }
    mediaRecorderRef.current = null
    audioChunksRef.current = []
    setRecordingSecondsLeft(0)
  }

  const speakAnswerDisabled =
    !callActive ||
    callCompleteRef.current ||
    isAiSpeaking ||
    callStatus === 'AI Speaking' ||
    callStatus === 'Listening' ||
    callStatus === 'Processing' ||
    callStatus === 'Complete'

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

        <section className="panel call-panel">
          <div className="call-header">
            <div>
              <h2>Interactive Voice Call</h2>
              <span className={`call-status ${callStatus.toLowerCase().replaceAll(' ', '-')}`}>
                {callStatus}
              </span>
            </div>
            <div className="call-pulse" aria-hidden="true" />
          </div>

          <div className="ai-question">
            <div className="ai-question-header">
              <strong>AI Question</strong>
              <div className="ai-voice-controls">
                <label className="voice-toggle">
                  <input
                    type="checkbox"
                    checked={aiVoiceEnabled}
                    onChange={(event) => {
                      setAiVoiceEnabled(event.target.checked)
                      if (!event.target.checked && window.speechSynthesis) {
                        window.speechSynthesis.cancel()
                        setIsAiSpeaking(false)
                        if (callActiveRef.current && !callCompleteRef.current) {
                          setCallStatus('Waiting for answer')
                        }
                      }
                    }}
                  />
                  <span>AI Voice: {aiVoiceEnabled ? 'On' : 'Off'}</span>
                </label>
              </div>
            </div>
            <p>{callQuestion || 'Press Start Call to begin.'}</p>
            {callStatus === 'Listening' && (
              <p className="recording-hint">
                Listening... speak now{recordingSecondsLeft ? ` (${recordingSecondsLeft}s)` : ''}
              </p>
            )}
          </div>

          <div className="call-actions">
            <button className="primary-button" onClick={handleStartCall} disabled={callActive}>
              Start Call
            </button>
            <button className="primary-button" onClick={handleSpeakAnswer} disabled={speakAnswerDisabled}>
              Speak Answer
            </button>
            <button className="secondary-button" onClick={handleEndCall} disabled={!callActive}>
              End Call
            </button>
            <button className="ghost-button" onClick={handleResetCall}>
              Reset Call
            </button>
          </div>

          {callError && <div className="status error">{callError}</div>}

          <div className="call-layout">
            <div className="conversation-log">
              <strong>Conversation Transcript</strong>
              {callConversation.length ? (
                callConversation.map((item, index) => (
                  <div key={`${item.speaker}-${index}`} className={`message ${item.speaker.toLowerCase()}`}>
                    <span>{item.speaker}</span>
                    <p>{item.text}</p>
                  </div>
                ))
              ) : (
                <p className="empty-state">The live call transcript will appear here.</p>
              )}
            </div>

            <div className="collected-fields">
              <strong>Current Collected Fields</strong>
              <div className="field-list">
                {getCollectedFields(callIncident).length ? (
                  getCollectedFields(callIncident).map((item) => (
                    <DashboardItem key={item.label} label={item.label} value={item.value} />
                  ))
                ) : (
                  <p className="empty-state">No fields collected yet.</p>
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="panel">
          <h2>Result Dashboard</h2>
          {incident ? (
            <div className="grid">
              {getDashboardItems(incident, callIncident).map((item) => (
                <DashboardItem key={item.label} label={item.label} value={item.value} />
              ))}
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

function getCollectedFields(currentIncident) {
  const fields = []
  const location = currentIncident.location_name || currentIncident.location_query || currentIncident.landmark

  if (currentIncident.event_type && currentIncident.event_type !== 'unknown') {
    fields.push({ label: 'Event Type', value: formatValue(currentIncident.event_type) })
  }
  if (location && location !== 'Unknown Location') {
    fields.push({ label: 'Location / Landmark / Junction', value: location })
  }
  if (currentIncident.road_name) {
    fields.push({ label: 'Road / Corridor', value: currentIncident.road_name })
  }
  if (currentIncident.traffic_condition) {
    fields.push({ label: 'Traffic Condition', value: formatValue(currentIncident.traffic_condition) })
  }
  if (currentIncident.vehicle_type && currentIncident.vehicle_type !== 'unknown') {
    fields.push({ label: 'Vehicle Type', value: formatValue(currentIncident.vehicle_type) })
  }

  return fields
}

function getDashboardItems(incident, currentIncident = {}) {
  const items = [
    { label: 'Incident ID', value: incident.incident_id || 'N/A' },
    { label: 'Event Type', value: formatValue(incident.event_type || 'N/A') },
  ]

  if (incident.vehicle_type && incident.vehicle_type !== 'unknown') {
    items.push({ label: 'Vehicle Type', value: formatValue(incident.vehicle_type) })
  } else if (incident.event_type === 'congestion') {
    items.push({ label: 'Vehicle Type', value: 'Not applicable' })
  }

  items.push({ label: 'Location Name', value: incident.location_name || 'N/A' })

  const landmark = incident.landmark || currentIncident.landmark
  if (landmark) {
    items.push({ label: 'Landmark / Junction', value: landmark })
  }
  if (incident.corridor) {
    items.push({ label: 'Road / Corridor', value: incident.corridor })
  }

  const hasCoordinates = incident.latitude != null && incident.longitude != null
  items.push({
    label: 'Coordinates',
    value: hasCoordinates ? `${incident.latitude}, ${incident.longitude}` : 'Not available'
  })

  items.push({ label: 'Severity', value: incident.severity || 'N/A' })
  items.push({ label: 'Confidence', value: incident.confidence ?? 'N/A' })
  return items
}

function formatValue(value) {
  return String(value)
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function formatLabel(key) {
  return key
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function createSessionId() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID()
  }
  return `voice-session-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function getSupportedAudioMimeType() {
  if (!window.MediaRecorder?.isTypeSupported) {
    return ''
  }

  return [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/ogg'
  ].find((mimeType) => window.MediaRecorder.isTypeSupported(mimeType)) || ''
}

export default App
