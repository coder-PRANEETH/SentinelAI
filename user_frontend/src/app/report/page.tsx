import { PageShell } from "@/components/PageShell";
import { IncidentTypeCard } from "@/components/IncidentTypeCard";
import { ReportProgressSteps } from "@/components/ReportProgressSteps";
import { INCIDENT_TYPES } from "@/types/incident";

export default function ReportTypeSelectionPage() {
  return (
    <PageShell>
      <ReportProgressSteps currentStep={1} />
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>What&apos;s happening?</h1>
      <p style={{ fontSize: 14, color: "var(--color-text-2)", marginBottom: 28 }}>
        Select the situation that best describes what you&apos;re reporting.
      </p>
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
