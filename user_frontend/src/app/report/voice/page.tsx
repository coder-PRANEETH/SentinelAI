"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { ReportProgressSteps } from "@/components/ReportProgressSteps";
import { saveDraftReport } from "@/lib/reportStore";
import type { CarBreakdownReport } from "@/types/incident";
import { Mic, MicOff, Type, Loader2 } from "lucide-react";
import { useWebSpeech } from "@/hooks/useWebSpeech";

export default function VoiceReportPage() {
  const router = useRouter();

  const [inputMode, setInputMode] = useState<"manual" | "dictation">("dictation");
  const [transcript, setTranscript] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const { isListening, error: webSpeechError, interimTranscript, toggleListening } = useWebSpeech({
    onTranscript: (t) => setTranscript((prev) => (prev ? prev + " " + t : t)),
  });

  const finishWithIncident = async (finalText: string) => {
    if (!finalText.trim()) return;
    setIsExtracting(true);
    setErrorMsg("");

    try {
      const url = process.env.NEXT_PUBLIC_API_BASE_URL || "https://sentinelai-mdpt.onrender.com";
      const res = await fetch(`${url}/voice-report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: finalText }),
      });

      if (!res.ok) throw new Error("Extraction failed");
      
      const body = await res.json();
      const inc = body.incident || {};

      const report: CarBreakdownReport = {
        incidentTypeId: (inc.event_type as CarBreakdownReport["incidentTypeId"]) || "car_breakdown",
        vehicleType: (inc.vehicle_type as string) || "Unknown",
        issueType: (inc.event_type as string) || "Other",
        description: finalText,
        location: null, // user_frontend handles map location separately
      };
      
      saveDraftReport(report);
      router.push("/report/safe-location");
    } catch (err) {
      console.error(err);
      // Fallback
      const report: CarBreakdownReport = {
        incidentTypeId: "car_breakdown",
        vehicleType: "Unknown",
        issueType: "Other",
        description: finalText,
        location: null,
      };
      saveDraftReport(report);
      router.push("/report/safe-location");
    } finally {
      setIsExtracting(false);
    }
  };

  const processSubmit = () => {
    if (isListening) {
      toggleListening();
    }
    finishWithIncident(transcript);
  };

  return (
    <PageShell>
      <ReportProgressSteps currentStep={2} />
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Voice Report</h1>
      <p style={{ fontSize: 14, color: "var(--color-text-2)", marginBottom: 24 }}>
        Speak naturally and we&apos;ll extract the details.
      </p>

      <div className="card fade-up" style={{ display: "flex", flexDirection: "column", gap: 16, marginBottom: 20 }}>
        <style>{`
          @keyframes pulse {
            0% { opacity: 0.6; }
            50% { opacity: 1; transform: scale(1.05); }
            100% { opacity: 0.6; }
          }
          .sel-input {
            width: 100%;
            background: var(--color-surface-raised);
            border: 1px solid var(--color-border);
            border-radius: 12px;
            padding: 10px 12px;
            color: var(--color-text-1);
            font-size: 14px;
            outline: none;
            transition: border-color 0.15s ease;
          }
          .sel-input:focus {
            border-color: var(--color-accent);
          }
          .textarea {
            width: 100%;
            background: var(--color-surface-raised);
            border: 1px solid var(--color-border);
            border-radius: 12px;
            padding: 16px;
            font-size: 14px;
            line-height: 1.6;
            resize: vertical;
            color: var(--color-text-1);
            outline: none;
          }
          .textarea:focus {
            border-color: var(--color-accent);
          }
        `}</style>
        
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text-1)' }}>Incident Input</h2>
          <div style={{ display: 'flex', gap: '6px' }}>
            <button
              type="button"
              onClick={() => setInputMode('manual')}
              style={{
                padding: '4px 10px',
                borderRadius: '20px',
                fontSize: '11px',
                fontWeight: 600,
                background: inputMode === 'manual' ? 'var(--color-text-1)' : 'transparent',
                color: inputMode === 'manual' ? 'var(--color-surface)' : 'var(--color-text-2)',
                border: '1px solid ' + (inputMode === 'manual' ? 'var(--color-text-1)' : 'var(--color-border)'),
                cursor: 'pointer',
                transition: 'all 0.15s'
              }}
            >
              <Type size={10} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'text-top' }} />
              Manual
            </button>
            <button
              type="button"
              onClick={() => setInputMode('dictation')}
              style={{
                padding: '4px 10px',
                borderRadius: '20px',
                fontSize: '11px',
                fontWeight: 600,
                background: inputMode === 'dictation' ? 'var(--color-text-1)' : 'transparent',
                color: inputMode === 'dictation' ? 'var(--color-surface)' : 'var(--color-text-2)',
                border: '1px solid ' + (inputMode === 'dictation' ? 'var(--color-text-1)' : 'var(--color-border)'),
                cursor: 'pointer',
                transition: 'all 0.15s'
              }}
            >
              <Mic size={10} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'text-top' }} />
              Dictation
            </button>
          </div>
        </div>

        {inputMode === 'manual' ? (
          <div style={{ marginTop: '8px' }}>
            <textarea
              className="textarea"
              value={transcript}
              onChange={e => setTranscript(e.target.value)}
              placeholder="Describe the incident in detail..."
              rows={5}
            />
          </div>
        ) : (
          <div style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            background: 'var(--color-surface-raised)',
            borderRadius: '12px',
            border: '1px solid var(--color-border)',
            marginTop: '8px',
            overflow: 'hidden',
            width: '100%'
          }}>
            <div style={{
              display: 'flex', 
              flexDirection: 'column', 
              alignItems: 'center', 
              justifyContent: 'center',
              padding: '32px 24px',
              background: isListening ? 'rgba(185, 230, 63, 0.05)' : 'transparent',
              borderBottom: transcript ? '1px solid var(--color-border)' : 'none',
              transition: 'background 0.3s'
            }}>
              <div style={{ position: 'relative' }}>
                {isListening && (
                  <div style={{
                    position: 'absolute',
                    top: -8, left: -8, right: -8, bottom: -8,
                    borderRadius: '50%',
                    background: 'var(--color-accent)',
                    opacity: 0.2,
                    animation: 'pulse 1.5s infinite'
                  }} />
                )}
                <button
                  type="button"
                  onClick={toggleListening}
                  title={isListening ? 'Stop recording' : 'Start recording'}
                  style={{ 
                    position: 'relative', 
                    zIndex: 1, 
                    border: '1px solid ' + (isListening ? 'var(--err)' : 'var(--color-border)'), 
                    background: isListening ? 'rgba(255,51,102,0.1)' : 'var(--color-surface)',
                    color: isListening ? 'var(--err)' : 'var(--color-text-2)',
                    width: '48px', height: '48px',
                    borderRadius: '50%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer', transition: 'all 0.2s',
                    boxShadow: isListening ? 'none' : '0 2px 4px rgba(0,0,0,0.05)'
                  }}
                >
                  {isListening ? <MicOff size={20} color="var(--err)" /> : <Mic size={20} />}
                </button>
              </div>
              
              <div style={{ textAlign: 'center', marginTop: '16px' }}>
                <span style={{ fontSize: '13px', color: isListening ? 'var(--color-accent)' : 'var(--color-text-2)', fontWeight: 600 }}>
                  {isListening ? 'Listening...' : 'Click to start dictation'}
                </span>
              </div>
              
              {webSpeechError && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '12px', padding: '6px 12px', background: 'rgba(255,51,102,0.1)', borderRadius: '6px', border: '1px solid var(--err)' }}>
                  <span style={{ fontSize: '12px', color: 'var(--err)', fontWeight: 500 }}>{webSpeechError}</span>
                </div>
              )}
            </div>

            {(transcript || interimTranscript || isListening) && (
              <div style={{ padding: '16px', background: 'rgba(185, 230, 63, 0.05)' }}>
                <textarea
                  value={transcript + (transcript && interimTranscript ? ' ' : '') + interimTranscript}
                  onChange={e => setTranscript(e.target.value)}
                  placeholder="Live transcript..."
                  rows={4}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    padding: '0',
                    fontSize: '14px',
                    lineHeight: '1.6',
                    resize: 'none',
                    outline: 'none',
                    boxShadow: 'none',
                    width: '100%',
                    color: 'var(--color-text-1)'
                  }}
                  ref={(el) => {
                    if (el && isListening) {
                      el.scrollTop = el.scrollHeight;
                    }
                  }}
                />
              </div>
            )}
          </div>
        )}

        {errorMsg && (
          <div style={{ fontSize: 13, color: "var(--err)", textAlign: "center" }}>
            {errorMsg}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
          <button
            onClick={processSubmit}
            disabled={!transcript.trim() || isExtracting}
            className="btn-primary"
            style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 16px" }}
          >
            {isExtracting ? <Loader2 size={16} className="animate-spin" /> : "Submit"}
          </button>
        </div>
      </div>
    </PageShell>
  );
}
