import Link from "next/link";

export function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "20px 28px",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 8,
              background: "var(--color-accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 800,
              color: "#0a0a0a",
              fontSize: 15,
            }}
          >
            S
          </div>
          <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: "-0.01em" }}>SentinelAI</span>
        </Link>
        <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--color-text-2)", fontSize: 12 }}>
          <span className="live-dot" />
          Public Incident Reporting
        </div>
      </header>
      <main style={{ flex: 1, width: "100%", maxWidth: 880, margin: "0 auto", padding: "40px 24px" }}>
        {children}
      </main>
      <footer
        style={{
          padding: "20px 28px",
          borderTop: "1px solid var(--color-border)",
          color: "var(--color-text-3)",
          fontSize: 12,
          textAlign: "center",
        }}
      >
        In a life-threatening emergency, always call your local emergency number first.
      </footer>
    </div>
  );
}
