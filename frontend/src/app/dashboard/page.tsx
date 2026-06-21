'use client';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { Activity, Clock, Users, AlertTriangle, ArrowUpRight, Bell, X, ExternalLink } from 'lucide-react';
import { PageHeading } from '@/components/layout/PageHeading';
import { StatCard } from '@/components/shared/StatCard';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { ReadinessBar } from '@/components/shared/ReadinessBar';
import { LoadingState, EmptyState } from '@/components/shared/LoadingState';
import { StatisticsPanel } from '@/components/dashboard/StatisticsPanel';
import { useKPIs } from '@/hooks/useKPIs';
import { useStations } from '@/hooks/useStations';
import useSWRImmutable from 'swr/immutable';
import { api, Incident } from '@/lib/api';
import { listStationReadiness } from '@/api/finalEndpointsApi';
import Link from 'next/link';

const BengaluruMap = dynamic(
  () => import('@/components/map/BengaluruMap').then(m => m.BengaluruMap),
  { ssr: false, loading: () => <div className="card h-[420px] flex items-center justify-center"><LoadingState message="Loading map…" /></div> }
);

const PRIORITY_COLORS: Record<string, { bg: string; text: string }> = {
  P1: { bg: '#FEE2E2', text: '#DC2626' },
  P2: { bg: '#FEF3C7', text: '#D97706' },
  P3: { bg: '#FEF9C3', text: '#A16207' },
  P4: { bg: '#DBEAFE', text: '#1D4ED8' },
};

// ── Incident toast notification ─────────────────────────────────────────────

function IncidentToast({ incident, onClose }: { incident: Incident; onClose: () => void }) {
  const priority = incident.predicted_priority ?? 'P4';
  const c = PRIORITY_COLORS[priority] ?? { bg: '#F3F4F6', text: '#6B7280' };

  useEffect(() => {
    const timer = setTimeout(onClose, 8000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24, zIndex: 99999,
      background: '#111111', borderRadius: 18, padding: '16px 20px',
      boxShadow: '0 8px 40px rgba(0,0,0,0.35)', width: 340,
      display: 'flex', flexDirection: 'column', gap: 10,
      animation: 'slideUp 0.3s ease',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%', background: c.text,
            boxShadow: `0 0 0 3px ${c.bg}`, flexShrink: 0,
          }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: '#CDFF50', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            🚨 New Incident
          </span>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#6B7280', cursor: 'pointer' }}>
          <X size={14} />
        </button>
      </div>

      <div>
        <div style={{ fontSize: 15, fontWeight: 700, color: '#FFFFFF', marginBottom: 4 }}>
          {incident.incident_type || 'Unknown Incident'}
        </div>
        <div style={{ fontSize: 12, color: '#9CA3AF' }}>
          {incident.location || incident.corridor || 'Location unknown'}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{
          padding: '3px 10px', borderRadius: 9999, fontSize: 11, fontWeight: 700,
          background: c.bg, color: c.text,
        }}>
          {priority}
        </span>
        <span style={{ fontSize: 11, color: '#6B7280', fontFamily: 'monospace' }}>
          {incident.incident_id}
        </span>
      </div>

      <Link
        href={`/incidents/${incident.incident_id}`}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '8px 14px', background: '#CDFF50', borderRadius: 9999,
          fontSize: 12, fontWeight: 600, color: '#111111', textDecoration: 'none',
          width: 'fit-content',
        }}
      >
        View Incident <ExternalLink size={12} />
      </Link>
    </div>
  );
}

// ── Active incidents hook with new-incident detection ──────────────────────

function useActiveIncidentsWithNotifications() {
  const result = useSWRImmutable('/incidents/active', () => api.incidents.active());

  return {
    ...result,
    newIncident: null as Incident | null,
    clearNewIncident: () => {},
  };
}

// ── Test incident simulation ───────────────────────────────────────────────

const TEST_INCIDENT: Incident = {
  incident_id: 'TEST-DEMO',
  incident_type: 'Vehicle Breakdown',
  status: 'REPORTED',
  latitude: 12.9352,
  longitude: 77.6245,
  predicted_priority: 'P1',
  corridor: 'Outer Ring Road',
  location: 'Near Iblur Junction, Outer Ring Road',
};

