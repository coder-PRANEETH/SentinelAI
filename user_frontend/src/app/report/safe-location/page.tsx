"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { ReportProgressSteps } from "@/components/ReportProgressSteps";
import { UserMapPanel } from "@/components/UserMapPanel";
import { SafeLocationCard } from "@/components/SafeLocationCard";
import { findNearestSafeLocations, submitIncidentReport } from "@/lib/api";
import { loadDraftReport, saveSubmissionResult } from "@/lib/reportStore";
import type { CarBreakdownReport, SafeLocation } from "@/types/incident";

export default function SafeLocationPage() {
  const router = useRouter();
  const [report, setReport] = useState<CarBreakdownReport | null>(null);
  const [safeLocations, setSafeLocations] = useState<SafeLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const draft = loadDraftReport();
    setReport(draft);

    if (draft?.location) {
      findNearestSafeLocations(draft.location)
        .then(setSafeLocations)
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const handleSubmit = async () => {
    if (!report) {
      router.push("/report/car-breakdown");
      return;
    }
    setSubmitting(true);
    const result = await submitIncidentReport(report);
    saveSubmissionResult(result);
    router.push("/report/success");
  };

  const nearest = safeLocations[0];

  return (
    <PageShell>
      <ReportProgressSteps currentStep={3} />
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Finding your safe location</h1>
      <p style={{ fontSize: 14, color: "var(--color-text-2)", marginBottom: 24 }}>
        Move somewhere safe while help is on the way, if possible.
      </p>

      {!report?.location && (
        <div
          className="card"
          style={{
            marginBottom: 20,
            background: "rgba(246,173,85,0.08)",
            borderColor: "rgba(246,173,85,0.3)",
            fontSize: 13,
          }}
        >
          We don&apos;t have your location yet — go back and enable location to see nearby safe
          spots, or submit your report without it.
        </div>
      )}

      <div style={{ marginBottom: 24 }}>
        <UserMapPanel
          title="Route to safety"
          userLocation={report?.location ?? null}
          safeLocations={safeLocations}
          height="300px"
        />
      </div>

      {loading ? (
        <div style={{ color: "var(--color-text-2)", fontSize: 13, marginBottom: 24 }}>
          Searching nearby safe locations…
        </div>
      ) : safeLocations.length > 0 ? (
        <div style={{ marginBottom: 28 }}>
          {nearest && (
            <div
              className="card fade-up"
              style={{
                marginBottom: 16,
                background: "var(--color-accent-muted)",
                borderColor: "var(--color-accent)",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--color-accent)", marginBottom: 4 }}>
                SAFEST SUGGESTED LOCATION
              </div>
              <div style={{ fontSize: 18, fontWeight: 800, marginBottom: 4 }}>{nearest.name}</div>
              <div style={{ fontSize: 13, color: "var(--color-text-2)" }}>
                {nearest.distanceKm} km away · ~{nearest.etaMinutes} min
                {nearest.type === "police_station" ? " · Nearest police station" : ""}
              </div>
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {safeLocations.map((loc, idx) => (
              <SafeLocationCard key={loc.name} location={loc} rank={idx + 1} />
            ))}
          </div>
        </div>
      ) : (
        <div style={{ color: "var(--color-text-2)", fontSize: 13, marginBottom: 28 }}>
          No safe locations could be determined for this position.
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={submitting}
        className="btn-primary"
        style={{ width: "100%", fontSize: 15 }}
      >
        {submitting ? "Submitting…" : "Submit Report"}
      </button>
    </PageShell>
  );
}
