/**
 * lib/api.ts
 * Centralized API client for SentinelAI Flask backend (port 5001).
 * - Attaches Bearer JWT from auth context
 * - Handles 401 → dispatches logout event
 * - Handles 403 → "Insufficient permissions"
 * - Handles 503 → "AI models unavailable" (non-blocking)
 * - Returns typed responses
 */

const FLASK_BASE = process.env.NEXT_PUBLIC_FLASK_API_URL || 'http://localhost:5001';
const FASTAPI_BASE = process.env.NEXT_PUBLIC_FASTAPI_URL || 'http://localhost:8000';

export type ApiError = {
  error: string;
  message: string;
  details: Record<string, unknown>;
  status: number;
};

// Token storage — in-memory only (not localStorage)
let _token: string | null = null;

export function setToken(token: string | null) {
  _token = token;
}

export function getToken(): string | null {
  if (!_token && typeof window !== 'undefined') {
    _token = localStorage.getItem('sentinel_token');
  }
  return _token;
}

// Custom event for session expiry
const AUTH_EXPIRED_EVENT = 'sentinel:auth:expired';

async function request<T>(
  url: string,
  options: RequestInit = {},
  useFastApi = false
): Promise<T> {
  const base = useFastApi ? FASTAPI_BASE : FLASK_BASE;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  const currentToken = getToken();
  if (currentToken) {
    headers['Authorization'] = `Bearer ${currentToken}`;
  }

  const response = await fetch(`${base}${url}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    throw { error: 'UNAUTHORIZED', message: 'Session expired. Please log in.', details: {}, status: 401 } as ApiError;
  }

  if (response.status === 403) {
    throw { error: 'FORBIDDEN', message: 'Insufficient permissions for this action.', details: {}, status: 403 } as ApiError;
  }

  if (response.status === 503) {
    // Non-blocking — surface banner but don't crash
    const body = await response.json().catch(() => ({}));
    throw { error: 'SERVICE_UNAVAILABLE', message: 'AI models unavailable. Some features may be limited.', details: body, status: 503 } as ApiError;
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw {
      error: body.error || 'INTERNAL_ERROR',
      message: body.message || 'An unexpected error occurred.',
      details: body.details || {},
      status: response.status,
    } as ApiError;
  }

  return response.json();
}

// ─────────────────────────────────────────────────────────────────────────────
// Auth
// ─────────────────────────────────────────────────────────────────────────────

export const api = {
  auth: {
    login: (username: string, password: string) =>
      request<{ access_token: string; user: User }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      }),

    logout: () =>
      request<void>('/auth/logout', { method: 'POST' }),

    me: () =>
      request<User>('/auth/me'),
  },

  // ─── Health ────────────────────────────────────────────────────────────────

  health: {
    get: () =>
      request<HealthStatus>('/health'),
  },

  // ─── Incidents ─────────────────────────────────────────────────────────────

  incidents: {
    active: () => request<Incident[]>('/incidents/active'),
    get: (id: string) => request<IncidentDetail>(`/incidents/${id}`),
    list: (params?: { status?: string; limit?: number }) => {
      const qs = params ? '?' + new URLSearchParams(params as Record<string, string>).toString() : '';
      return request<Incident[]>(`/incidents${qs}`);
    },
  },

  // ─── Predict & STT ─────────────────────────────────────────────────────────

  predict: {
    run: (payload: PredictPayload) =>
      request<PredictResponse>('/predict', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    stt: (audioBlob: Blob) => {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');
      return request<{ success: boolean; transcript: string }>('/stt', {
        method: 'POST',
        body: formData,
      }, true); // useFastApi = true
    },
  },

  // ─── Stations ──────────────────────────────────────────────────────────────

  stations: {
    list: (params?: { min_readiness?: number; sort?: string }) => {
      const qs = params ? '?' + new URLSearchParams(params as Record<string, string>).toString() : '';
      return request<Station[]>(`/stations${qs}`);
    },
    get: (stationId: string) =>
      request<Station>(`/stations/${stationId}`),
    update: (stationId: string, body: Record<string, number>) =>
      request<Station>(`/stations/${stationId}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    allocate: (stationId: string, body: AllocateBody) =>
      request<AllocateResponse>(`/stations/${stationId}/allocate`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    release: (stationId: string, body: ReleaseBody) =>
      request<ReleaseResponse>(`/stations/${stationId}/release`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  },

  // ─── Dispatch ──────────────────────────────────────────────────────────────

  dispatch: {
    create: (body: DispatchBody) =>
      request<DispatchResponse>('/dispatch', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  },

  // ─── Historical search ─────────────────────────────────────────────────────

  historical: {
    search: (body: HistoricalSearchBody) =>
      request<HistoricalSearchResponse>('/historical-search', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  },

  // ─── Station readiness ─────────────────────────────────────────────────────

  readiness: {
    ranked: (params?: ReadinessQueryParams) => {
      const qs = params ? '?' + new URLSearchParams(params as Record<string, string>).toString() : '';
      return request<ReadinessResponse>(`/station-readiness${qs}`);
    },
  },

  // ─── Feedback ──────────────────────────────────────────────────────────────

  feedback: {
    submit: (body: FeedbackBody) =>
      request<FeedbackResponse>('/incident-feedback', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    submitExtended: (body: ExtendedFeedbackBody) =>
      request<FeedbackResponse>('/feedback', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  },

  // ─── Analytics ─────────────────────────────────────────────────────────────

  analytics: {
    kpis: () =>
      request<KPIData>('/analytics/kpis'),
    trends: (days = 30) =>
      request<TrendData[]>(`/analytics/trends?days=${days}`),
    histogram: (days = 30) =>
      request<HistogramData[]>(`/analytics/resolution-histogram?days=${days}`),
    modelAccuracy: () =>
      request<ModelAccuracy>('/analytics/model-accuracy'),
    corridors: () =>
      request<CorridorStat[]>('/analytics/corridors'),
  },

  // ─── Risk zones ────────────────────────────────────────────────────────────

  risk: {
    zones: () =>
      request<RiskZone[]>('/risk-zones'),
    runAnalysis: () =>
      request<{ zones_updated: number; high_risk_zones: number; analysis_timestamp: string }>(
        '/admin/run-risk-analysis',
        { method: 'POST' }
      ),
  },

  // ─── Admin ─────────────────────────────────────────────────────────────────

  admin: {
    rebuildIndex: () =>
      request<{ incidents_indexed: number; rebuild_duration_seconds: number }>(
        '/admin/rebuild-index',
        { method: 'POST' }
      ),
    modelStatus: () =>
      request<ModelStatus>('/admin/model-status'),
    updateWeights: (weights: ReadinessWeights) =>
      request<void>('/admin/readiness-weights', {
        method: 'PUT',
        body: JSON.stringify(weights),
      }),
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface User {
  user_id: string;
  username: string;
  email: string;
  role: 'OPERATOR' | 'STATION_OFFICER' | 'SUPERVISOR' | 'ADMIN';
  station_id: string | null;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded';
  timestamp: string;
  components: Record<string, string>;
  version: string;
}

export interface Station {
  station_id: string;
  station_name: string;
  latitude: number | null;
  longitude: number | null;
  readiness_score: number;
  available_officers: number;
  available_vehicles: number;
  available_tow_trucks: number;
  available_barricades: number;
  active_incidents: number;
  total_officers?: number;
  total_vehicles?: number;
  total_tow_trucks?: number;
  total_barricades?: number;
  updated_at?: string;
}

export interface Incident {
  incident_id: string;
  incident_type: string;
  status: string;
  latitude: number | null;
  longitude: number | null;
  predicted_priority?: string;
  corridor?: string;
  location?: string | null;
  event_cause?: string | null;
  vehicle_type?: string | null;
  reported_at?: string;
  created_at?: string;
}

export interface IncidentDetail extends Incident {
  event_cause: string | null;
  vehicle_type: string | null;
  location: string | null;
  priority_indicators: string[] | null;
  reported_by: string | null;
  reported_at: string;
  resolved_at: string | null;
  closed_at: string | null;
  raw_transcript: string | null;
  prediction?: {
    predicted_priority: string;
    priority_confidence: number;
    predicted_resolution_minutes: number;
    road_closure_probability: number;
    road_closure_recommendation: string;
    priority_reasons: string[];
    closure_reasons: string[];
  } | null;
}

export interface PredictPayload {
  incident_type?: string;
  event_type_grouped?: string;
  event_cause?: string;
  corridor: string;
  location: string;
  vehicle_type?: string;
  veh_type_grouped?: string;
  police_station_grouped?: string;
  latitude?: number;
  longitude?: number;
  location_cluster?: number;
  hour_of_day?: number;
  month?: number;
  day_of_week?: string;
  is_peak_hour?: number;
  is_weekend?: number;
  is_cascaded?: number;
  cascade_size?: number;
  raw_transcript?: string;
  incident_id?: string;
}

export interface PredictResponse {
  success: boolean;
  incident: Record<string, unknown>;
  predictions: {
    predicted_priority: string;
    priority_confidence: number;
    priority_reasons: string[];
    predicted_resolution_minutes: number;
    resolution_range: { low: number; high: number };
    road_closure_probability: number;
    road_closure_recommendation: 'Yes' | 'No' | 'Monitor';
    closure_reasons: string[];
  };
  recommended_resources: Resources;
  historical_context: HistoricalContext | null;
  prediction_id: string | null;
}

export interface HistoricalContext {
  similar_cases: SimilarCase[];
  total_similar: number;
  average_resolution_time: number | null;
  historical_priority: string | null;
  most_common_outcome: string | null;
  low_confidence_warning: boolean;
}

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

export interface Resources {
  officers: number;
  vehicles: number;
  tow_trucks: number;
  barricades: number;
}

export interface AllocateBody {
  incident_id: string;
  resources: Resources;
}

export interface AllocateResponse {
  success: boolean;
  dispatch_id: string;
  station: Station;
  resources_allocated: Resources;
  new_readiness_score: number;
}

export interface ReleaseBody {
  incident_id: string;
  dispatch_id: string;
}

export interface ReleaseResponse {
  success: boolean;
  station: Station;
  new_readiness_score: number;
}

export interface DispatchBody {
  incident_id: string;
  station_id: string;
  resources_dispatched: Resources;
  override: boolean;
  override_reason?: string;
  operator_id?: string;
  notes?: string;
}

export interface DispatchResponse {
  success: boolean;
  dispatch_id: string;
  incident_id: string;
  station_id: string;
  incident_status: string;
  resources_dispatched: Resources;
  dispatch_override: boolean;
  station_readiness: number | null;
  dispatched_at: string;
}

export interface HistoricalSearchBody {
  query_text: string;
  top_k?: number;
  min_similarity?: number;
}

export type HistoricalSearchResponse = HistoricalContext;

export interface ReadinessQueryParams {
  officers?: number;
  patrol_vehicles?: number;
  tow_trucks?: number;
  barricades?: number;
  min_readiness?: number;
}

export interface ReadinessResponse {
  stations: StationCandidate[];
  total: number;
  filter_applied: Record<string, number>;
}

export interface StationCandidate extends Station {
  rank: number;
  reasons: string[];
}

export interface FeedbackBody {
  incident_id: string;
  actual_priority: string;
  actual_resolution_time_minutes: number;
  road_closure_occurred: boolean;
  outcome_description?: string;
  operator_id?: string;
}

export interface ExtendedFeedbackBody {
  incident_id: string;
  actual_priority: string;
  actual_closure: boolean;
  actual_resolution_time: number;
  officers_used: number;
  barricades_used: number;
  remarks?: string;
}

export interface FeedbackResponse {
  success: boolean;
  feedback_id: string;
  incident_id: string;
  incident_status: string;
  priority_accurate: boolean | null;
  resolution_error_minutes: number | null;
  model_drift_alert: boolean;
  drift_reason?: string;
}

export interface KPIData {
  active_incidents: number;
  avg_resolution_minutes: number;
  resources_deployed: number;
  high_risk_zones: number;
}

export interface TrendData {
  date: string;
  P1: number;
  P2: number;
  P3: number;
  P4: number;
}

export interface HistogramData {
  bucket: string;
  count: number;
}

export interface ModelAccuracy {
  priority_accuracy: number;
  avg_resolution_error_minutes: number;
  road_closure_accuracy: number;
  feedback_count: number;
}

export interface CorridorStat {
  corridor: string;
  incident_count: number;
  avg_resolution_minutes: number;
  p1_rate: number;
  most_common_type: string;
}

export interface RiskZone {
  zone_id: string;
  corridor: string;
  risk_score: number;
  trend: 'increasing' | 'stable' | 'decreasing';
  incident_count_30d: number;
  p1_p2_fraction: number;
  last_updated: string;
  rate_ratio: number;
}

export interface ModelStatus {
  priority_model: string;
  resolution_model: string;
  closure_model: string;
  faiss_index: string;
  sentence_transformer: string;
}

export interface ReadinessWeights {
  officer: number;
  vehicle: number;
  tow: number;
  barricade: number;
  penalty: number;
}

export { AUTH_EXPIRED_EVENT };
