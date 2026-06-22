import { useState } from "react";
import type { GeolocationStatus } from "@/hooks/useGeolocation";
import { LocationPinIcon } from "./icons";

interface Props {
  status: GeolocationStatus;
  error: string | null;
  onRequest: () => void;
  hasManualLocation: boolean;
  manualLocationLabel: string | null;
  onManualLocationSubmit: (address: string) => Promise<void>;
}

export function LocationPermissionBanner({
  status,
  error,
  onRequest,
  hasManualLocation,
  manualLocationLabel,
  onManualLocationSubmit,
}: Props) {
  const [manualAddress, setManualAddress] = useState("");
  const [manualBusy, setManualBusy] = useState(false);
  const [manualError, setManualError] = useState<string | null>(null);

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

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualAddress.trim() || manualBusy) return;
    setManualBusy(true);
    setManualError(null);
    try {
      await onManualLocationSubmit(manualAddress.trim());
    } catch (err) {
      setManualError(err instanceof Error ? err.message : "Couldn't find that location.");
    } finally {
      setManualBusy(false);
    }
  };

  return (
    <div
      className="card"
      style={{
        padding: "14px 18px",
        background: isDenied && !hasManualLocation ? "rgba(229,62,62,0.08)" : "var(--color-surface-raised)",
        borderColor: isDenied && !hasManualLocation ? "rgba(229,62,62,0.3)" : "var(--color-border)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <LocationPinIcon size={18} color={isDenied && !hasManualLocation ? "var(--color-danger)" : "var(--color-text-2)"} />
          <span style={{ fontSize: 13, color: "var(--color-text-1)" }}>
            {hasManualLocation
              ? `Using manually entered location: ${manualLocationLabel}`
              : status === "requesting"
                ? "Requesting your location…"
                : isDenied
                  ? error || "Location access denied. Enter your location manually below."
                  : "Share your location so we can find help near you."}
          </span>
        </div>
        {!isDenied && !hasManualLocation && (
          <button onClick={onRequest} className="btn-secondary" style={{ padding: "8px 18px", fontSize: 13 }}>
            {status === "requesting" ? "Requesting…" : "Enable Location"}
          </button>
        )}
      </div>

      {isDenied && !hasManualLocation && (
        <form onSubmit={handleManualSubmit} style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <input
            className="sel-input"
            style={{ flex: 1, minWidth: 180 }}
            type="text"
            placeholder="Enter your address or nearest landmark"
            value={manualAddress}
            onChange={(e) => setManualAddress(e.target.value)}
            disabled={manualBusy}
          />
          <button
            type="submit"
            className="btn-secondary"
            style={{ padding: "8px 18px", fontSize: 13, flexShrink: 0 }}
            disabled={manualBusy || !manualAddress.trim()}
          >
            {manualBusy ? "Looking up…" : "Use this location"}
          </button>
        </form>
      )}
      {manualError && (
        <div style={{ fontSize: 12, color: "var(--color-danger)", marginTop: 8 }}>{manualError}</div>
      )}
    </div>
  );
}
