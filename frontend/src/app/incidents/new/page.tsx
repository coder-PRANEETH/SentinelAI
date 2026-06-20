'use client';
import { useState, useRef, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { CopilotPanel } from '@/components/copilot/CopilotPanel';
import { PageHeading } from '@/components/layout/PageHeading';
import { api, PredictResponse } from '@/lib/api';
import { Mic, MicOff, Type, Loader2 } from 'lucide-react';
import type { ApiError } from '@/lib/api';

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

/**
 * New Incident Submission — two-column layout.
 * LEFT: voice/text input + extracted form.
 * RIGHT: AI Copilot Panel (slides in after prediction).
 *
 * CRITICAL: Form MUST NOT auto-submit. Submit button requires explicit click.
 */
export default function NewIncidentPage() {
  const router = useRouter();

  // Form state
  const [transcript, setTranscript] = useState('');
  const [incidentType, setIncidentType] = useState('');
  const [eventCause, setEventCause] = useState('');
  const [vehicleType, setVehicleType] = useState('');
  const [corridor, setCorridor] = useState('');
  const [location, setLocation] = useState('');
  const [useTextInput, setUseTextInput] = useState(false);

  // AI badge tracking (which fields were AI-filled)
  const [aiFilledFields, setAiFilled] = useState<Set<string>>(new Set());
  const [editedFields, setEditedFields] = useState<Set<string>>(new Set());

  // Recording state
  const [isRecording, setIsRecording] = useState(false);
  const [recError, setRecError] = useState('');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [predicting, setPredicting] = useState(false);
  const [incidentId, setIncidentId] = useState<string | null>(null);

  // ── Voice recording ───────────────────────────────────────────────────────

  const startRecording = async () => {
    setRecError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size) audioChunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        try {
          const res = await api.predict.stt(audioBlob);
          if (res.success && res.transcript) {
            setTranscript(res.transcript);
          }
        } catch (err) {
          setRecError('Transcription failed. Please try typing.');
        }
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch (err) {
      setRecError('Microphone access denied. Please allow microphone access and try again.');
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  };

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

      const result = await api.predict.run(payload);
      setPrediction(result);

      if (result.incident?.incident_id) {
        setIncidentId(result.incident.incident_id as string);
        router.push(`/incidents/${result.incident.incident_id}?new=1`, { scroll: false });
      }
    } catch (err) {
      const apiErr = err as ApiError;
      setSubmitError(apiErr.message || 'Failed to submit incident.');
    } finally {
      setPredicting(false);
    }
  };

  const isSubmitDisabled = (!corridor || !location) || predicting;

  const FieldLabel = ({ field, label }: { field: string; label: string }) => (
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
      <div className="flex-1 px-7 pb-7 overflow-auto">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 420px', gap: '24px', maxWidth: '1280px' }}>
            {/* LEFT: Input form */}
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

              {/* Voice / Text toggle */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <h2 style={{ fontSize: '13px', fontWeight: 700 }}>Incident Input</h2>
                  <button
                    type="button"
                    onClick={() => setUseTextInput(t => !t)}
                    style={{ fontSize: '12px', color: 'var(--color-text-secondary)', background: 'none', border: 'none', cursor: 'pointer' }}
                  >
                    {useTextInput ? '🎙 Switch to voice' : <><Type size={12} style={{ display: 'inline', marginRight: '4px' }} />Type instead</>}
                  </button>
                </div>

                {!useTextInput ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                    <button
                      id="mic-toggle-btn"
                      type="button"
                      className={`mic-button ${isRecording ? 'recording' : ''}`}
                      onClick={isRecording ? stopRecording : startRecording}
                      title={isRecording ? 'Stop recording' : 'Start recording'}
                    >
                      {isRecording ? <MicOff size={24} color="#fff" /> : <Mic size={24} color="#151515" />}
                    </button>
                    {isRecording && (
                      <span style={{ fontSize: '12px', color: 'var(--p1)', fontWeight: 500 }}>
                        Recording — click to stop
                      </span>
                    )}
                    {recError && <span style={{ fontSize: '11px', color: 'var(--p1)' }}>{recError}</span>}
                  </div>
                ) : null}

                {/* Transcript */}
                <div className="form-group">
                  <label htmlFor="transcript" className="form-label">
                    {useTextInput ? 'Incident Description' : 'Live Transcript'}
                  </label>
                  <textarea
                    id="transcript"
                    className="textarea"
                    value={transcript}
                    onChange={e => setTranscript(e.target.value)}
                    placeholder={useTextInput ? 'Describe the incident in detail…' : 'Transcript will appear here after recording…'}
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
                    <FieldLabel field="incidentType" label="Incident Type" />
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
                    <FieldLabel field="vehicleType" label="Vehicle Type" />
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
                  <FieldLabel field="corridor" label="Corridor *" />
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
                  <FieldLabel field="location" label="Location / Junction *" />
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
                  <FieldLabel field="eventCause" label="Event Cause" />
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
              {submitError && (
                <div style={{ padding: '10px 14px', background: 'rgba(229,62,62,0.08)', border: '1px solid rgba(229,62,62,0.2)', borderRadius: '8px', fontSize: '12px', color: 'var(--p1)' }}>
                  {submitError}
                </div>
              )}

              {/* Submit */}
              <button
                id="submit-incident"
                type="submit"
                className="btn-primary"
                disabled={isSubmitDisabled}
                style={{ alignSelf: 'flex-start', minWidth: '160px' }}
              >
                {predicting ? (
                  <><Loader2 size={14} className="animate-spin" /> Analyzing…</>
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
                incidentId={incidentId ?? undefined}
              />
            </div>
          </div>
      </div>
    </>
  );
}
