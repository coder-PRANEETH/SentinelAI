"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { ReportProgressSteps } from "@/components/ReportProgressSteps";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";
import { saveDraftReport } from "@/lib/reportStore";
import type { CarBreakdownReport } from "@/types/incident";
import { Mic, Square, Keyboard, Loader2, AlertCircle, RefreshCw } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";

export default function VoiceReportPage() {
  const router = useRouter();
  const { state, elapsed, audioBlob, start, stop, reset } = useVoiceRecorder();

  const [sessionId, setSessionId] = useState<string>("");
  const [currentIncident, setCurrentIncident] = useState<any>({});
  const [nextQuestion, setNextQuestion] = useState<string>("Please describe the incident.");
  const [transcript, setTranscript] = useState<string>("");
  
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const [useTextMode, setUseTextMode] = useState(false);
  const [textInput, setTextInput] = useState("");

  // Process audio when recording stops
  useEffect(() => {
    if (state === "stopped" && audioBlob && !isProcessing) {
      processAudio(audioBlob);
    }
  }, [state, audioBlob]);

  const processAudio = async (blob: Blob) => {
    setIsProcessing(true);
    setErrorMsg("");
    setTranscript("");
    
    try {
      const formData = new FormData();
      formData.append("audio", blob, "voice.webm");
      if (sessionId) formData.append("session_id", sessionId);
      if (Object.keys(currentIncident).length > 0) {
        formData.append("current_incident_json", JSON.stringify(currentIncident));
      }

      const res = await fetch(`${API_URL}/interactive-voice-audio-turn`, {
        method: "POST",
        body: formData,
      });
      
      if (!res.ok) throw new Error("Network request failed");
      const data = await res.json();
      
      handleTurnResponse(data);
    } catch (err: any) {
      setErrorMsg("Failed to process audio. Please try again.");
    } finally {
      setIsProcessing(false);
      reset();
    }
  };

  const processText = async () => {
    if (!textInput.trim()) return;
    setIsProcessing(true);
    setErrorMsg("");
    setTranscript("");

    try {
      const res = await fetch(`${API_URL}/interactive-voice-turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: textInput,
          session_id: sessionId || undefined,
          current_incident: currentIncident,
        }),
      });

      if (!res.ok) throw new Error("Network request failed");
      const data = await res.json();

      setTextInput("");
      setUseTextMode(false);
      handleTurnResponse(data);
    } catch (err: any) {
      setErrorMsg("Failed to submit text. Please try again.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleTurnResponse = (data: any) => {
    if (data.error === "empty_transcript") {
      setErrorMsg("Audio too short or silent. Please try speaking again.");
      return;
    }

    if (data.session_id) setSessionId(data.session_id);
    if (data.transcript) setTranscript(data.transcript);

    if (data.complete && data.incident) {
      // Map to CarBreakdownReport and route to review
      const inc = data.incident;
      const report: CarBreakdownReport = {
        incidentTypeId: (inc.event_type as any) || "car_breakdown",
        vehicleType: inc.vehicle_type || "Unknown",
        issueType: inc.event_type || "Other",
        description: inc.description || data.transcript,
        location: inc.latitude && inc.longitude ? { latitude: inc.latitude, longitude: inc.longitude } : null,
      };
      saveDraftReport(report);
      router.push("/report/safe-location");
    } else {
      if (data.current_incident) setCurrentIncident(data.current_incident);
      if (data.next_question) setNextQuestion(data.next_question);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <PageShell>
      <ReportProgressSteps currentStep={2} />
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Voice Report</h1>
      <p style={{ fontSize: 14, color: "var(--color-text-2)", marginBottom: 24 }}>
        Speak naturally and we&apos;ll extract the details.
      </p>

      {state === "permission_denied" && (
        <div className="card" style={{ backgroundColor: "rgba(255, 51, 102, 0.1)", border: "1px solid var(--err)" }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <AlertCircle size={24} color="var(--err)" />
            <div style={{ fontSize: 14, color: "var(--color-text-1)" }}>
              Microphone access denied. Please enable it in your browser settings to use voice report.
            </div>
          </div>
        </div>
      )}

      {state === "no_device" && (
        <div className="card" style={{ backgroundColor: "rgba(255, 150, 0, 0.1)", border: "1px solid rgb(255, 150, 0)" }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <AlertCircle size={24} color="rgb(255, 150, 0)" />
            <div style={{ fontSize: 14, color: "var(--color-text-1)" }}>
              No microphone found. Please connect a microphone or use text.
            </div>
          </div>
        </div>
      )}

      <div className="card fade-up" style={{ display: "flex", flexDirection: "column", gap: 20, marginBottom: 20 }}>
        <div style={{ fontSize: 18, fontWeight: 600, color: "var(--color-text-1)", textAlign: "center" }}>
          {nextQuestion}
        </div>

        {transcript && (
          <div style={{ fontSize: 13, color: "var(--color-text-2)", fontStyle: "italic", textAlign: "center" }}>
            Heard: &quot;{transcript}&quot;
          </div>
        )}

        {errorMsg && (
          <div style={{ fontSize: 13, color: "var(--err)", textAlign: "center" }}>
            {errorMsg}
          </div>
        )}

        {!useTextMode ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, marginTop: 10 }}>
            {state === "recording" ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                <div style={{ fontSize: 24, fontWeight: 700, color: "var(--color-accent)", fontVariantNumeric: "tabular-nums" }}>
                  {formatTime(elapsed)}
                </div>
                <button
                  onClick={stop}
                  className="btn-primary"
                  style={{
                    width: 72, height: 72, borderRadius: 36, display: "flex", alignItems: "center", justifyContent: "center",
                    backgroundColor: "var(--err)", color: "white", padding: 0
                  }}
                >
                  <Square size={28} fill="currentColor" />
                </button>
                <div style={{ fontSize: 13, color: "var(--color-text-2)", fontWeight: 500 }}>Tap to stop</div>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                <button
                  onClick={start}
                  disabled={isProcessing || state === "permission_denied" || state === "no_device"}
                  className="btn-primary"
                  style={{
                    width: 72, height: 72, borderRadius: 36, display: "flex", alignItems: "center", justifyContent: "center",
                    padding: 0, opacity: isProcessing ? 0.7 : 1
                  }}
                >
                  {isProcessing ? <Loader2 size={32} className="animate-spin" /> : <Mic size={32} />}
                </button>
                <div style={{ fontSize: 13, color: "var(--color-text-2)", fontWeight: 500 }}>
                  {isProcessing ? "Processing..." : "Tap to speak"}
                </div>
              </div>
            )}

            {!isProcessing && state !== "recording" && (
              <button 
                onClick={() => setUseTextMode(true)}
                style={{ background: "none", border: "none", color: "var(--color-accent)", fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", gap: 6, cursor: "pointer", marginTop: 12 }}
              >
                <Keyboard size={16} /> Type instead
              </button>
            )}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <textarea
              className="sel-input"
              rows={3}
              placeholder="Type your response here..."
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              style={{ resize: "vertical", fontFamily: "inherit" }}
              disabled={isProcessing}
            />
            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button 
                onClick={() => setUseTextMode(false)}
                disabled={isProcessing}
                style={{ background: "none", border: "none", color: "var(--color-text-2)", fontSize: 14, fontWeight: 600, cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                onClick={processText}
                disabled={isProcessing || !textInput.trim()}
                className="btn-primary"
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 16px" }}
              >
                {isProcessing ? <Loader2 size={16} className="animate-spin" /> : null}
                {isProcessing ? "Submitting..." : "Submit"}
              </button>
            </div>
          </div>
        )}
      </div>

      <style>{`
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
        .animate-spin {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </PageShell>
  );
}
