import { PublicMap } from "@/components/map/PublicMap";
import type { GeoPoint, SafeLocation } from "@/types/incident";

interface UserMapPanelProps {
  title: string;
  userLocation: GeoPoint | null;
  safeLocations?: SafeLocation[];
  height?: string;
}

/**
 * Card wrapper around PublicMap — adds a title/legend header so the map
 * reads consistently across the report flow (current location, then
 * current location + ranked safe-location pins).
 */
export function UserMapPanel({ title, userLocation, safeLocations = [], height = "360px" }: UserMapPanelProps) {
  return (
    <div className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text-1)" }}>{title}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 11, color: "var(--color-text-3)" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#4299E1" }} />
            You
          </span>
          {safeLocations.length > 0 && (
            <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#CDFF50" }} />
              Safe spot
            </span>
          )}
        </div>
      </div>
      <PublicMap userLocation={userLocation} safeLocations={safeLocations} height={height} />
    </div>
  );
}
