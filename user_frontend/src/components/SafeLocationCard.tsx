import type { SafeLocation } from "@/types/incident";
import { ShieldCheckIcon } from "./icons";

export function SafeLocationCard({ location, rank }: { location: SafeLocation; rank: number }) {
  const isPoliceStation = location.type === "police_station";

  return (
    <div
      className="card"
      style={{ display: "flex", alignItems: "flex-start", gap: 14, padding: "16px 18px" }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          background: isPoliceStation ? "var(--color-accent-muted)" : "rgba(246,173,85,0.15)",
          color: isPoliceStation ? "var(--color-accent)" : "var(--color-warning)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 700,
          fontSize: 13,
          flexShrink: 0,
        }}
      >
        {rank}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 15, fontWeight: 700 }}>{location.name}</span>
          {isPoliceStation && <ShieldCheckIcon size={15} color="var(--color-accent)" />}
        </div>
        <div style={{ fontSize: 12, color: "var(--color-text-2)", textTransform: "capitalize" }}>
          {location.type.replace("_", " ")}
        </div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-accent)" }}>
          {location.distanceKm} km
        </div>
        <div style={{ fontSize: 11, color: "var(--color-text-3)" }}>~{location.etaMinutes} min</div>
      </div>
    </div>
  );
}
