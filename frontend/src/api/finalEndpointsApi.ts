/**
 * finalEndpointsApi.ts
 * Client for the standalone SentinelAI Flask API in final_endpoints/models.py.
 * Separate from lib/api.ts (which talks to the auth/DB-backed backend on port 5001) —
 * this one is unauthenticated, has no incident/station IDs, and stations are keyed by name.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_FINAL_ENDPOINTS_API_URL || 'http://127.0.0.1:5000';

// Fixed per-station resource caps from final_endpoints/models.py DEFAULT_RESOURCES.
// The API never returns these totals, only current availability, so they're mirrored here.
export const STATION_RESOURCE_CAPS = {
  officers: 15,
  vehicles: 4,
  tow_trucks: 2,
  barricades: 20,
};

export type FinalApiError = {
  message: string;
  status: number;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string> || {}),
      },
    });
  } catch {
    throw { message: 'Could not reach the final_endpoints server. Is it running?', status: 0 } as FinalApiError;
  }

  let body: any = {};
  try {
    const text = await response.text();
    // Python's jsonify sometimes outputs NaN, which is invalid JSON.
    const safeText = text.replace(/:\s*NaN/g, ': null');
    body = JSON.parse(safeText);
  } catch {
    body = {};
  }

  if (!response.ok) {
    throw { message: body.error || 'Request failed.', status: response.status } as FinalApiError;
  }

  return body as T;
}

// ─── Health ────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  service: string;
}

export const getHealth = () => request<HealthResponse>('/health');

// ─── Predict ───────────────────────────────────────────────────────────────

export interface PredictPayload {
  event_type_grouped?: string;
  event_cause?: string;
  corridor?: string;
  police_station_grouped?: string;
  veh_type_grouped?: string;
  day_of_week?: string;
  latitude?: number;
  longitude?: number;
  location_cluster?: number;
  hour_of_day?: number;
  month?: number;
  is_peak_hour?: number;
  is_weekend?: number;
  is_cascaded?: number;
  cascade_size?: number;
}

export interface PredictResponse {
  incident: {
    event_type: string;
    event_cause: string;
    corridor: string;
  };
  predictions: {
    priority: 'high' | 'low';
    priority_confidence: number;
    road_closure_required: boolean;
    road_closure_probability: number;
    expected_resolution_minutes: number;
  };
}

export const predict = (payload: PredictPayload) =>
  request<PredictResponse>('/predict', { method: 'POST', body: JSON.stringify(payload) });

// ─── Stations ──────────────────────────────────────────────────────────────

export interface StationResources {
  station: string;
  officers: number;
  vehicles: number;
  tow_trucks: number;
  barricades: number;
}

export const listStations = () => request<StationResources[]>('/stations');

export const getStation = (station: string) =>
  request<StationResources>(`/stations/${encodeURIComponent(station)}`);

export interface AllocateReleaseBody {
  officers?: number;
  vehicles?: number;
  tow_trucks?: number;
  barricades?: number;
}

export interface AllocateResponse {
  station: string;
  action: 'allocated';
  dispatched: Required<AllocateReleaseBody>;
  remaining: StationResources;
}

export const allocateResources = (station: string, body: AllocateReleaseBody) =>
  request<AllocateResponse>(`/stations/${encodeURIComponent(station)}/allocate`, {
    method: 'POST',
    body: JSON.stringify(body),
  });

export interface ReleaseResponse {
  station: string;
  action: 'released';
  returned: Required<AllocateReleaseBody>;
  current: StationResources;
}

export const releaseResources = (station: string, body: AllocateReleaseBody) =>
  request<ReleaseResponse>(`/stations/${encodeURIComponent(station)}/release`, {
    method: 'POST',
    body: JSON.stringify(body),
  });

// ─── Station readiness ─────────────────────────────────────────────────────

export interface StationReadiness {
  station: string;
  readiness_score: number;
  resource_ratio_pct: number;
  available_officers: number;
  available_vehicles: number;
  available_tow_trucks: number;
  active_incidents: number;
  high_priority_incidents: number;
  avg_resolution_mins: number;
  error?: string;
}

export const getStationReadiness = (station?: string) => {
  const qs = station ? `?station=${encodeURIComponent(station)}` : '';
  return request<StationReadiness | StationReadiness[]>(`/station-readiness${qs}`);
};

export const listStationReadiness = () =>
  getStationReadiness() as Promise<StationReadiness[]>;

// ─── Historical search ─────────────────────────────────────────────────────

export interface SimilarCase {
  event_cause: string;
  corridor: string;
  junction: string;
  priority: string;
  veh_type: string;
  police_station: string;
  status: string;
  resolution_mins: number | null;
  similarity_score: number;
}

export interface HistoricalSearchResponse {
  similar_cases: SimilarCase[];
  total_similar: number;
  average_resolution_time: number | null;
  historical_priority: string | null;
  most_common_outcome: string | null;
}

export const historicalSearch = (query: string, top_k = 20) =>
  request<HistoricalSearchResponse>('/historical-search', {
    method: 'POST',
    body: JSON.stringify({ query, top_k }),
  });

// ─── Dispatch ──────────────────────────────────────────────────────────────

export interface DispatchPayload {
  incident_id?: string;
  incident_text: string;
  corridor?: string;
  min_officers?: number;
  min_vehicles?: number;
  search_top_k?: number;
}

export interface DispatchCandidate {
  station: string;
  readiness_pct: number;
  active: number;
  officers: number;
  vehicles: number;
}

export interface DispatchResponse {
  dispatch: {
    incident: string;
    incident_id?: string;
    incident_status_updated?: boolean;
    recommended_station: string;
    readiness_score: number;
    reasons: string[];
    top_candidates: DispatchCandidate[];
  };
  historical_context: {
    similar_cases: number;
    average_resolution_time: number | null;
    historical_priority: string | null;
    most_common_outcome: string | null;
  };
}

export const getDispatchRecommendation = (payload: DispatchPayload) =>
  request<DispatchResponse>('/dispatch', { method: 'POST', body: JSON.stringify(payload) });
