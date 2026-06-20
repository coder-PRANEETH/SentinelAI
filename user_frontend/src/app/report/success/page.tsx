"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ReportProgressSteps } from "@/components/ReportProgressSteps";
import { PageShell } from "@/components/PageShell";
import { CheckCircleIcon } from "@/components/icons";
import { loadSubmissionResult } from "@/lib/reportStore";
import type { IncidentSubmissionResult } from "@/types/incident";

export default function ReportSuccessPage() {
  const [result, setResult] = useState<IncidentSubmissionResult | null>(null);

  useEffect(() => {
    setResult(loadSubmissionResult());
  }, []);

  return (
    <PageShell>
      <ReportProgressSteps currentStep={4} />
      <div className="fade-up" style={{ textAlign: "center", padding: "32px 0" }}>
        <div
          style={{
            width: 88,
            height: 88,
            borderRadius: "50%",
            background: "var(--color-accent-muted)",
            color: "var(--color-accent)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 24px",
          }}
        >
          <CheckCircleIcon size={48} />
        </div>

        <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 10 }}>Report Received</h1>
        <p style={{ fontSize: 15, color: "var(--color-text-2)", marginBottom: 28, maxWidth: 420, margin: "0 auto 28px" }}>
          Help is being coordinated. Stay where you are if it&apos;s safe to do so.
        </p>

        <div className="card" style={{ display: "inline-block", padding: "18px 32px", marginBottom: 32 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--color-text-3)", letterSpacing: "0.06em", marginBottom: 6 }}>
            INCIDENT REFERENCE ID
          </div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "var(--color-accent)", fontFamily: "monospace" }}>
            {result?.incidentId ?? "—"}
          </div>
          {result?.isMock && (
            <div style={{ fontSize: 11, color: "var(--color-text-3)", marginTop: 8 }}>
              Demo mode — backend submission endpoint not yet connected.
            </div>
          )}
        </div>

        <div>
          <Link href="/" className="btn-secondary">
            Back to Home
          </Link>
        </div>
      </div>
    </PageShell>
  );
}
