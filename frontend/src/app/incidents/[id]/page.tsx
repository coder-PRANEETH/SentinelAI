'use client';
import dynamic from 'next/dynamic';
import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import useSWR, { useSWRConfig } from 'swr';
import {
  AlertTriangle, ArrowLeft, Clock, MapPin, Users, Car, Truck,
  Shield, ExternalLink, Loader2, Check, X, Navigation, Zap, ChevronDown, ChevronUp, Activity
} from 'lucide-react';
import { PageHeading } from '@/components/layout/PageHeading';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { LoadingState, ErrorState, EmptyState } from '@/components/shared/LoadingState';
import { ReadinessBar } from '@/components/shared/ReadinessBar';
import { api, IncidentDetail, Incident } from '@/lib/api';
import { listStationReadiness, getStation, allocateResources, historicalSearch, getDispatchRecommendation, simulateRipple, FinalApiError } from '@/api/finalEndpointsApi';

const BengaluruMap = dynamic(
  () => import('@/components/map/BengaluruMap').then(m => m.BengaluruMap),
  { ssr: false, loading: () => <div className="card" style={{ height: 320, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><LoadingState message="Loading map…" /></div> }
);

// ── Priority color helpers ──────────────────────────────────────────────────

const PRIORITY_COLORS: Record<string, { bg: string; text: string }> = {
  P1: { bg: '#FEE2E2', text: '#DC2626' },
  P2: { bg: '#FEF3C7', text: '#D97706' },
  P3: { bg: '#FEF9C3', text: '#A16207' },
  P4: { bg: '#DBEAFE', text: '#1D4ED8' },
};

function PriorityBadge({ priority }: { priority: string }) {
  const c = PRIORITY_COLORS[priority] ?? { bg: '#F3F4F6', text: '#6B7280' };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', padding: '4px 14px',
      borderRadius: '9999px', fontWeight: 700, fontSize: '13px',
      background: c.bg, color: c.text, letterSpacing: '0.04em',
    }}>
      {priority}
    </span>
  );
}

// ── Allocate Resources Modal ────────────────────────────────────────────────

