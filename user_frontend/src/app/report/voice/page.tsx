"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { ReportProgressSteps } from "@/components/ReportProgressSteps";
import { saveDraftReport } from "@/lib/reportStore";
import type { CarBreakdownReport } from "@/types/incident";
import { Square, Play, Keyboard, Loader2 } from "lucide-react";

const STREAMING_VOICE_THRESHOLD = 0.025;
const STREAMING_SILENCE_DURATION_MS = 1500;
const STREAMING_MIN_RECORDING_MS = 1500;
const STREAMING_MAX_RECORDING_MS = 10000;

type CallStatus = "idle" | "connecting" | "listening" | "processing" | "speaking" | "completed";

function getSupportedAudioMimeType() {
  if (typeof window === "undefined" || !window.MediaRecorder?.isTypeSupported) {
    return "";
  }
  return [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ].find((mimeType) => window.MediaRecorder.isTypeSupported(mimeType)) || "";
}

export default function VoiceReportPage() {
  const router = useRouter();

  const [callActive, setCallActive] = useState(false);
  const [callStatus, setCallStatus] = useState<CallStatus>("idle");
  const [chatHistory, setChatHistory] = useState<{ sender: "ai" | "user"; text: string }[]>([]);
  const [errorMsg, setErrorMsg] = useState("");

  const [useTextMode, setUseTextMode] = useState(false);
  const [textInput, setTextInput] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const rAFRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const chatHistoryRef = useRef<{ sender: "ai" | "user"; text: string }[]>([]);

  useEffect(() => {
    chatHistoryRef.current = chatHistory;
  }, [chatHistory]);

  const getWsUrl = () => {
    const url = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";
    return url.replace(/^http/, "ws") + "/ws/voice-call";
  };

  const cleanupCall = () => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
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
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    mediaRecorderRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    setCallActive(false);
  };

  useEffect(() => {
    return () => {
      cleanupCall();
    };
  }, []);

  const speak = (text: string, onEnd?: () => void) => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      onEnd?.();
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find((v) => v.lang.startsWith("en") && v.name.includes("Google")) || voices.find((v) => v.lang.startsWith("en"));
    if (preferredVoice) utterance.voice = preferredVoice;
    utterance.onend = () => onEnd?.();
    utterance.onerror = () => onEnd?.();
    window.speechSynthesis.speak(utterance);
  };

  const speakAIQuestion = (text: string, onDone?: () => void) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "ai_speaking", value: true }));
    }
    speak(text, () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ai_speaking", value: false }));
        startSegment();
      }
      onDone?.();
    });
  };

  const startSegment = async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setCallStatus("listening");
    startTimeRef.current = Date.now();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioContext = new AudioContextClass();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      analyserRef.current = analyser;

      const mimeType = getSupportedAudioMimeType() || "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType });
      const chunks: Blob[] = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        if (audioContext.state !== "closed") {
          await audioContext.close().catch(() => {});
        }

        const duration = Date.now() - startTimeRef.current;
        if (chunks.length > 0 && duration >= STREAMING_MIN_RECORDING_MS) {
          const blob = new Blob(chunks, { type: mimeType });
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            setCallStatus("processing");
            const arrayBuffer = await blob.arrayBuffer();
            wsRef.current.send(arrayBuffer);
          }
        } else if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          startSegment();
        }
      };

      recorder.start(100);
      mediaRecorderRef.current = recorder;

      let silenceStart = Date.now();
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Float32Array(bufferLength);

      const checkVolume = () => {
        if (!analyserRef.current || recorder.state === "inactive") return;

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
          recorder.stop();
        } else if (duration >= STREAMING_MIN_RECORDING_MS && silenceDuration >= STREAMING_SILENCE_DURATION_MS) {
          recorder.stop();
        } else {
          rAFRef.current = requestAnimationFrame(checkVolume);
        }
      };

      rAFRef.current = requestAnimationFrame(checkVolume);
    } catch {
      setErrorMsg("Microphone access denied. Please allow microphone access and try again.");
      setCallStatus("idle");
      setCallActive(false);
    }
  };

  const finishWithIncident = (inc: Record<string, unknown> | undefined) => {
    const report: CarBreakdownReport = {
      incidentTypeId: (inc?.event_type as CarBreakdownReport["incidentTypeId"]) || "car_breakdown",
      vehicleType: (inc?.vehicle_type as string) || "Unknown",
      issueType: (inc?.event_type as string) || "Other",
      description: (inc?.description as string) || chatHistoryRef.current.filter((c) => c.sender === "user").map((c) => c.text).join(" "),
      location: inc?.latitude && inc?.longitude ? { latitude: inc.latitude as number, longitude: inc.longitude as number } : null,
    };
    saveDraftReport(report);
    router.push("/report/safe-location");
  };

  const handleStartCall = async () => {
    cleanupCall();
    setErrorMsg("");
    setCallActive(true);
    setCallStatus("connecting");
    setChatHistory([{ sender: "ai", text: "Connecting..." }]);

    const ws = new WebSocket(getWsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      setCallStatus("speaking");
    };

    ws.onmessage = async (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "ai_question") {
        const questionText = data.text;
        setChatHistory((prev) => [...prev.filter((c) => c.text !== "Connecting..."), { sender: "ai", text: questionText }]);
        setCallStatus("speaking");
        speakAIQuestion(questionText);
      } else if (data.type === "transcript") {
        if (data.text) {
          setChatHistory((prev) => [...prev, { sender: "user", text: data.text }]);
        }
      } else if (data.type === "complete") {
        setCallStatus("completed");
        const completionMsg = data.message || "Thank you. The details are complete.";
        setChatHistory((prev) => [...prev, { sender: "ai", text: completionMsg }]);
        const finalIncident = data.incident;
        speak(completionMsg, () => {
          cleanupCall();
          finishWithIncident(finalIncident);
        });
      }
    };

    ws.onerror = () => {
      setCallStatus("idle");
      setCallActive(false);
      setErrorMsg("Error connecting to voice assistant. Please try again or use text instead.");
    };

    ws.onclose = () => {
      setCallActive(false);
    };
  };

  const processText = async () => {
    if (!textInput.trim()) return;
    setChatHistory((prev) => [...prev, { sender: "user", text: textInput.trim() }]);
    setTextInput("");
    setUseTextMode(false);
    finishWithIncident({ description: textInput.trim() });
  };

  return (
    <PageShell>
      <ReportProgressSteps currentStep={2} />
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Voice Report</h1>
      <p style={{ fontSize: 14, color: "var(--color-text-2)", marginBottom: 24 }}>
        Speak naturally and we&apos;ll extract the details.
      </p>

      <div className="card fade-up" style={{ display: "flex", flexDirection: "column", gap: 16, marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                backgroundColor: callActive ? (callStatus === "listening" ? "var(--color-accent)" : "var(--err)") : "#A0A0A0",
                animation: callActive && callStatus === "listening" ? "pulse 1.5s infinite" : "none",
              }}
            />
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-1)" }}>
              {callActive ? `Status: ${callStatus}` : "Ready to call"}
            </span>
          </div>

          {!callActive ? (
            <button
              onClick={handleStartCall}
              disabled={useTextMode}
              className="btn-primary"
              style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 16px" }}
            >
              <Play size={14} /> Start Call
            </button>
          ) : (
            <button
              onClick={cleanupCall}
              style={{
                display: "flex", alignItems: "center", gap: 6, padding: "8px 16px",
                borderRadius: 10, border: "1px solid var(--err)", background: "rgba(255,51,102,0.1)",
                color: "var(--err)", fontWeight: 600, fontSize: 13, cursor: "pointer",
              }}
            >
              <Square size={14} /> End Call
            </button>
          )}
        </div>

        {callActive && callStatus === "listening" && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4, height: 20 }}>
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                style={{
                  width: 3,
                  backgroundColor: "var(--color-accent)",
                  borderRadius: 2,
                  animation: "bounce 0.8s ease-in-out infinite alternate",
                  animationDelay: `${i * 0.15}s`,
                  height: "100%",
                }}
              />
            ))}
          </div>
        )}

        {callActive && callStatus === "processing" && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, color: "var(--color-text-2)", fontSize: 13 }}>
            <Loader2 size={14} className="animate-spin" /> Processing...
          </div>
        )}

        {errorMsg && (
          <div style={{ fontSize: 13, color: "var(--err)", textAlign: "center" }}>
            {errorMsg}
          </div>
        )}

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            maxHeight: 240,
            overflowY: "auto",
            padding: 10,
            background: "var(--color-surface-raised)",
            borderRadius: 12,
            border: "1px solid var(--color-border)",
          }}
        >
          {chatHistory.length === 0 ? (
            <div style={{ fontSize: 12, color: "var(--color-text-2)", textAlign: "center", padding: 12 }}>
              Tap &quot;Start Call&quot; and speak naturally to report the incident.
            </div>
          ) : (
            chatHistory.map((chat, idx) => (
              <div
                key={idx}
                style={{
                  alignSelf: chat.sender === "ai" ? "flex-start" : "flex-end",
                  backgroundColor: chat.sender === "ai" ? "var(--color-surface)" : "var(--color-accent)",
                  color: chat.sender === "ai" ? "var(--color-text-1)" : "white",
                  padding: "8px 12px",
                  borderRadius: chat.sender === "ai" ? "12px 12px 12px 2px" : "12px 12px 2px 12px",
                  maxWidth: "85%",
                  fontSize: 13,
                  lineHeight: 1.4,
                }}
              >
                {chat.text}
              </div>
            ))
          )}
        </div>

        {!callActive && (
          <>
            {!useTextMode ? (
              <button
                onClick={() => setUseTextMode(true)}
                style={{ background: "none", border: "none", color: "var(--color-accent)", fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}
              >
                <Keyboard size={16} /> Type instead
              </button>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <textarea
                  className="sel-input"
                  rows={3}
                  placeholder="Describe the incident here..."
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  style={{ resize: "vertical", fontFamily: "inherit" }}
                />
                <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
                  <button
                    onClick={() => setUseTextMode(false)}
                    style={{ background: "none", border: "none", color: "var(--color-text-2)", fontSize: 14, fontWeight: 600, cursor: "pointer" }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={processText}
                    disabled={!textInput.trim()}
                    className="btn-primary"
                    style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 16px" }}
                  >
                    Submit
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

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
