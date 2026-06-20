'use client';
import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import useSWR from 'swr';
import { PageHeading } from '@/components/layout/PageHeading';
import { ReadinessBar } from '@/components/shared/ReadinessBar';
import { LoadingState, ErrorState } from '@/components/shared/LoadingState';
import { api, StationCandidate, DispatchBody } from '@/lib/api';
import { Check, AlertTriangle, Loader2, Users, Car, Truck, Shield } from 'lucide-react';
import type { ApiError } from '@/lib/api';

/**
 * Dispatch Recommendation Screen.
 * CRITICAL:
 * - Dispatch requires TWO explicit clicks (button + dialog confirm).
 * - Override requires non-empty reason field (min 20 chars).
 * - POST to /dispatch only on confirmed user action. NEVER auto-dispatches.
 */
export default function DispatchPage() {
  const params = useParams<{ id: string }>();
  const incidentId = params.id;
  const router = useRouter();

  const { data: readiness, isLoading, error } = useSWR(
    '/station-readiness',
    () => api.readiness.ranked()
  );

  const candidates = readiness?.stations.slice(0, 3) ?? [];
  const recommended = candidates[0];

  const [showConfirm, setShowConfirm] = useState(false);
  const [showOverrideDrawer, setShowOverrideDrawer] = useState(false);
  const [overrideStation, setOverrideStation] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [isDispatching, setIsDispatching] = useState(false);
  const [dispatchError, setDispatchError] = useState('');
  const [dispatchSuccess, setDispatchSuccess] = useState(false);

  const handleConfirmDispatch = async () => {
    if (!recommended) return;
    setIsDispatching(true);
    setDispatchError('');
    try {
      const body: DispatchBody = {
        incident_id: incidentId,
        station_id: recommended.station_id,
        resources_dispatched: {
          officers: recommended.available_officers,
          vehicles: recommended.available_vehicles,
          tow_trucks: recommended.available_tow_trucks,
          barricades: recommended.available_barricades,
        },
        override: false,
      };
      await api.dispatch.create(body);
      setDispatchSuccess(true);
      setTimeout(() => router.push('/dashboard'), 2000);
    } catch (err) {
      const e = err as ApiError;
      setDispatchError(e.message || 'Dispatch failed.');
    } finally {
      setIsDispatching(false);
      setShowConfirm(false);
    }
  };

  const handleOverrideDispatch = async () => {
    if (overrideReason.length < 20) return;
    setIsDispatching(true);
    setDispatchError('');
    try {
      const body: DispatchBody = {
        incident_id: incidentId,
        station_id: overrideStation,
        resources_dispatched: { officers: 2, vehicles: 1, tow_trucks: 0, barricades: 2 },
        override: true,
        override_reason: overrideReason,
      };
      await api.dispatch.create(body);
      setDispatchSuccess(true);
      setTimeout(() => router.push('/dashboard'), 2000);
    } catch (err) {
      const e = err as ApiError;
      setDispatchError(e.message || 'Override dispatch failed.');
    } finally {
      setIsDispatching(false);
      setShowOverrideDrawer(false);
    }
  };

  if (isLoading) return <PageShell incidentId={incidentId}><LoadingState message="Loading station data…" /></PageShell>;
  if (error)     return <PageShell incidentId={incidentId}><ErrorState message="Failed to load stations." /></PageShell>;

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

            {/* Recommended station */}
            {recommended && (
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
                      {recommended.station_name}
                    </h2>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '10px', color: 'rgba(17,17,17,0.5)', marginBottom: '2px' }}>
                      Readiness
                    </div>
                    <div style={{ fontSize: '32px', fontWeight: 800, letterSpacing: '-0.03em' }}>
                      {Math.round(Number(recommended.readiness_score))}
                    </div>
                  </div>
                </div>

                <ReadinessBar score={Number(recommended.readiness_score)} />

                <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  {recommended.reasons?.map((r, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px' }}>
                      <Check size={13} style={{ color: 'var(--ink)', marginTop: '1px', flexShrink: 0 }} />
                      {r}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Resource package */}
            {recommended && (
              <div className="card">
                <div style={{
                  fontSize: '11px', fontWeight: 700, color: 'var(--muted)',
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '16px',
                }}>
                  Resource Package
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                  {[
                    { icon: <Users size={18} />, count: recommended.available_officers, label: 'Officers' },
                    { icon: <Car size={18} />,   count: recommended.available_vehicles,  label: 'Vehicles' },
                    { icon: <Truck size={18} />, count: recommended.available_tow_trucks, label: 'Tow Trucks' },
                    { icon: <Shield size={18} />,count: recommended.available_barricades, label: 'Barricades' },
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
                    <tr key={s.station_id}>
                      <td>
                        {i === 0 && (
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                            width: 18, height: 18, borderRadius: '5px',
                            background: 'var(--lime)', fontSize: '10px', fontWeight: 700,
                            marginRight: '8px',
                          }}>★</span>
                        )}
                        <span style={{ fontWeight: i === 0 ? 600 : 400 }}>{s.station_name}</span>
                      </td>
                      <td style={{ minWidth: '140px' }}>
                        <ReadinessBar score={Number(s.readiness_score)} />
                      </td>
                      <td>{s.available_officers}</td>
                      <td>{s.available_vehicles}</td>
                      <td>{s.active_incidents}</td>
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
                disabled={!recommended}
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
          {showConfirm && recommended && (
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
                      Dispatch <strong style={{ color: 'var(--ink)' }}>{recommended.available_officers} officers</strong> and{' '}
                      <strong style={{ color: 'var(--ink)' }}>{recommended.available_vehicles} vehicles</strong> from{' '}
                      <strong style={{ color: 'var(--ink)' }}>{recommended.station_name}</strong> to incident{' '}
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
                      <option key={s.station_id} value={s.station_id}>{s.station_name}</option>
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
