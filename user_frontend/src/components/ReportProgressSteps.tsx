const STEPS = [
  { label: "Incident Type", path: "/report" },
  { label: "Details & Location", path: "/report/car-breakdown" },
  { label: "Safe Location", path: "/report/safe-location" },
  { label: "Confirmation", path: "/report/success" },
];

export function ReportProgressSteps({ currentStep }: { currentStep: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 28, flexWrap: "wrap" }}>
      {STEPS.map((step, idx) => {
        const stepNum = idx + 1;
        const isDone = stepNum < currentStep;
        const isActive = stepNum === currentStep;
        return (
          <div key={step.path} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "6px 12px",
                borderRadius: 9999,
                background: isActive
                  ? "var(--color-accent)"
                  : isDone
                    ? "var(--color-accent-muted)"
                    : "var(--color-surface-raised)",
                color: isActive ? "#0a0a0a" : isDone ? "var(--color-accent)" : "var(--color-text-3)",
                fontSize: 12,
                fontWeight: 700,
                border: isActive || isDone ? "none" : "1px solid var(--color-border)",
              }}
            >
              <span>{stepNum}</span>
              <span style={{ fontSize: 12 }}>{step.label}</span>
            </div>
            {stepNum < STEPS.length && (
              <div style={{ width: 16, height: 1, background: "var(--color-border)" }} />
            )}
          </div>
        );
      })}
    </div>
  );
}
