import type { GeolocationStatus } from "@/hooks/useGeolocation";
import { LocationPinIcon } from "./icons";

interface Props {
  status: GeolocationStatus;
  error: string | null;
  onRequest: () => void;
}

export function LocationPermissionBanner({ status, error, onRequest }: Props) {
  if (status === "granted") {
    return (
      <div
        className="card"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "12px 16px",
          background: "rgba(72,187,120,0.1)",
          borderColor: "rgba(72,187,120,0.3)",
        }}
      >
        <LocationPinIcon size={18} color="var(--color-success)" />
        <span style={{ fontSize: 13, color: "var(--color-text-1)", fontWeight: 500 }}>
          Location detected — your position is shown on the map below.
        </span>
      </div>
    );
  }

  const isDenied = status === "denied" || status === "unsupported";

  return (
    <div
      className="card"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        padding: "14px 18px",
        background: isDenied ? "rgba(229,62,62,0.08)" : "var(--color-surface-raised)",
        borderColor: isDenied ? "rgba(229,62,62,0.3)" : "var(--color-border)",
        flexWrap: "wrap",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <LocationPinIcon size={18} color={isDenied ? "var(--color-danger)" : "var(--color-text-2)"} />
        <span style={{ fontSize: 13, color: "var(--color-text-1)" }}>
          {status === "requesting"
            ? "Requesting your location…"
            : isDenied
              ? error || "Location access denied. You can still continue manually."
              : "Share your location so we can find help near you."}
        </span>
      </div>
      {!isDenied && (
        <button onClick={onRequest} className="btn-secondary" style={{ padding: "8px 18px", fontSize: 13 }}>
          {status === "requesting" ? "Requesting…" : "Enable Location"}
        </button>
      )}
    </div>
  );
}