function AllocateModal({
  incidentId,
  onClose,
}: { incidentId: string; onClose: () => void }) {
  const { data: readiness, isLoading } = useSWR('/station-readiness', () => listStationReadiness());
  const candidates = readiness?.slice(0, 5) ?? [];

  const [selected, setSelected] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [err, setErr] = useState('');

  const handleAllocate = async () => {
    if (!selected) return;
    const station = candidates.find(s => s.station === selected);
    if (!station) return;
    setSubmitting(true);
    setErr('');
    try {
      // Fetch full current resources (readiness omits barricades) right before committing.
      const resources = await getStation(station.station);
      await allocateResources(station.station, {
        officers: resources.officers,
        vehicles: resources.vehicles,
        tow_trucks: resources.tow_trucks,
        barricades: resources.barricades,
      });
      setSuccess(true);
      setTimeout(onClose, 1500);
    } catch (e) {
      setErr((e as FinalApiError).message || 'Failed to allocate resources.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="dialog-overlay" role="dialog" aria-modal="true">
      <div className="dialog-content" style={{ maxWidth: 480 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ fontSize: 17, fontWeight: 700 }}>Allocate Resources</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6B7280' }}>
            <X size={18} />
          </button>
        </div>

        {success ? (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <div style={{ width: 52, height: 52, borderRadius: '50%', background: '#D1FAE5', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
              <Check size={24} style={{ color: '#059669' }} />
            </div>
            <div style={{ fontWeight: 700, fontSize: 16 }}>Resources Allocated</div>
          </div>
        ) : (
          <>
            <p style={{ fontSize: 13, color: '#6B6B6B', marginBottom: 16 }}>
              Select a station to allocate available resources to incident <strong>{incidentId}</strong>.
            </p>

            {isLoading ? <LoadingState size="sm" /> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
                {candidates.map(s => (
                  <label
                    key={s.station}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px',
                      border: `2px solid ${selected === s.station ? '#111111' : '#E5E5E5'}`,
                      borderRadius: 12, cursor: 'pointer', transition: 'border-color 0.15s',
                    }}
                  >
                    <input
                      type="radio"
                      name="station"
                      value={s.station}
                      checked={selected === s.station}
                      onChange={() => setSelected(s.station)}
                      style={{ accentColor: '#111111' }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{s.station}</div>
                      <div style={{ fontSize: 11, color: '#6B7280' }}>
                        Readiness: {Math.round(Number(s.readiness_score))} · {s.available_officers} officers · {s.available_vehicles} vehicles
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            )}

            {err && (
              <div style={{ padding: '10px 14px', background: 'rgba(229,62,62,0.08)', borderRadius: 10, fontSize: 12, color: '#E53E3E', marginBottom: 12 }}>
                {err}
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button className="btn-secondary" onClick={onClose} disabled={submitting}>Cancel</button>
              <button
                className="btn-primary"
                onClick={handleAllocate}
                disabled={!selected || submitting}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                {submitting ? <Loader2 size={13} className="animate-spin" /> : null}
                Allocate Resources
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Recommended Station Panel ───────────────────────────────────────────────

function RecommendedStationPanel({ incident, incidentId }: { incident: any, incidentId: string }) {
  const { data: result, isLoading, error } = useSWR(
    incident ? ['/dispatch', incidentId] : null,
    async () => {
      const res = await getDispatchRecommendation({
        incident_id: incidentId,
        incident_text: incident.raw_transcript || incident.incident_type || `Incident ${incidentId}`,
        corridor: incident.corridor || undefined,
        min_officers: 1,
        min_vehicles: 1,
        search_top_k: 8,
      });
      return res; // returns { dispatch, historical_context }
    },
    { revalidateOnFocus: false }
  );

  const [isDispatching, setIsDispatching] = useState(false);
  const [dispatchSuccess, setDispatchSuccess] = useState(false);
  const [dispatchErr, setDispatchErr] = useState('');
  const [showCandidates, setShowCandidates] = useState(false);
  const { mutate } = useSWRConfig();

  const handleDirectDispatch = async () => {
    if (!result?.dispatch?.recommended_station) return;
    setIsDispatching(true);
    setDispatchErr('');
    try {
      const resources = await getStation(result.dispatch.recommended_station);
      await allocateResources(result.dispatch.recommended_station, {
        officers: resources.officers || 2, // fallback defaults
        vehicles: resources.vehicles || 1,
        tow_trucks: resources.tow_trucks || 0,
        barricades: resources.barricades || 0,
      });
      setDispatchSuccess(true);
      // Immediately reflect state updates globally where applicable
      mutate('/station-readiness');
    } catch (e) {
      setDispatchErr((e as FinalApiError).message || 'Failed to dispatch.');
    } finally {
      setIsDispatching(false);
    }
  };

  if (isLoading) {
    return (
      <div className="card" style={{ padding: 24, display: 'flex', justifyContent: 'center' }}>
        <LoadingState message="Generating AI station recommendation…" size="sm" />
      </div>
    );
  }

  if (error || !result) {
    const errMessage = error instanceof Error ? error.message : (error?.message || 'Unknown error');
    return (
      <div className="card" style={{ padding: 16 }}>
        <ErrorState message={`Failed to load recommended station: ${errMessage}`} />
      </div>
    );
  }

  const { dispatch, historical_context } = result;

  return (
    <div className="card" style={{ background: 'var(--lime)', border: 'none' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
        <div>
          <div style={{
            fontSize: '10px', fontWeight: 700, color: 'rgba(17,17,17,0.5)',
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: 4
          }}>
            <Zap size={10} /> AI Recommended Station
          </div>
          <h2 style={{ fontSize: '22px', fontWeight: 800, letterSpacing: '-0.02em' }}>
            {dispatch.recommended_station}
          </h2>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '10px', color: 'rgba(17,17,17,0.5)', marginBottom: '2px' }}>
            Readiness
          </div>
          <div style={{ fontSize: '32px', fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1 }}>
            {Math.round(Number(dispatch.readiness_score))}
          </div>
        </div>
      </div>

      <ReadinessBar score={Number(dispatch.readiness_score)} />

      {dispatch.reasons && dispatch.reasons.length > 0 && (
        <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
          {dispatch.reasons.map((r: string, i: number) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px', color: 'var(--ink)' }}>
              <Check size={13} style={{ color: 'var(--ink)', marginTop: '1px', flexShrink: 0 }} />
              {r}
            </div>
          ))}
        </div>
      )}

      {/* Historical Context */}
      {historical_context && (
        <div style={{ marginTop: '16px', background: 'rgba(255,255,255,0.4)', borderRadius: '10px', padding: '12px' }}>
          <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(17,17,17,0.6)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
            Historical Context
          </div>
          <div style={{ fontSize: '12px', color: 'var(--ink)', lineHeight: 1.6 }}>
            Similar cases: <strong>{historical_context.similar_cases}</strong> &nbsp;·&nbsp;
            Avg resolution: <strong>{historical_context.average_resolution_time ?? '—'} min</strong><br/>
            Priority: <strong>{historical_context.historical_priority ?? 'Unknown'}</strong> &nbsp;·&nbsp;
            Outcome: <strong>{historical_context.most_common_outcome ?? 'Unknown'}</strong>
          </div>
        </div>
      )}

      {/* Candidates toggle */}
      {dispatch.top_candidates && dispatch.top_candidates.length > 1 && (
        <div style={{ marginTop: '12px' }}>
          <button 
            onClick={() => setShowCandidates(!showCandidates)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', fontWeight: 600, color: 'rgba(17,17,17,0.6)', display: 'flex', alignItems: 'center', gap: 4, padding: 0 }}
          >
            {showCandidates ? 'Hide' : 'Show'} alternative candidates {showCandidates ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          
          {showCandidates && (
            <div style={{ marginTop: '8px', background: 'rgba(255,255,255,0.4)', borderRadius: '10px', overflow: 'hidden' }}>
              <table className="data-table" style={{ fontSize: '11px', background: 'transparent' }}>
                <tbody>
                  {dispatch.top_candidates.slice(1, 4).map((s: any) => (
                    <tr key={s.station}>
                      <td style={{ padding: '6px 10px', fontWeight: 600, borderColor: 'rgba(17,17,17,0.05)' }}>{s.station}</td>
                      <td style={{ padding: '6px 10px', borderColor: 'rgba(17,17,17,0.05)' }}>{Math.round(s.readiness_pct)}% ready</td>
                      <td style={{ padding: '6px 10px', borderColor: 'rgba(17,17,17,0.05)' }}>{s.active} active</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Action */}
      <div style={{ marginTop: '16px' }}>
        {dispatchSuccess ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'rgba(255,255,255,0.5)', borderRadius: '10px', fontSize: '13px', fontWeight: 600, color: '#059669' }}>
            <Check size={16} /> Dispatched successfully
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <button
              onClick={handleDirectDispatch}
              disabled={isDispatching}
              style={{
                background: '#111111', color: '#FFFFFF', border: 'none', padding: '12px', borderRadius: '10px',
                fontSize: '13px', fontWeight: 600, cursor: isDispatching ? 'default' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%'
              }}
            >
              {isDispatching ? <Loader2 size={14} className="animate-spin" /> : <Users size={14} />}
              {isDispatching ? 'Dispatching...' : `Dispatch to ${dispatch.recommended_station}`}
            </button>
            {dispatchErr && (
              <div style={{ fontSize: '12px', color: '#DC2626', fontWeight: 500 }}>
                {dispatchErr}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const incidentId = params.id;
  const router = useRouter();
  const [showAllocate, setShowAllocate] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [rippleData, setRippleData] = useState<any[] | null>(null);

  const handleSimulateRipple = async () => {
    if (!incident?.corridor) return;
    setIsSimulating(true);
    try {
      const res = await simulateRipple(incident.corridor, incident.prediction?.road_closure_probability || 0);
      setRippleData(res);
    } catch (e) {
      console.error(e);
      alert('Failed to simulate traffic ripple.');
    } finally {
      setIsSimulating(false);
    }
  };

  const { data: incident, isLoading, error } = useSWR(
    incidentId ? `/incidents/${incidentId}` : null,
    () => api.incidents.get(incidentId),
    { revalidateOnFocus: false }
  );

  // Historical similar incidents
  const { data: historicalData, isLoading: histLoading } = useSWR(
    incident?.corridor ? `/historical/${incidentId}` : null,
    () => historicalSearch(
      `${incident?.incident_type || ''} ${incident?.corridor || ''} ${incident?.event_cause || ''}`,
      5
    ),
    { revalidateOnFocus: false }
  );

  if (isLoading) {
    return (
      <>
        <PageHeading title="Incident Detail" />
        <div className="flex-1 px-7 pb-7 flex items-center justify-center">
          <LoadingState message="Loading incident…" size="lg" />
        </div>
      </>
    );
  }

  if (error || !incident) {
    return (
      <>
        <PageHeading title="Incident Detail" />
        <div className="flex-1 px-7 pb-7 flex items-center justify-center">
          <ErrorState message="Could not load incident. It may not exist." onRetry={() => router.refresh()} />
        </div>
      </>
    );
  }

  const pred = incident.prediction;
  const priority = pred?.predicted_priority ?? incident.predicted_priority ?? 'P4';
  const isActive = !['CLOSED', 'CANCELLED', 'RESOLVED'].includes(incident.status);

  return (
    <>
      <PageHeading title={
        <>
          <button
            onClick={() => router.back()}
            style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', color: '#6B7280', padding: '0 8px 0 0' }}
          >
            <ArrowLeft size={18} />
          </button>
          <span
            style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 36, height: 36, borderRadius: 10, backgroundColor: '#CDFF50', flexShrink: 0,
            }}
          >
            <AlertTriangle size={18} color="#111111" strokeWidth={2.5} />
          </span>
          Incident {incidentId}
        </>
      } />

      <div className="flex-1 px-7 pb-7 overflow-auto">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 20, maxWidth: 1200 }}>

          {/* ── Left column ── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Header card */}
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
                    <PriorityBadge priority={priority} />
                    <StatusBadge status={incident.status.replace(/_/g, ' ') as any} />
                    <span style={{ fontSize: 11, color: '#9CA3AF', fontFamily: 'monospace' }}>{incidentId}</span>
                  </div>
                  <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.02em', marginBottom: 4 }}>
                    {incident.incident_type || 'Unknown Incident Type'}
                  </h1>
                  {incident.corridor && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#6B7280', fontSize: 13 }}>
                      <Navigation size={13} />
                      {incident.corridor}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {isActive && (
                    <button
                      className="btn-accent"
                      onClick={() => setShowAllocate(true)}
                      style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                      <Users size={14} /> Allocate Resources
                    </button>
                  )}
                  <Link
                    href={`/incidents/${incidentId}/dispatch`}
                    className="btn-primary"
                    style={{ display: 'flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}
                  >
                    <ExternalLink size={14} /> Full Dispatch Plan
                  </Link>
                </div>
              </div>

              {/* Detail fields */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                {[
                  { label: 'Event Cause', value: incident.event_cause || '—' },
                  { label: 'Vehicle Type', value: incident.vehicle_type || '—' },
                  { label: 'Location', value: incident.location || '—' },
                  {
                    label: 'Reported At',
                    value: incident.reported_at
                      ? new Date(incident.reported_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
                      : '—'
                  },
                  {
                    label: 'Resolved At',
                    value: incident.resolved_at
                      ? new Date(incident.resolved_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
                      : '—'
                  },
                  { label: 'Status', value: incident.status.replace(/_/g, ' ') },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <div style={{ fontSize: 10, fontWeight: 600, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>
                      {label}
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 500, color: '#111111' }}>{value}</div>
                  </div>
                ))}
              </div>

              {/* Priority indicators */}
              {incident.priority_indicators && incident.priority_indicators.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, fontWeight: 600, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                    Priority Indicators
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {incident.priority_indicators.map((ind, i) => (
                      <span key={i} style={{ padding: '3px 10px', background: '#F3F4F6', borderRadius: 9999, fontSize: 11, fontWeight: 500, color: '#374151' }}>
                        {ind}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Transcript */}
              {incident.raw_transcript && (
                <div>
                  <div style={{ fontSize: 10, fontWeight: 600, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                    Raw Transcript
                  </div>
                  <div style={{ fontSize: 12, color: '#6B7280', lineHeight: 1.7, background: '#F9FAFB', borderRadius: 10, padding: '10px 14px', fontStyle: 'italic' }}>
                    "{incident.raw_transcript}"
                  </div>
                </div>
              )}
            </div>

            {/* ML Predictions */}
            {pred && (
              <div className="card">
                <div style={{ fontSize: 11, fontWeight: 700, color: '#A0A0A0', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 16 }}>
                  ML Model Predictions
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginBottom: 16 }}>
                  {[
                    {
                      label: 'Priority',
                      value: pred.predicted_priority,
                      sub: pred.priority_confidence != null
                        ? `${Math.round(pred.priority_confidence * 100)}% confidence`
                        : '',
                    },
                    {
                      label: 'Est. Resolution',
                      value: `${pred.predicted_resolution_minutes ?? '—'} min`,
                      sub: 'predicted duration',
                    },
                  ].map(({ label, value, sub }) => (
                    <div key={label} style={{ background: '#F9FAFB', borderRadius: 14, padding: '14px 16px' }}>
                      <div style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                        {label}
                      </div>
                      <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: '-0.02em', color: '#111111' }}>{value}</div>
                      {sub && <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>{sub}</div>}
                    </div>
                  ))}

                  {/* Road Closure Probability Gauge */}
                  <div style={{ background: '#F9FAFB', borderRadius: 14, padding: '14px 16px', gridColumn: 'span 2' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <div style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        Road Closure Risk
                      </div>
                      <span style={{ fontSize: 11, fontWeight: 700, color: pred.road_closure_probability && pred.road_closure_probability > 0.5 ? '#DC2626' : '#6B7280' }}>
                        {pred.road_closure_recommendation ?? '—'}
                      </span>
                    </div>
                    
                    {pred.road_closure_probability != null && (
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{ fontSize: 20, fontWeight: 800, letterSpacing: '-0.02em', color: '#111111' }}>
                            {Math.round(pred.road_closure_probability * 100)}%
                          </span>
                        </div>
                        <div style={{ height: 6, background: '#E5E7EB', borderRadius: 9999, overflow: 'hidden' }}>
                          <div style={{ 
                            height: '100%', 
                            background: pred.road_closure_probability > 0.8 ? '#DC2626' : pred.road_closure_probability > 0.4 ? '#D97706' : '#10B981',
                            width: `${Math.round(pred.road_closure_probability * 100)}%`,
                            transition: 'width 0.5s ease-out'
                          }} />
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Priority reasons */}
                {pred.priority_reasons && pred.priority_reasons.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: '#6B7280', marginBottom: 6 }}>Priority Reasons</div>
                    {pred.priority_reasons.map((r, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 12, color: '#374151', marginBottom: 3 }}>
                        <Check size={12} style={{ color: '#059669', marginTop: 2, flexShrink: 0 }} /> {r}
                      </div>
                    ))}
                  </div>
                )}

                {/* Closure reasons */}
                {pred.closure_reasons && pred.closure_reasons.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: '#6B7280', marginBottom: 6 }}>Closure Reasons</div>
                    {pred.closure_reasons.map((r, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 12, color: '#374151', marginBottom: 3 }}>
                        <AlertTriangle size={12} style={{ color: '#D97706', marginTop: 2, flexShrink: 0 }} /> {r}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Recommended Station Panel */}
            {isActive && (
              <RecommendedStationPanel incident={incident} incidentId={incidentId} />
            )}

            {/* Map */}
            {incident.latitude && incident.longitude ? (
              <div className="card" style={{ padding: 0, overflow: 'hidden', height: 340 }}>
                <BengaluruMap
                  incidents={[incident as Incident]}
                  height="100%"
                  showLayerControls={false}
                  rippleNodes={rippleData || []}
                />
              </div>
            ) : (
              <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, color: '#9CA3AF', fontSize: 13, height: 100 }}>
                <MapPin size={16} /> No location data available for this incident
              </div>
            )}
          </div>

          {/* ── Right column — Historical incidents ── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{ padding: '14px 20px', borderBottom: '1px solid #E5E5E5' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#A0A0A0', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Similar Historical Incidents
                </div>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>
                  Based on location, type, and cause
                </div>
              </div>

              {histLoading ? (
                <LoadingState size="sm" message="Searching similar cases…" />
              ) : historicalData && historicalData.similar_cases && historicalData.similar_cases.length > 0 ? (
                <div>
                  {historicalData.similar_cases.map((c, i) => (
                    <div
                      key={i}
                      style={{
                        padding: '12px 20px',
                        borderBottom: '1px solid #E5E5E5',
                        cursor: 'default',
                        transition: 'background 0.12s',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = '#F9FAFB')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{
                          padding: '2px 8px', borderRadius: 9999, fontSize: 10, fontWeight: 700,
                          background: PRIORITY_COLORS[c.priority]?.bg ?? '#F3F4F6',
                          color: PRIORITY_COLORS[c.priority]?.text ?? '#6B7280',
                        }}>
                          {c.priority}
                        </span>
                        <span style={{ fontSize: 10, color: '#9CA3AF' }}>
                          {Math.round(c.similarity_score * 100)}% match
                        </span>
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#111111', marginBottom: 2 }}>
                        {c.event_cause || 'Unknown cause'}
                      </div>
                      <div style={{ fontSize: 11, color: '#6B7280' }}>{c.corridor}</div>
                      {c.resolution_mins != null && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>
                          <Clock size={10} /> Resolved in {c.resolution_mins} min
                        </div>
                      )}
                    </div>
                  ))}

                  {historicalData.average_resolution_time && (
                    <div style={{ padding: '10px 20px', background: '#F9FAFB', borderTop: '1px solid #E5E5E5' }}>
                      <div style={{ fontSize: 11, color: '#6B7280' }}>
                        Avg resolution for similar cases:{' '}
                        <strong style={{ color: '#111111' }}>
                          {Math.round(historicalData.average_resolution_time)} min
                        </strong>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <EmptyState message="No similar historical incidents found." />
              )}
            </div>

            {/* Quick actions */}
            <div className="card">
              <div style={{ fontSize: 11, fontWeight: 700, color: '#A0A0A0', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
                Quick Actions
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>

                <Link
                  href={`/feedback?incident_id=${incidentId}`}
                  style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: '#F9FAFB', borderRadius: 10, fontSize: 13, fontWeight: 500, color: '#111111', border: '1px solid #E5E5E5' }}
                >
                  <Check size={14} style={{ color: '#6B7280' }} /> Submit Feedback
                </Link>

                {incident.corridor && incident.prediction?.road_closure_probability && incident.prediction.road_closure_probability > 0.4 ? (
                  <button
                    onClick={handleSimulateRipple}
                    disabled={isSimulating}
                    style={{ cursor: isSimulating ? 'default' : 'pointer', display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: '#FEF3C7', borderRadius: 10, fontSize: 13, fontWeight: 500, color: '#92400E', border: '1px solid #FDE68A' }}
                  >
                    {isSimulating ? <Loader2 size={14} className="animate-spin" /> : <Activity size={14} style={{ color: '#D97706' }} />} Simulate Traffic Ripple
                  </button>
                ) : null}

                {rippleData && (
                  <div style={{ marginTop: 8, padding: 12, background: '#F9FAFB', borderRadius: 10, border: '1px solid #E5E5E5' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#111111', marginBottom: 6 }}>Ripple Simulation Complete</div>
                    <div style={{ fontSize: 12, color: '#6B7280' }}>
                      <strong style={{ color: '#DC2626' }}>{rippleData.length}</strong> intersections affected<br/>
                      Max delay: {Math.max(0, ...rippleData.map(r => r.time_taken_minutes))} min
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Allocate resources modal */}
      {showAllocate && (
        <AllocateModal incidentId={incidentId} onClose={() => setShowAllocate(false)} />
      )}
    </>
  );
}
