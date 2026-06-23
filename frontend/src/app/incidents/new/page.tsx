'use client';
import { useState, useRef, useEffect, FormEvent } from 'react';
import { CopilotPanel } from '@/components/copilot/CopilotPanel';
import { PageHeading } from '@/components/layout/PageHeading';
import { api } from '@/lib/api';
import { predict, PredictResponse, FinalApiError } from '@/api/finalEndpointsApi';
import { Mic, MicOff, Type, Loader2, Play, Square, Volume2, VolumeX, RotateCcw, MessageSquare } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWebSpeech } from '@/hooks/useWebSpeech';

const INCIDENT_TYPES = [
  'Vehicle Breakdown', 'Road Blockage', 'Fallen Tree',
  'Traffic Disruption', 'Road Closure',
];

const VEHICLE_TYPES = [
  'Car', 'Motorcycle', 'Bus', 'Truck', 'Lorry', 'Tanker',
  'Auto Rickshaw', 'Unknown',
];

const CORRIDORS = [
  'Tumkur Road', 'Outer Ring Road', 'MG Road', 'Hosur Road',
  'Old Madras Road', 'Bannerghatta Road', 'Mysore Road',
  'Sarjapur Road', 'Bellary Road', 'NH 44',
];

const STREAMING_VOICE_THRESHOLD = 0.025;
const STREAMING_SILENCE_DURATION_MS = 1500;
const STREAMING_MIN_RECORDING_MS = 1500;
const STREAMING_MAX_RECORDING_MS = 10000;

// Field mapping helpers for Interactive Voice Assistant
const mapEventTypeToIncidentType = (eventType: string): string => {
  if (!eventType) return '';
  const mapping: Record<string, string> = {
    congestion: 'Traffic Disruption',
    accident: 'Vehicle Breakdown',
    road_block: 'Road Blockage',
    vehicle_breakdown: 'Vehicle Breakdown',
    fire: 'Road Blockage',
    medical_emergency: 'Vehicle Breakdown',
  };
  return mapping[eventType] || '';
};

const mapVehicleTypeToVehicleType = (vehType: string): string => {
  if (!vehType) return '';
  const mapping: Record<string, string> = {
    two_wheeler: 'Motorcycle',
    car: 'Car',
    bus: 'Bus',
    truck: 'Truck',
    heavy_vehicle: 'Lorry',
    lorry: 'Lorry',
    tanker: 'Tanker',
  };
  return mapping[vehType] || 'Unknown';
};

const mapRoadNameToCorridor = (locationName?: string, roadName?: string): string => {
  const text = `${locationName || ''} ${roadName || ''}`.toLowerCase();
  if (text.includes('tumkur')) return 'Tumkur Road';
  if (text.includes('outer ring') || text.includes('orr')) return 'Outer Ring Road';
  if (text.includes('mg road')) return 'MG Road';
  if (text.includes('hosur')) return 'Hosur Road';
  if (text.includes('old madras') || text.includes('omr')) return 'Old Madras Road';
  if (text.includes('bannerghatta')) return 'Bannerghatta Road';
  if (text.includes('mysore')) return 'Mysore Road';
  if (text.includes('sarjapur')) return 'Sarjapur Road';
  if (text.includes('bellary')) return 'Bellary Road';
  if (text.includes('nh 44') || text.includes('nh44')) return 'NH 44';
  return '';
};

function getSupportedAudioMimeType() {
  if (typeof window === 'undefined' || !window.MediaRecorder?.isTypeSupported) {
    return '';
  }
  return [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/ogg'
  ].find((mimeType) => window.MediaRecorder.isTypeSupported(mimeType)) || '';
}

/**
 * New Incident Submission — two-column layout.
 * LEFT: voice/text input + extracted form.
 * RIGHT: AI Copilot Panel (slides in after prediction).
 *
 * CRITICAL: Form MUST NOT auto-submit. Submit button requires explicit click.
 */
