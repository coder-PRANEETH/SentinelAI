'use client';
import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import useSWR from 'swr';
import { PageHeading } from '@/components/layout/PageHeading';
import { ReadinessBar } from '@/components/shared/ReadinessBar';
import { LoadingState, ErrorState } from '@/components/shared/LoadingState';
import {
  getDispatchRecommendation, getStation, allocateResources,
  FinalApiError,
} from '@/api/finalEndpointsApi';
import { Check, AlertTriangle, Loader2, Users, Car, Truck, Shield } from 'lucide-react';

interface RecommendationInputs {
  incidentText: string;
  corridor: string;
}

/**
 * Dispatch Recommendation Screen.
 * Recommendation comes from POST /dispatch (final_endpoints). Confirm/Override
 * commits the resource deduction via POST /stations/<station>/allocate, since
 * final_endpoints keeps "recommend" and "commit" as separate steps.
 */
export default function DispatchPage() {
  const params = useParams<{ id: string }>();
  const incidentId = params.id;
  const router = useRouter();

  // Fields the user edits freely.
  const [incidentText, setIncidentText] = useState(`Incident ${incidentId}`);
  const [corridor, setCorridor] = useState('');

  // Snapshot only updated when "Get Recommendation" is clicked (or on first load).
  const [submitted, setSubmitted] = useState<RecommendationInputs>({
    incidentText: `Incident ${incidentId}`, corridor: '',
  });

  const { data: result, isLoading, error, mutate } = useSWR(
    ['/dispatch', submitted],
    async ([, inputs]: [string, RecommendationInputs]) => {
      const payload = {
        incident_id: incidentId,
        incident_text: inputs.incidentText || `Incident ${incidentId}`,
        corridor: inputs.corridor || undefined,
        search_top_k: 20,
      };
      console.log("PAYLOAD", payload);
      console.log("BEFORE FETCH");
      try {
        const res = await getDispatchRecommendation(payload);
        console.log("AFTER FETCH");
        console.log("RESPONSE", res);
        const resources = await getStation(res.dispatch.recommended_station);
        return { dispatch: res, recommendedResources: resources };
      } catch (err) {
        console.error("REQUEST FAILED", err);
        throw err;
      }
    }
  );
  const loadError = error ? ((error as FinalApiError).message || 'Failed to load dispatch recommendation.') : '';

  const recommendedResources = result?.recommendedResources ?? null;
  const candidates = result?.dispatch.dispatch.top_candidates.slice(0, 5) ?? [];
  const recommendedStation = result?.dispatch.dispatch.recommended_station;

  const handleGetRecommendation = () => {
    console.log("BUTTON CLICKED");
    setSubmitted({ incidentText, corridor });
  };

  const [showConfirm, setShowConfirm] = useState(false);
  const [showOverrideDrawer, setShowOverrideDrawer] = useState(false);
  const [overrideStation, setOverrideStation] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [isDispatching, setIsDispatching] = useState(false);
  const [dispatchError, setDispatchError] = useState('');
  const [dispatchSuccess, setDispatchSuccess] = useState(false);

  const handleConfirmDispatch = async () => {
    if (!recommendedStation || !recommendedResources) return;
    setIsDispatching(true);
    setDispatchError('');
    const pkg = result.dispatch.recommended_resources;
    if (!pkg) return;
    try {
      await allocateResources(recommendedStation, {
        officers: pkg.officers,
        vehicles: pkg.vehicles,
        tow_trucks: pkg.tow_trucks,
        barricades: pkg.barricades,
      });
      setDispatchSuccess(true);
      setTimeout(() => router.push('/dashboard'), 2000);
    } catch (err) {
      setDispatchError((err as FinalApiError).message || 'Dispatch failed.');
    } finally {
      setIsDispatching(false);
      setShowConfirm(false);
    }
  };

  const handleOverrideDispatch = async () => {
    if (overrideReason.length < 20 || !overrideStation) return;
    setIsDispatching(true);
    setDispatchError('');
    try {
      await allocateResources(overrideStation, { officers: 2, vehicles: 1, tow_trucks: 0, barricades: 2 });
      setDispatchSuccess(true);
      setTimeout(() => router.push('/dashboard'), 2000);
    } catch (err) {
      setDispatchError((err as FinalApiError).message || 'Override dispatch failed.');
    } finally {
      setIsDispatching(false);
      setShowOverrideDrawer(false);
    }
  };

  if (isLoading) return <PageShell incidentId={incidentId}><LoadingState message="Loading dispatch recommendation…" /></PageShell>;
  if (loadError) return <PageShell incidentId={incidentId}><ErrorState message={loadError} onRetry={() => mutate()} /></PageShell>;

  if (dispatchSuccess) return (
    <PageShell incidentId={incidentId}>
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', gap: '16px', padding: '64px',
      }}>
        <div style={{
          width: 64, height: 64, borderRadius: '50%',
          background: 'var(--lime)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Check size={28} style={{ color: 'var(--ink)' }} />
        </div>
        <h2 style={{ fontSize: '20px', fontWeight: 700 }}>Dispatch Confirmed</h2>
        <p style={{ color: 'var(--muted)', fontSize: '13px' }}>Redirecting to dashboard…</p>
      </div>
    </PageShell>
  );

  return (
    <>
      <PageHeading title={`Dispatch — ${incidentId}`} />
      <div className="flex-1 px-7 pb-7 overflow-auto">
          <div style={{ maxWidth: '820px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

            {/* Recommendation inputs */}
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Recommendation Inputs
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div className="form-group">
                  <label className="form-label">Incident Text</label>
                  <input className="form-input" value={incidentText} onChange={e => setIncidentText(e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Corridor</label>
                  <input className="form-input" value={corridor} onChange={e => setCorridor(e.target.value)} placeholder="e.g. Tumkur Road" />
                </div>
              </div>
              <button className="btn-secondary" style={{ alignSelf: 'flex-start' }} onClick={handleGetRecommendation}>
                Get Recommendation
              </button>
            </div>

            {/* Recommended station */}
            {result && (
              <div className="card" style={{ background: 'var(--lime)', border: 'none' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                  <div>
                    <div style={{
                      fontSize: '10px', fontWeight: 700, color: 'rgba(17,17,17,0.5)',
                      textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px',
                    }}>
                      AI Recommended Station
                    </div>
                    <h2 style={{ fontSize: '22px', fontWeight: 800, letterSpacing: '-0.02em' }}>
                      {result.dispatch.dispatch.recommended_station}
                    </h2>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '10px', color: 'rgba(17,17,17,0.5)', marginBottom: '2px' }}>
                      Readiness
                    </div>
                    <div style={{ fontSize: '32px', fontWeight: 800, letterSpacing: '-0.03em' }}>
                      {Math.round(Number(result.dispatch.dispatch.readiness_score))}
                    </div>
                  </div>
                </div>

                <ReadinessBar score={Number(result.dispatch.dispatch.readiness_score)} />

                <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  {result.dispatch.dispatch.reasons?.map((r, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px' }}>
                      <Check size={13} style={{ color: 'var(--ink)', marginTop: '1px', flexShrink: 0 }} />
                      {r}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Resource package */}
            {result?.dispatch.recommended_resources && (
              <div className="card">
                <div style={{
                  fontSize: '11px', fontWeight: 700, color: 'var(--muted)',
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '16px',
                  display: 'flex', justifyContent: 'space-between'
                }}>
                  <span>Resource Package</span>
                  <span style={{ textTransform: 'none', fontWeight: 400, color: 'var(--accent)' }}>
                    {result.dispatch.recommended_resources.justification}
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                  {[
                    { icon: <Users size={18} />, count: result.dispatch.recommended_resources.officers, label: 'Officers' },
                    { icon: <Car size={18} />,   count: result.dispatch.recommended_resources.vehicles,  label: 'Vehicles' },
                    { icon: <Truck size={18} />, count: result.dispatch.recommended_resources.tow_trucks, label: 'Tow Trucks' },
                    { icon: <Shield size={18} />,count: result.dispatch.recommended_resources.barricades, label: 'Barricades' },
                  ].map(({ icon, count, label }) => (
                    <div key={label} style={{
                      background: 'var(--bg)', borderRadius: '14px', padding: '14px',
                      display: 'flex', flexDirection: 'column', gap: '8px',
                    }}>
                      <span style={{ color: 'var(--muted)' }}>{icon}</span>
                      <div style={{ fontSize: '26px', fontWeight: 800, letterSpacing: '-0.02em' }}>{count}</div>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 500 }}>{label}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Historical context */}
            {result?.dispatch.historical_context && (
              <div className="card" style={{ padding: '12px 16px' }}>
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                  Historical Context
                </div>
                <div style={{ fontSize: '12px', color: 'var(--ink)', lineHeight: 1.7 }}>
                  Similar cases: <strong>{result.dispatch.historical_context.similar_cases}</strong> &nbsp;·&nbsp;
                  Avg resolution: <strong>{result.dispatch.historical_context.average_resolution_time ?? '—'} min</strong> &nbsp;·&nbsp;
                  Common priority: <strong>{result.dispatch.historical_context.historical_priority ?? 'Unknown'}</strong> &nbsp;·&nbsp;
                  Common outcome: <strong>{result.dispatch.historical_context.most_common_outcome ?? 'Unknown'}</strong>
                </div>
              </div>
            )}

            {/* Candidate comparison */}
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{
                padding: '14px 20px', borderBottom: '1px solid var(--border)',
                fontSize: '12px', fontWeight: 700, color: 'var(--muted)',
                textTransform: 'uppercase', letterSpacing: '0.06em',
              }}>
                Candidate Comparison
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Station</th>
                    <th>Readiness</th>
                    <th>Officers</th>
                    <th>Vehicles</th>
                    <th>Active Inc.</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((s, i) => (
                    <tr key={s.station}>
                      <td>
                        {i === 0 && (
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                            width: 18, height: 18, borderRadius: '5px',
                            background: 'var(--lime)', fontSize: '10px', fontWeight: 700,
                            marginRight: '8px',
                          }}>★</span>
                        )}
                        <span style={{ fontWeight: i === 0 ? 600 : 400 }}>{s.station}</span>
                      </td>
                      <td style={{ minWidth: '140px' }}>
                        <ReadinessBar score={Number(s.readiness_pct)} />
                      </td>
                      <td>{s.officers}</td>
                      <td>{s.vehicles}</td>
                      <td>{s.active}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Error */}
            {dispatchError && (
              <div style={{
                padding: '12px 16px',
                background: 'rgba(229,62,62,0.08)',
                border: '1px solid rgba(229,62,62,0.2)',
                borderRadius: '12px', fontSize: '12px', color: 'var(--err)',
                fontWeight: 500,
              }}>
                {dispatchError}
              </div>
            )}

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                id="confirm-dispatch-btn"
                className="btn-accent"
                style={{ flex: 1, justifyContent: 'center', padding: '14px', fontSize: '14px' }}
                onClick={() => setShowConfirm(true)}
                disabled={!recommendedStation}
              >
                Confirm Dispatch
              </button>
              <button
                id="override-dispatch-btn"
                className="btn-secondary"
                onClick={() => setShowOverrideDrawer(true)}
              >
                Override →
              </button>
            </div>
          </div>

          {/* Confirmation dialog */}
          {showConfirm && recommendedStation && recommendedResources && (
            <div className="dialog-overlay" role="dialog" aria-modal="true">
              <div className="dialog-content">
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', marginBottom: '20px' }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: '10px',
                    background: 'rgba(246,173,85,0.12)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  }}>
                    <AlertTriangle size={18} style={{ color: 'var(--warn)' }} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '8px' }}>Confirm Dispatch</h3>
                    <p style={{ fontSize: '13px', color: 'var(--muted)', lineHeight: 1.6 }}>
                      Dispatch <strong style={{ color: 'var(--ink)' }}>{result?.dispatch.recommended_resources?.officers} officers</strong> and{' '}
                      <strong style={{ color: 'var(--ink)' }}>{result?.dispatch.recommended_resources?.vehicles} vehicles</strong> from{' '}
                      <strong style={{ color: 'var(--ink)' }}>{recommendedStation}</strong> to incident{' '}
                      <strong style={{ color: 'var(--ink)' }}>{incidentId}</strong>?
                      <br /><br />
                      This action deducts resources from the station and cannot be undone automatically.
                    </p>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                  <button className="btn-secondary" onClick={() => setShowConfirm(false)} disabled={isDispatching}>
                    Cancel
                  </button>
                  <button
                    id="confirm-dispatch-dialog"
                    className="btn-danger"
                    onClick={handleConfirmDispatch}
                    disabled={isDispatching}
                  >
                    {isDispatching
                      ? <><Loader2 size={13} className="animate-spin" /> Dispatching…</>
                      : 'Confirm Dispatch'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Override drawer */}
          {showOverrideDrawer && (
            <>
              <div className="drawer-overlay" onClick={() => setShowOverrideDrawer(false)} />
              <div className="drawer">
                <h3 style={{ fontSize: '17px', fontWeight: 700 }}>Override Dispatch</h3>
                <p style={{ fontSize: '12px', color: 'var(--muted)' }}>
                  Select an alternate station and provide a mandatory reason. Minimum 20 characters.
                </p>

                <div className="form-group">
                  <label className="form-label">Select Station</label>
                  <select
                    id="override-station"
                    className="select"
                    value={overrideStation}
                    onChange={e => setOverrideStation(e.target.value)}
                  >
                    <option value="">Choose station…</option>
                    {candidates.map(s => (
                      <option key={s.station} value={s.station}>{s.station}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Override Reason *</label>
                  <textarea
                    id="override-reason"
                    className="textarea"
                    value={overrideReason}
                    onChange={e => setOverrideReason(e.target.value)}
                    placeholder="Explain why you are overriding the AI recommendation (min. 20 characters)…"
                    rows={4}
                  />
                  <span style={{
                    fontSize: '10px',
                    color: overrideReason.length < 20 ? 'var(--err)' : 'var(--muted)',
                  }}>
                    {overrideReason.length} / 20 min characters
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '10px' }}>
                  <button className="btn-secondary" onClick={() => setShowOverrideDrawer(false)} style={{ flex: 1 }}>
                    Cancel
                  </button>
                  <button
                    id="confirm-override-btn"
                    className="btn-danger"
                    onClick={handleOverrideDispatch}
                    disabled={overrideReason.length < 20 || !overrideStation || isDispatching}
                    style={{ flex: 1 }}
                  >
                    {isDispatching ? <Loader2 size={13} className="animate-spin" /> : 'Override & Dispatch'}
                  </button>
                </div>
              </div>
            </>
          )}
      </div>
    </>
  );
}

function PageShell({ incidentId, children }: { incidentId: string; children: React.ReactNode }) {
  return (
    <>
      <PageHeading title={`Dispatch — ${incidentId}`} />
      <div className="flex-1 px-7 pb-7 overflow-auto">{children}</div>
    </>
  );
}
