import { PageShell } from "@/components/PageShell";
import { IncidentTypeCard } from "@/components/IncidentTypeCard";
import { ReportProgressSteps } from "@/components/ReportProgressSteps";
import { INCIDENT_TYPES } from "@/types/incident";
import Link from "next/link";
import { Mic } from "lucide-react";

export default function ReportTypeSelectionPage() {
  return (
    <PageShell>
      <ReportProgressSteps currentStep={1} />
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>What&apos;s happening?</h1>
      <p style={{ fontSize: 14, color: "var(--color-text-2)", marginBottom: 24 }}>
        Select the situation that best describes what you&apos;re reporting, or describe it by voice.
      </p>

      <div style={{ marginBottom: 24 }}>
        <Link href="/report/voice" style={{ textDecoration: "none" }}>
          <div className="card fade-up" style={{ 
            display: "flex", alignItems: "center", gap: 16, 
            backgroundColor: "var(--color-accent-dim)",
            border: "1px solid var(--color-accent)",
            cursor: "pointer"
          }}>
            <div style={{
              width: 48, height: 48, borderRadius: 24,
              backgroundColor: "var(--color-accent)",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "white"
            }}>
              <Mic size={24} />
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "var(--color-text-1)" }}>
                Report by Voice
              </div>
              <div style={{ fontSize: 14, color: "var(--color-text-2)", marginTop: 2 }}>
                Just speak naturally and we&apos;ll extract the details
              </div>
            </div>
          </div>
        </Link>
      </div>

      <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text-2)", marginBottom: 16 }}>
        Or select a category manually:
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 16,
        }}
      >
        {INCIDENT_TYPES.map((type) => (
          <IncidentTypeCard key={type.id} type={type} />
        ))}
      </div>
    </PageShell>
  );
}
