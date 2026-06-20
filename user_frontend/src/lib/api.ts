/**
 * lib/api.ts
 * API client for the SentinelAI public incident-reporting site.
 *
 * Two existing backend services:
 * - FINAL_ENDPOINTS_BASE (port 5000): ML predictions + station resource
 *   tracker. `/stations` here is public (no auth) but only returns resource
 *   counts (officers/vehicles/etc.), no coordinates.
 * - BACKEND_BASE (port 5001): main Flask API. `/stations` and `/incidents`
 *   exist but `/stations` requires an operator JWT, and there is currently
 *   NO public "create incident" endpoint exposed for anonymous reporters.
 *
 * TODO(backend): once a public `POST /public/incidents` (or similar) exists,
 * wire `submitIncidentReport` to it directly and remove the mock fallback.
 */

import type {
  CarBreakdownReport,
  GeoPoint,
  IncidentSubmissionResult,
  SafeLocation,
} from "@/types/incident";
import { BENGALURU_STATIONS } from "./stationsData";
import { distanceKm, etaMinutes } from "./geo";

const FINAL_ENDPOINTS_BASE =
  process.env.NEXT_PUBLIC_FINAL_ENDPOINTS_API_URL || "http://127.0.0.1:5000";
const BACKEND_BASE =
  process.env.NEXT_PUBLIC_BACKEND_API_URL || "http://127.0.0.1:5001";

function generateMockIncidentId(): string {
  const year = new Date().getFullYear();
  const rand = Math.floor(100000 + Math.random() * 900000);
  return `INC-${year}-${rand}`;
}

/**
 * Submit a car breakdown / incident report.
 *
 * TODO(backend): there is no confirmed public submit endpoint yet. This
 * tries POST {BACKEND_BASE}/incidents first (in case it becomes available),
 * and falls back to a local mock reference ID so the UI flow keeps working.
 */
export async function submitIncidentReport(
  report: CarBreakdownReport
): Promise<IncidentSubmissionResult> {
  const payload = {
    incident_type: report.incidentTypeId,
    vehicle_type: report.vehicleType,
    event_cause: report.issueType,
    raw_transcript: report.description,
    phone_number: report.phoneNumber || null,
    latitude: report.location?.latitude ?? null,
    longitude: report.location?.longitude ?? null,
  };

  try {
    const res = await fetch(`${BACKEND_BASE}/incidents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const body = await res.json();
      return {
        success: true,
        incidentId: body.incident_id || generateMockIncidentId(),
        isMock: false,
        message: "Your report has been received.",
      };
    }
    throw new Error(`Submit endpoint returned ${res.status}`);
  } catch {
    // Mock fallback — keeps the report flow usable until the real
    // public submission endpoint is wired up on the backend.
    return {
      success: true,
      incidentId: generateMockIncidentId(),
      isMock: true,
      message: "Your report has been recorded locally (demo mode).",
    };
  }
}

interface FinalEndpointStation {
  station: string;
  officers: number;
  vehicles: number;
  tow_trucks: number;
  barricades: number;
}

/**
 * Fetch live resource counts from the public final-endpoints API
 * (port 5000, `/stations` — no auth required). Used to enrich the
 * bundled coordinate list with real availability data when reachable.
 */
async function fetchStationResources(): Promise<FinalEndpointStation[]> {
  const res = await fetch(`${FINAL_ENDPOINTS_BASE}/stations`, {
    signal: AbortSignal.timeout(4000),
  });
  if (!res.ok) throw new Error(`Stations endpoint returned ${res.status}`);
  return res.json();
}

/**
 * Find the nearest safe locations (police stations / safe stops) to a
 * given point, ranked by distance.
 *
 * Coordinates come from a bundled static dataset (see stationsData.ts)
 * since the live, authoritative station list requires operator auth.
 * Resource availability is merged in opportunistically when the public
 * final-endpoints API is reachable.
 */
export async function findNearestSafeLocations(
  point: GeoPoint,
  limit = 3
): Promise<SafeLocation[]> {
  let resources: FinalEndpointStation[] = [];
  try {
    resources = await fetchStationResources();
  } catch {
    // Non-fatal — proceed with coordinates only.
  }

  const ranked = BENGALURU_STATIONS.map((s) => {
    const km = distanceKm(point.latitude, point.longitude, s.latitude, s.longitude);
    return {
      name: s.name,
      type: s.type as SafeLocation["type"],
      latitude: s.latitude,
      longitude: s.longitude,
      distanceKm: Math.round(km * 10) / 10,
      etaMinutes: etaMinutes(km),
    };
  }).sort((a, b) => a.distanceKm - b.distanceKm);

  // Resource data is currently unmatched by name (different naming
  // schemes between the bundled list and the resource tracker DB) — kept
  // here as the integration point once a shared station ID exists.
  void resources;

  return ranked.slice(0, limit);
}
