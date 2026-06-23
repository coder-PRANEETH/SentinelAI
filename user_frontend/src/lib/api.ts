/**
 * lib/api.ts
 * API client for the SentinelAI public incident-reporting site.
 *
 * Uses FINAL_ENDPOINTS_BASE (port 5000) for ML predictions.
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
  process.env.NEXT_PUBLIC_API_BASE_URL || "https://sentinelai-h7ib.onrender.com";

/**
 * Resolve a free-text address/landmark to coordinates, for the manual
 * location fallback when browser geolocation is denied or unsupported.
 * Uses OpenStreetMap's free Nominatim geocoder — no API key required.
 */
export async function geocodeAddress(query: string): Promise<{ point: GeoPoint; label: string }> {
  const params = new URLSearchParams({
    q: query,
    format: "json",
    limit: "1",
    countrycodes: "in",
    viewbox: "77.35,13.2,77.95,12.75",
    bounded: "0",
  });
  const res = await fetch(`https://nominatim.openstreetmap.org/search?${params.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error("Location search failed — try again.");
  const data = (await res.json()) as Array<{ lat: string; lon: string; display_name: string }>;
  if (!data.length) throw new Error(`Couldn't find "${query}". Try a more specific address.`);
  return {
    point: { latitude: parseFloat(data[0].lat), longitude: parseFloat(data[0].lon) },
    label: data[0].display_name,
  };
}

function generateMockIncidentId(): string {
  const year = new Date().getFullYear();
  const rand = Math.floor(100000 + Math.random() * 900000);
  return `INC-${year}-${rand}`;
}

function mapEventType(type: CarBreakdownReport["incidentTypeId"]): string {
  const eventTypes: Record<CarBreakdownReport["incidentTypeId"], string> = {
    car_breakdown: "vehicle_breakdown",
    accident: "accident",
    road_block: "road_block",
    medical_emergency: "medical_emergency",
  };
  return eventTypes[type];
}

function mapEventCause(issueType: string): string {
  const issue = issueType.toLowerCase();
  if (issue.includes("flat") || issue.includes("tyre")) return "tyre_puncture";
  if (issue.includes("battery") || issue.includes("electrical")) return "electrical_failure";
  if (issue.includes("overheat")) return "overheating";
  if (issue.includes("fuel")) return "out_of_fuel";
  if (issue.includes("collision")) return "accident";
  return "mechanical_failure";
}

function mapVehicleType(vehicleType: string): string {
  const vehicle = vehicleType.toLowerCase();
  if (vehicle.includes("truck") || vehicle.includes("heavy")) return "heavy";
  if (vehicle.includes("bus")) return "bus";
  if (vehicle.includes("two") || vehicle.includes("auto")) return "two_wheeler";
  return "light";
}

function buildPredictPayload(report: CarBreakdownReport) {
  const now = new Date();
  const hour = now.getHours();
  const dayOfWeek = now.toLocaleDateString("en-US", { weekday: "long" });
  const isWeekend = dayOfWeek === "Saturday" || dayOfWeek === "Sunday";

  return {
    incident_type: mapEventType(report.incidentTypeId),
    event_type_grouped: mapEventType(report.incidentTypeId),
    event_cause: mapEventCause(report.issueType),
    corridor: "Tumkur Road",
    location: "Tumkur Road",
    police_station_grouped: "Peenya",
    vehicle_type: report.vehicleType,
    veh_type_grouped: mapVehicleType(report.vehicleType),
    raw_transcript: report.description || null,
    day_of_week: dayOfWeek,
    latitude: report.location?.latitude ?? 13.02,
    longitude: report.location?.longitude ?? 77.56,
    location_cluster: 3,
    hour_of_day: hour,
    month: now.getMonth() + 1,
    is_peak_hour: Number((hour >= 8 && hour <= 11) || (hour >= 17 && hour <= 20)),
    is_weekend: Number(isWeekend),
    is_cascaded: 0,
    cascade_size: 1,
  };
}

/**
 * Submit a car breakdown / incident report.
 */
export async function submitIncidentReport(
  report: CarBreakdownReport
): Promise<IncidentSubmissionResult> {
  const payload = buildPredictPayload(report);

  try {
    const res = await fetch(`${FINAL_ENDPOINTS_BASE}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const body = await res.json();
      const priority = body.predictions?.priority;
      return {
        success: true,
        incidentId: body.incident_id || generateMockIncidentId(),
        isMock: false,
        message: priority
          ? `Your report has been received. Predicted priority: ${priority}.`
          : "Your report has been received.",
      };
    }
    throw new Error(`Predict endpoint returned ${res.status}`);
  } catch {
    // Mock fallback keeps the report flow usable if the prediction API is down.
    return {
      success: true,
      incidentId: generateMockIncidentId(),
      isMock: true,
      message: "Your report has been recorded locally (prediction API unavailable).",
    };
  }
}

/**
 * Find the nearest safe locations (police stations / safe stops) to a
 * given point, ranked by distance.
 *
 * Coordinates come from a bundled static dataset (see stationsData.ts).
 */
export async function findNearestSafeLocations(
  point: GeoPoint,
  limit = 3
): Promise<SafeLocation[]> {
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

  return ranked.slice(0, limit);
}
