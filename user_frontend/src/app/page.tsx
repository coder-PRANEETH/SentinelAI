import Link from "next/link";
import { PageShell } from "@/components/PageShell";
import { IncidentTypeCard } from "@/components/IncidentTypeCard";
import { INCIDENT_TYPES } from "@/types/incident";

export default function LandingPage() {
  return (
    <PageShell>
      <section style={{ textAlign: "center", padding: "20px 0 48px" }} className="fade-up">
        <div
          className="pill"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            background: "var(--color-accent-muted)",
            color: "var(--color-accent)",
            marginBottom: 20,
          }}
        >
          <span className="live-dot" />
          AI-Coordinated Response
        </div>
        <h1
          style={{
            fontSize: "clamp(32px, 6vw, 56px)",
            fontWeight: 800,
            lineHeight: 1.1,
            letterSpacing: "-0.02em",
            marginBottom: 16,
          }}
        >
          Report Road Incidents
          <br />
          <span style={{ color: "var(--color-accent)" }}>Instantly</span>
        </h1>
        <p
          style={{
            fontSize: 16,
            color: "var(--color-text-2)",
            maxWidth: 520,
            margin: "0 auto 32px",
            lineHeight: 1.6,
          }}
        >
          Tell us what happened in seconds. SentinelAI shares your location with the
          nearest responders and finds you a safe place to wait.
        </p>
        <Link href="/report" className="btn-primary" style={{ fontSize: 15 }}>
          Report Now →
        </Link>
      </section>

      <section>
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
      </section>
    </PageShell>
  );
}