export default function NewIncidentPage() {
  // Form state
  const [transcript, setTranscript] = useState('');
  const [incidentType, setIncidentType] = useState('');
  const [eventCause, setEventCause] = useState('');
  const [vehicleType, setVehicleType] = useState('');
  const [corridor, setCorridor] = useState('');
  const [location, setLocation] = useState('');

  // Input Mode: 'manual' | 'dictation' | 'assistant'
  const [inputMode, setInputMode] = useState<'manual' | 'dictation' | 'assistant'>('manual');

  // Interactive AI Assistant states
  const [streamingCallActive, setStreamingCallActive] = useState(false);
  const [streamingCallStatus, setStreamingCallStatus] = useState<'idle' | 'connecting' | 'listening' | 'processing' | 'speaking' | 'completed'>('idle');
  const [streamingTranscript, setStreamingTranscript] = useState('');
  const [chatHistory, setChatHistory] = useState<{ sender: 'ai' | 'user'; text: string }[]>([]);

  // AI badge tracking (which fields were AI-filled)
  const [aiFilledFields, setAiFilled] = useState<Set<string>>(new Set());
  const [editedFields, setEditedFields] = useState<Set<string>>(new Set());

  // Recording state (Simple Dictation via native Web Speech API)
  const { isListening, error: webSpeechError, toggleListening } = useWebSpeech({
    onTranscript: (t) => setTranscript(prev => prev ? prev + ' ' + t : t)
  });
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  // Websocket and recording refs (Interactive Voice Assistant)
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const rAFRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const startTimeRef = useRef<number>(0);
  const chatHistoryRef = useRef<{ sender: 'ai' | 'user'; text: string }[]>([]);

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [predicting, setPredicting] = useState(false);

  // Keep chatHistoryRef updated for access in callbacks
  useEffect(() => {
    chatHistoryRef.current = chatHistory;
  }, [chatHistory]);

  // Clean up all resources when component unmounts or mode changes
  useEffect(() => {
    return () => {
      cleanupStreamingCall();
    };
  }, []);

  const getWsUrl = () => {
    const url = process.env.NEXT_PUBLIC_FASTAPI_URL || 'http://localhost:8000';
    return url.replace(/^http/, 'ws') + '/ws/voice-call';
  };

  const cleanupStreamingCall = () => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (rAFRef.current) {
      cancelAnimationFrame(rAFRef.current);
      rAFRef.current = null;
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    mediaRecorderRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    analyserRef.current = null;
  };

  const speak = (text: string, onEnd?: () => void) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find(v => v.lang.startsWith('en') && v.name.includes('Google')) || voices.find(v => v.lang.startsWith('en'));
    if (preferredVoice) utterance.voice = preferredVoice;
    utterance.onend = () => {
      onEnd?.();
    };
    utterance.onerror = () => {
      onEnd?.();
    };
    window.speechSynthesis.speak(utterance);
  };

  const handleStartStreamingCall = async () => {
    cleanupStreamingCall();
    setStreamingCallActive(true);
    setStreamingCallStatus('connecting');
    setStreamingTranscript('');
    setChatHistory([{ sender: 'ai', text: 'Connecting...' }]);
    setAiFilled(new Set());
    setEditedFields(new Set());

    const wsUrl = getWsUrl();
    console.log('Connecting to WebSocket:', wsUrl);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStreamingCallStatus('speaking');
    };

    ws.onmessage = async (event) => {
      const data = JSON.parse(event.data);
      console.log('WebSocket received:', data);

      if (data.type === 'ai_question') {
        const questionText = data.text;
        setChatHistory(prev => [...prev.filter(c => c.text !== 'Connecting...'), { sender: 'ai', text: questionText }]);
        setStreamingCallStatus('speaking');
        speakStreamingAIQuestion(questionText);
      } else if (data.type === 'transcript') {
        if (data.text) {
          setStreamingTranscript(prev => prev ? prev + '\n' + data.text : data.text);
          setChatHistory(prev => [...prev, { sender: 'user', text: data.text }]);
        }
      } else if (data.type === 'current_incident') {
        const incident = data.incident;
        if (incident) {
          const filled = new Set<string>();
          if (incident.event_type) {
            const mappedType = mapEventTypeToIncidentType(incident.event_type);
            if (mappedType) {
              setIncidentType(mappedType);
              filled.add('incidentType');
            }
          }
          if (incident.vehicle_type) {
            const mappedVeh = mapVehicleTypeToVehicleType(incident.vehicle_type);
            if (mappedVeh) {
              setVehicleType(mappedVeh);
              filled.add('vehicleType');
            }
          }
          const mappedCorr = mapRoadNameToCorridor(incident.location_name, incident.road_name);
          if (mappedCorr) {
            setCorridor(mappedCorr);
            filled.add('corridor');
          } else if (incident.road_name) {
            const matchedCorr = CORRIDORS.find(c => c.toLowerCase().includes(incident.road_name.toLowerCase()));
            if (matchedCorr) {
              setCorridor(matchedCorr);
              filled.add('corridor');
            }
          }
          
          const loc = incident.location_name || incident.location_query || incident.road_name || '';
          if (loc) {
            setLocation(loc);
            filled.add('location');
          }
          
          if (incident.event_cause) {
            setEventCause(incident.event_cause);
            filled.add('eventCause');
          }

          setAiFilled(prev => new Set([...prev, ...filled]));
        }
      } else if (data.type === 'complete') {
        setStreamingCallStatus('completed');
        const completionMsg = data.message || 'Thank you. The details are complete.';
        setChatHistory(prev => [...prev, { sender: 'ai', text: completionMsg }]);
        speakStreamingAIQuestion(completionMsg, () => {
          setStreamingCallActive(false);
        });

        const finalInc = data.incident;
        if (finalInc) {
          if (finalInc.event_type) setIncidentType(mapEventTypeToIncidentType(finalInc.event_type));
          if (finalInc.vehicle_type) setVehicleType(mapVehicleTypeToVehicleType(finalInc.vehicle_type));
          const mappedCorr = mapRoadNameToCorridor(finalInc.location_name, finalInc.road_name);
          if (mappedCorr) setCorridor(mappedCorr);
          const loc = finalInc.location_name || finalInc.location_query || finalInc.road_name || '';
          if (loc) setLocation(loc);
          if (finalInc.event_cause) setEventCause(finalInc.event_cause);
        }

        const chatLog = chatHistoryRef.current
          .map(c => `${c.sender.toUpperCase()}: ${c.text}`)
          .join('\n');
        setTranscript(prev => prev ? prev + '\n\nVoice Call Log:\n' + chatLog : 'Voice Call Log:\n' + chatLog);
        cleanupStreamingCall();
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket Error:', err);
      setStreamingCallStatus('idle');
      setStreamingCallActive(false);
      setChatHistory(prev => [...prev, { sender: 'ai', text: 'Error connecting to voice assistant.' }]);
    };

    ws.onclose = () => {
      console.log('WebSocket closed');
      setStreamingCallActive(false);
    };
  };

  const speakStreamingAIQuestion = (text: string, onDone?: () => void) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'ai_speaking', value: true }));
    }
    speak(text, () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ai_speaking', value: false }));
        startStreamingSegment();
      }
      onDone?.();
    });
  };

  const startStreamingSegment = async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setStreamingCallStatus('listening');
    startTimeRef.current = Date.now();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const audioContext = new AudioContextClass();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      analyserRef.current = analyser;

      const mimeType = getSupportedAudioMimeType() || 'audio/webm';
      const recorder = new MediaRecorder(stream, { mimeType });
      const chunks: Blob[] = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());
        if (audioContext.state !== 'closed') {
          await audioContext.close().catch(() => {});
        }

        const duration = Date.now() - startTimeRef.current;
        if (chunks.length > 0 && duration >= STREAMING_MIN_RECORDING_MS) {
          const blob = new Blob(chunks, { type: mimeType });
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            setStreamingCallStatus('processing');
            const arrayBuffer = await blob.arrayBuffer();
            wsRef.current.send(arrayBuffer);
          }
        } else {
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            startStreamingSegment();
          }
        }
      };

      recorder.start(100);
      mediaRecorderRef.current = recorder;

      let silenceStart = Date.now();
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Float32Array(bufferLength);

      const checkVolume = () => {
        if (!analyserRef.current || recorder.state === 'inactive') return;
        
        analyserRef.current.getFloatTimeDomainData(dataArray);
        
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i] * dataArray[i];
        }
        const rms = Math.sqrt(sum / bufferLength);

        const now = Date.now();
        const duration = now - startTimeRef.current;

        if (rms > STREAMING_VOICE_THRESHOLD) {
          silenceStart = now;
        }

        const silenceDuration = now - silenceStart;

        if (duration >= STREAMING_MAX_RECORDING_MS) {
          console.log('Max recording duration reached:', duration);
          recorder.stop();
        } else if (duration >= STREAMING_MIN_RECORDING_MS && silenceDuration >= STREAMING_SILENCE_DURATION_MS) {
          console.log('Silence detected, duration:', silenceDuration);
          recorder.stop();
        } else {
          rAFRef.current = requestAnimationFrame(checkVolume);
        }
      };

      rAFRef.current = requestAnimationFrame(checkVolume);

    } catch (err) {
      console.error('Failed to access microphone for streaming:', err);
      setStreamingCallStatus('idle');
      setStreamingCallActive(false);
    }
  };

  // ── Voice recording (Simple Dictation) ────────────────────────────────────
  // Removed old backend STT in favor of native browser Web Speech API.

  // ── Field change tracking ────────────────────────────────────────────────

  const handleFieldChange = (field: string, setter: (v: string) => void, value: string) => {
    setter(value);
    if (aiFilledFields.has(field)) {
      setEditedFields(prev => new Set(prev).add(field));
    }
  };

  // ── Submit ───────────────────────────────────────────────────────────────

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!corridor || !location) {
      setSubmitError('Corridor and Location are required.');
      return;
    }

    setSubmitError('');
    setPredicting(true);

    try {
      const now = new Date();
      const hour = now.getHours();
      const month = now.getMonth() + 1;
      const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      const dayOfWeek = dayNames[now.getDay()];
      const isPeakHour = [8, 9, 10, 17, 18, 19, 20].includes(hour) ? 1 : 0;
      const isWeekend = [0, 6].includes(now.getDay()) ? 1 : 0;

      const payload = {
        incident_type: incidentType || undefined,
        event_type_grouped: incidentType || 'unknown',
        event_cause: eventCause || 'unknown',
        corridor,
        location,
        vehicle_type: vehicleType || 'unknown',
        veh_type_grouped: vehicleType || 'unknown',
        hour_of_day: hour,
        month,
        day_of_week: dayOfWeek,
        is_peak_hour: isPeakHour,
        is_weekend: isWeekend,
        raw_transcript: transcript || undefined,
      };

      const result = await predict(payload);
      setPrediction(result);
    } catch (err) {
      const apiErr = err as FinalApiError;
      setSubmitError(apiErr.message || 'Failed to submit incident.');
    } finally {
      setPredicting(false);
    }
  };

  const isSubmitDisabled = (!corridor || !location) || predicting;

  const renderFieldLabel = (field: string, label: string) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <span className="form-label">{label}</span>
      {aiFilledFields.has(field) && !editedFields.has(field) && (
        <span className="ai-badge">AI</span>
      )}
      {editedFields.has(field) && (
        <span style={{ fontSize: '10px', color: 'var(--color-text-secondary)', fontStyle: 'italic' }}>edited</span>
      )}
    </div>
  );

  return (
    <>
      <PageHeading title="New Incident" />
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }} className="flex-1 px-4 md:px-7 pb-7 overflow-auto">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_420px] gap-6 max-w-[1280px]">
            {/* LEFT: Input form */}
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

              {/* Voice / Text toggle */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <style>{`
                  @keyframes pulse {
                    0% { opacity: 0.6; }
                    50% { opacity: 1; transform: scale(1.05); }
                    100% { opacity: 0.6; }
                  }
                  @keyframes bounce {
                    0% { height: 4px; }
                    100% { height: 20px; }
                  }
                `}</style>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <h2 style={{ fontSize: '13px', fontWeight: 700 }}>Incident Input</h2>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      onClick={() => {
                        setInputMode('manual');
                        cleanupStreamingCall();
                      }}
                      style={{
                        padding: '4px 10px',
                        borderRadius: '20px',
                        fontSize: '11px',
                        fontWeight: 600,
                        background: inputMode === 'manual' ? '#111111' : 'transparent',
                        color: inputMode === 'manual' ? '#ffffff' : 'var(--color-text-secondary)',
                        border: '1px solid ' + (inputMode === 'manual' ? '#111111' : 'var(--color-border)'),
                        cursor: 'pointer',
                        transition: 'all 0.15s'
                      }}
                    >
                      <Type size={10} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'text-top' }} />
                      Manual
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setInputMode('dictation');
                        cleanupStreamingCall();
                      }}
                      style={{
                        padding: '4px 10px',
                        borderRadius: '20px',
                        fontSize: '11px',
                        fontWeight: 600,
                        background: inputMode === 'dictation' ? '#111111' : 'transparent',
                        color: inputMode === 'dictation' ? '#ffffff' : 'var(--color-text-secondary)',
                        border: '1px solid ' + (inputMode === 'dictation' ? '#111111' : 'var(--color-border)'),
                        cursor: 'pointer',
                        transition: 'all 0.15s'
                      }}
                    >
                      <Mic size={10} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'text-top' }} />
                      Dictation
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setInputMode('assistant');
                      }}
                      style={{
                        padding: '4px 10px',
                        borderRadius: '20px',
                        fontSize: '11px',
                        fontWeight: 600,
                        background: inputMode === 'assistant' ? '#B9E63F' : 'transparent',
                        color: '#111111',
                        border: '1px solid ' + (inputMode === 'assistant' ? '#B9E63F' : 'var(--color-border)'),
                        cursor: 'pointer',
                        transition: 'all 0.15s',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      <MessageSquare size={10} />
                      AI Assistant
                    </button>
                  </div>
                </div>

                {inputMode === 'dictation' && (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', padding: '12px 0' }}>
                    <button
                      id="mic-toggle-btn"
                      type="button"
                      className={`mic-button ${isListening ? 'recording' : ''}`}
                      onClick={toggleListening}
                      title={isListening ? 'Stop recording' : 'Start recording'}
                    >
                      {isListening ? <MicOff size={24} color="#fff" /> : <Mic size={24} color="#151515" />}
                    </button>
                    {isListening && (
                      <span style={{ fontSize: '12px', color: 'var(--p1)', fontWeight: 500 }}>
                        Recording — click to stop
                      </span>
                    )}
                    {webSpeechError && <span style={{ fontSize: '11px', color: 'var(--p1)' }}>{webSpeechError}</span>}
                  </div>
                )}

                {inputMode === 'assistant' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', padding: '16px', background: '#F8FAF6', borderRadius: '16px', border: '1px dashed var(--color-border)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{
                          width: '10px',
                          height: '10px',
                          borderRadius: '50%',
                          backgroundColor: streamingCallActive
                            ? (streamingCallStatus === 'listening' ? '#B9E63F' : '#E53E3E')
                            : '#A0A0A0',
                          animation: (streamingCallActive && streamingCallStatus === 'listening') ? 'pulse 1.5s infinite' : 'none'
                        }} />
                        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                          {streamingCallActive ? `Status: ${streamingCallStatus}` : 'Assistant Offline'}
                        </span>
                      </div>
                      
                      {!streamingCallActive ? (
                        <button
                          type="button"
                          onClick={handleStartStreamingCall}
                          className="btn-accent"
                          style={{ backgroundColor: '#B9E63F', color: '#111111', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', padding: '6px 12px', border: 'none' }}
                        >
                          <Play size={12} /> Start Call
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={cleanupStreamingCall}
                          className="btn-danger"
                          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', cursor: 'pointer' }}
                        >
                          <Square size={12} /> Stop Call
                        </button>
                      )}
                    </div>

                    {streamingCallActive && streamingCallStatus === 'listening' && (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', height: '20px' }}>
                        {[1, 2, 3, 4, 5].map((i) => (
                          <div
                            key={i}
                            style={{
                              width: '3px',
                              backgroundColor: '#B9E63F',
                              borderRadius: '2px',
                              animation: `bounce 0.8s ease-in-out infinite alternate`,
                              animationDelay: `${i * 0.15}s`,
                              height: '100%'
                            }}
                          />
                        ))}
                      </div>
                    )}

                    <div style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '10px',
                      maxHeight: '180px',
                      overflowY: 'auto',
                      padding: '10px',
                      background: '#ffffff',
                      borderRadius: '12px',
                      border: '1px solid var(--color-border)'
                    }}>
                      {chatHistory.length === 0 ? (
                        <div style={{ fontSize: '11px', color: 'var(--color-text-tertiary)', textAlign: 'center', padding: '12px' }}>
                          Click "Start Call" to begin voice dialog session.
                        </div>
                      ) : (
                        chatHistory.map((chat, idx) => (
                          <div
                            key={idx}
                            style={{
                              alignSelf: chat.sender === 'ai' ? 'flex-start' : 'flex-end',
                              backgroundColor: chat.sender === 'ai' ? '#F3F4F1' : '#B9E63F',
                              color: '#111111',
                              padding: '8px 12px',
                              borderRadius: chat.sender === 'ai' ? '12px 12px 12px 2px' : '12px 12px 2px 12px',
                              maxWidth: '85%',
                              fontSize: '12px',
                              lineHeight: 1.4,
                            }}
                          >
                            {chat.text}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}

                {/* Transcript */}
                <div className="form-group">
                  <label htmlFor="transcript" className="form-label">
                    {inputMode === 'manual' ? 'Incident Description' : 'Live Transcript'}
                  </label>
                  <textarea
                    id="transcript"
                    className="textarea"
                    value={transcript}
                    onChange={e => setTranscript(e.target.value)}
                    placeholder={inputMode === 'manual' ? 'Describe the incident in detail…' : 'Transcript will appear here after recording…'}
                    rows={5}
                  />
                </div>
              </div>

              {/* Extracted Fields */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-secondary)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                  Incident Details
                </h3>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="form-group">
                    {renderFieldLabel('incidentType', 'Incident Type')}
                    <select
                      id="incident-type"
                      className="select"
                      value={incidentType}
                      onChange={e => handleFieldChange('incidentType', setIncidentType, e.target.value)}
                    >
                      <option value="">Select type…</option>
                      {INCIDENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>

                  <div className="form-group">
                    {renderFieldLabel('vehicleType', 'Vehicle Type')}
                    <select
                      id="vehicle-type"
                      className="select"
                      value={vehicleType}
                      onChange={e => handleFieldChange('vehicleType', setVehicleType, e.target.value)}
                    >
                      <option value="">Select type…</option>
                      {VEHICLE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  {renderFieldLabel('corridor', 'Corridor *')}
                  <select
                    id="corridor"
                    className="select"
                    value={corridor}
                    onChange={e => handleFieldChange('corridor', setCorridor, e.target.value)}
                    required
                  >
                    <option value="">Select corridor…</option>
                    {CORRIDORS.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>

                <div className="form-group">
                  {renderFieldLabel('location', 'Location / Junction *')}
                  <input
                    id="location"
                    type="text"
                    className="input"
                    value={location}
                    onChange={e => handleFieldChange('location', setLocation, e.target.value)}
                    placeholder="e.g. Near Peenya Flyover, 2nd Junction"
                    required
                  />
                </div>

                <div className="form-group">
                  {renderFieldLabel('eventCause', 'Event Cause')}
                  <input
                    id="event-cause"
                    type="text"
                    className="input"
                    value={eventCause}
                    onChange={e => handleFieldChange('eventCause', setEventCause, e.target.value)}
                    placeholder="e.g. Tyre burst, Engine failure"
                  />
                </div>
              </div>

              {/* System fields (read-only) */}
              <div className="card" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
                {[
                  { label: 'Date', value: new Date().toLocaleDateString('en-IN') },
                  { label: 'Time', value: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) },
                  { label: 'Day', value: new Date().toLocaleDateString('en-IN', { weekday: 'long' }) },
                ].map(({ label, value }) => (
                  <div key={label} className="form-group">
                    <span className="form-label">{label}</span>
                    <input
                      type="text"
                      className="input"
                      value={value}
                      readOnly
                      style={{ opacity: 0.55, cursor: 'default', background: '#F5F6F4' }}
                    />
                  </div>
                ))}
              </div>

              {/* Errors */}
              <AnimatePresence>
                {submitError && (
                  <motion.div 
                    initial={{ opacity: 0, height: 0 }} 
                    animate={{ opacity: 1, height: 'auto' }} 
                    exit={{ opacity: 0, height: 0 }}
                    style={{ overflow: 'hidden' }}
                  >
                    <div style={{ padding: '10px 14px', background: 'rgba(229,62,62,0.08)', border: '1px solid rgba(229,62,62,0.2)', borderRadius: '8px', fontSize: '12px', color: 'var(--p1)', marginTop: '8px', marginBottom: '8px' }}>
                      {submitError}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Submit */}
              <button
                id="submit-incident"
                type="submit"
                className={`btn-primary hover:scale-[1.02] active:scale-95 transition-all focus:ring-2 focus:ring-gray-400 focus:outline-none ${predicting ? 'opacity-80' : ''}`}
                disabled={isSubmitDisabled}
                style={{ alignSelf: 'flex-start', minWidth: '160px' }}
              >
                {predicting ? (
                  <><Loader2 size={14} className="animate-spin" /> Predicting…</>
                ) : (
                  'Submit Incident'
                )}
              </button>
            </form>

            {/* RIGHT: AI Copilot Panel */}
            <div style={{ position: 'sticky', top: '24px', alignSelf: 'flex-start' }}>
              <CopilotPanel
                prediction={prediction}
                isLoading={predicting}
              />
            </div>
          </div>
      </motion.div>
    </>
  );
}