// ── Main Dashboard ─────────────────────────────────────────────────────────

export default function DashboardPage() {
  const router = useRouter();
  const { kpis, isLoading: kpisLoading } = useKPIs(30000);
  const { stations } = useStations(30000);
  const { data: readinessData, isLoading: readinessLoading } = useSWRImmutable(
    '/station-readiness', () => listStationReadiness()
  );
  const { data: activeIncidents, newIncident, clearNewIncident } = useActiveIncidentsWithNotifications();
  const [highlightedIncidentId, setHighlightedIncidentId] = useState<string | null>(null);

  const top5 = (readinessData ?? []).slice(0, 5);

  const { data: trendDataRaw, isLoading: trendsLoading } = useSWRImmutable(
    '/analytics/trends',
    () => api.analytics.trends(7)
  );

  const trendData = (trendDataRaw || []).map(d => ({
    date: d.date,
    count: d.P1 + d.P2 + d.P3 + d.P4,
  }));

  const activeChange = (() => {
    if (!trendDataRaw || trendDataRaw.length < 2) return 0;
    const today = trendDataRaw[trendDataRaw.length - 1];
    const yesterday = trendDataRaw[trendDataRaw.length - 2];
    const todayTotal = today.P1 + today.P2 + today.P3 + today.P4;
    const yesterdayTotal = yesterday.P1 + yesterday.P2 + yesterday.P3 + yesterday.P4;
    if (yesterdayTotal === 0) return todayTotal > 0 ? 100 : 0;
    return Math.round(((todayTotal - yesterdayTotal) / yesterdayTotal) * 100);
  })();

  const isDev = process.env.NODE_ENV === 'development';
  const [testToast, setTestToast] = useState<Incident | null>(null);

  return (
    <div className="flex flex-col h-full">
      <PageHeading title={
        <>
          <span
            style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: '36px', height: '36px', borderRadius: '10px',
              backgroundColor: '#CDFF50', flexShrink: 0,
            }}
          >
            <Activity size={18} color="#111111" strokeWidth={2.5} />
          </span>
          Traffic Incident Command
        </>
      } />

      <div className="flex-1 px-7 pb-7 grid grid-cols-12 gap-4 overflow-auto">

          {/* ── ROW 1: Live Incident Queue (primary focus, full width) ── */}
          <div className="col-span-8">
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div className="flex items-center justify-between p-5 border-b border-border">
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <h3 className="text-sm font-bold text-text-1">Live Incident Queue</h3>
                  {activeIncidents && activeIncidents.length > 0 && (
                    <span style={{
                      padding: '2px 8px', borderRadius: 9999,
                      background: '#FEE2E2', color: '#DC2626',
                      fontSize: 11, fontWeight: 700,
                    }}>
                      {activeIncidents.length} active
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {isDev && (
                    <button
                      onClick={() => setTestToast(TEST_INCIDENT)}
                      title="Test incident notification"
                      style={{
                        display: 'flex', alignItems: 'center', gap: 5,
                        padding: '4px 10px', borderRadius: 9999, fontSize: 11,
                        background: '#F3F4F6', border: '1px dashed #D0D0D0',
                        color: '#6B7280', cursor: 'pointer', fontWeight: 600,
                      }}
                    >
                      <Bell size={11} /> Test Alert
                    </button>
                  )}
                  <Link href="/incidents/new" className="text-xs text-text-2 flex items-center gap-1 no-underline hover:text-text-1">
                    New <ArrowUpRight size={14} />
                  </Link>
                </div>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Corridor</th>
                    <th>Priority</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(activeIncidents || []).slice(0, 8).map(inc => (
                    <tr
                      key={inc.incident_id}
                      onClick={() => {
                        if (inc.latitude && inc.longitude) {
                          setHighlightedIncidentId(prev =>
                            prev === inc.incident_id ? null : inc.incident_id
                          );
                        } else {
                          router.push(`/incidents/${inc.incident_id}`);
                        }
                      }}
                      style={{
                        cursor: 'pointer',
                        background: highlightedIncidentId === inc.incident_id ? '#F0FDF4' : undefined,
                        outline: highlightedIncidentId === inc.incident_id ? '2px solid #B9E63F' : undefined,
                        outlineOffset: '-1px',
                      }}
                    >
                      <td className="font-mono text-xs text-text-2">{inc.incident_id}</td>
                      <td className="font-medium">{inc.incident_type}</td>
                      <td className="text-text-2">{inc.corridor}</td>
                      <td><StatusBadge priority={inc.predicted_priority as any} /></td>
                      <td><StatusBadge status={inc.status as any} /></td>
                    </tr>
                  ))}
                  {(!activeIncidents || activeIncidents.length === 0) && (
                    <tr>
                      <td colSpan={5}><EmptyState message="No active incidents" /></td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Map — right side, spans 2 rows */}
          <div className="col-span-4 row-span-2" style={{ position: 'relative', minHeight: '400px' }}>
            <div className="card" style={{ padding: 0, position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <BengaluruMap
                stations={stations}
                incidents={activeIncidents || []}
                height="100%"
                highlightedIncidentId={highlightedIncidentId}
                onIncidentClick={(inc) => {
                  if (inc.latitude && inc.longitude) {
                    setHighlightedIncidentId(prev =>
                      prev === inc.incident_id ? null : inc.incident_id
                    );
                  } else {
                    router.push(`/incidents/${inc.incident_id}`);
                  }
                }}
              />
            </div>
          </div>

          {/* ── ROW 2: Stat cards ── */}
          <div className="col-span-8 grid grid-cols-2 gap-4 items-stretch">
            <StatCard
              icon={AlertTriangle}
              title="Active Incidents"
              value={kpis?.active_incidents ?? 0}
              percentage={activeChange}
              usedDots={kpis?.active_incidents ? Math.min(10, Math.ceil(kpis.active_incidents / 2)) : 0}
              totalDots={10}
              isLoading={kpisLoading || trendsLoading}
            />
            <StatCard
              icon={Clock}
              title="Avg Resolution"
              value={kpis?.avg_resolution_minutes ?? 0}
              total="min"
              percentage={8}
              usedDots={8}
              totalDots={10}
              variant="accent"
              isLoading={kpisLoading}
            />
          </div>

          {/* ── ROW 3: Statistics chart ── */}
          <div className="col-span-7">
            <div className="card">
              {trendsLoading ? <LoadingState message="Loading trend data…" /> : <StatisticsPanel data={trendData} />}
            </div>
          </div>

          {/* Station Readiness */}
          <div className="col-span-5">
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div className="flex items-center justify-between p-5 border-b border-border">
                <h3 className="text-sm font-bold text-text-1">Station Readiness</h3>
                <Link href="/stations" className="text-xs text-text-2 flex items-center gap-1 no-underline hover:text-text-1">
                  All <ArrowUpRight size={14} />
                </Link>
              </div>
              {readinessLoading ? (
                <LoadingState message="Loading…" size="sm" />
              ) : (
                <div>
                  {top5.map(station => (
                    <div
                      key={station.station}
                      className="flex flex-col gap-2 p-4 border-b border-border cursor-pointer hover:bg-surface-raised transition-colors"
                      onClick={() => router.push('/stations')}
                    >
                      <div className="flex justify-between items-center">
                        <span className="text-xs font-semibold text-text-1">{station.station}</span>
                        <span className="text-[11px] text-text-2">{station.active_incidents} active</span>
                      </div>
                      <ReadinessBar score={Number(station.readiness_score)} />
                    </div>
                  ))}
                  {top5.length === 0 && <EmptyState message="No station data" />}
                </div>
              )}
            </div>
          </div>
        </div>
      {/* Real-time notification toasts */}
      {newIncident && (
        <IncidentToast incident={newIncident} onClose={clearNewIncident} />
      )}
      {testToast && (
        <IncidentToast incident={testToast} onClose={() => setTestToast(null)} />
      )}

      {/* Slide-up animation */}
      <style>{`
        @keyframes slideUp {
          from { transform: translateY(24px); opacity: 0; }
          to   { transform: translateY(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
