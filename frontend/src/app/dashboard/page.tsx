'use client';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { Activity, Clock, Users, AlertTriangle, ArrowUpRight, Bell, X, ExternalLink, TrendingUp } from 'lucide-react';
import { PageHeading } from '@/components/layout/PageHeading';
import { StatCard } from '@/components/shared/StatCard';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { ReadinessBar } from '@/components/shared/ReadinessBar';
import { LoadingState, EmptyState } from '@/components/shared/LoadingState';
import { StatisticsPanel } from '@/components/dashboard/StatisticsPanel';
import { useKPIs } from '@/hooks/useKPIs';
import { useStations } from '@/hooks/useStations';
import useSWR from 'swr';
import useSWRImmutable from 'swr/immutable';
import { api, Incident } from '@/lib/api';
import { listStationReadiness } from '@/api/finalEndpointsApi';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { Skeleton } from '@/components/shared/Skeleton';

const BengaluruMap = dynamic(
  () => import('@/components/map/BengaluruMap').then(m => m.BengaluruMap),
  { ssr: false, loading: () => <div className="card h-[420px]"><Skeleton height={420} /></div> }
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
    <motion.div 
      initial={{ opacity: 0, y: 50, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      transition={{ type: 'spring', damping: 25, stiffness: 300 }}
      style={{
      position: 'fixed', bottom: 24, right: 24, zIndex: 99999,
      background: '#111111', borderRadius: 18, padding: '16px 20px',
      boxShadow: '0 8px 40px rgba(0,0,0,0.35)', width: 340,
      display: 'flex', flexDirection: 'column', gap: 10,
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
        <button onClick={onClose} className="hover:bg-white/10 p-1 rounded-md transition-colors" style={{ border: 'none', color: '#6B7280', cursor: 'pointer' }}>
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
        className="hover:scale-105 active:scale-95 transition-transform"
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '8px 14px', background: '#CDFF50', borderRadius: 9999,
          fontSize: 12, fontWeight: 600, color: '#111111', textDecoration: 'none',
          width: 'fit-content',
        }}
      >
        View Incident <ExternalLink size={12} />
      </Link>
    </motion.div>
  );
}

// ── Active incidents hook with new-incident detection ──────────────────────

function useActiveIncidentsWithNotifications() {
  const result = useSWR('/incidents/active', () => api.incidents.active(), { refreshInterval: 5000 });

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
  
  const { data: riskZonesData, isLoading: riskZonesLoading } = useSWRImmutable(
    '/risk-zones', () => api.risk.zones()
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
    if (yesterdayTotal === 0) return todayTotal > 0 ? "New" : 0;
    return Math.round(((todayTotal - yesterdayTotal) / yesterdayTotal) * 100);
  })();

  const isDev = process.env.NODE_ENV === 'development';
  const [testToast, setTestToast] = useState<Incident | null>(null);

  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const isKpisLoading = !mounted || kpisLoading;
  const isTrendsLoading = !mounted || trendsLoading;
  const isReadinessLoading = !mounted || readinessLoading;
  const isRiskZonesLoading = !mounted || riskZonesLoading;
  const topRiskZones = (riskZonesData ?? []).slice(0, 3);

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

      <div className="flex-1 px-4 md:px-7 pb-7 grid grid-cols-12 gap-4 overflow-auto">

          {/* ── ROW 1: Live Incident Queue (primary focus, full width) ── */}
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.3 }}
            className="col-span-12 lg:col-span-8 card overflow-hidden min-w-0" 
            style={{ padding: 0 }}
          >
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
                      className="hover:bg-gray-100 hover:border-gray-400 active:scale-95 transition-all focus:ring-2 focus:ring-gray-300 focus:outline-none"
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
                  <Link href="/incidents/new" className="text-xs text-text-2 flex items-center gap-1 no-underline hover:text-text-1 hover:-translate-y-0.5 transition-transform">
                    New <ArrowUpRight size={14} />
                  </Link>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="data-table min-w-[600px] w-full">
                  <thead>
                  <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Corridor</th>
                    <th>Priority</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <motion.tbody
                  initial="hidden"
                  animate="visible"
                  variants={{
                    hidden: { opacity: 0 },
                    visible: { opacity: 1, transition: { staggerChildren: 0.05 } }
                  }}
                >
                  {(activeIncidents || []).slice(0, 8).map(inc => (
                    <motion.tr
                      key={inc.incident_id}
                      variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 } }}
                      onClick={() => {
                        if (inc.latitude && inc.longitude) {
                          setHighlightedIncidentId(prev =>
                            prev === inc.incident_id ? null : inc.incident_id
                          );
                        } else {
                          router.push(`/incidents/${inc.incident_id}`);
                        }
                      }}
                      className="hover:bg-gray-50 transition-colors focus:outline-none"
                      tabIndex={0}
                      onKeyDown={(e) => {
                         if (e.key === 'Enter') router.push(`/incidents/${inc.incident_id}`);
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
                    </motion.tr>
                  ))}
                  {(!activeIncidents || activeIncidents.length === 0) && (
                    <motion.tr variants={{ hidden: { opacity: 0 }, visible: { opacity: 1 } }}>
                      <td colSpan={5}>
                        {!activeIncidents ? (
                          <div className="flex flex-col gap-3 p-4">
                            <Skeleton height={40} />
                            <Skeleton height={40} />
                            <Skeleton height={40} />
                          </div>
                        ) : (
                          <EmptyState message="No active incidents" />
                        )}
                      </td>
                    </motion.tr>
                  )}
                </motion.tbody>
              </table>
              </div>
            </motion.div>

          {/* Map — right side, spans 2 rows */}
          <motion.div 
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="col-span-12 lg:col-span-4 lg:row-span-2 min-w-0" 
            style={{ position: 'relative', minHeight: '400px' }}
          >
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
          </motion.div>

          {/* ── ROW 2: Stat cards ── */}
          <motion.div 
            initial="hidden" 
            animate="visible" 
            variants={{ visible: { transition: { staggerChildren: 0.15, delayChildren: 0.2 } } }}
            className="col-span-12 lg:col-span-8 grid grid-cols-1 sm:grid-cols-2 gap-4 items-stretch min-w-0"
          >
            <StatCard
              icon={AlertTriangle}
              title="Active Incidents"
              value={kpis?.active_incidents ?? 0}
              percentage={activeChange}
              usedDots={kpis?.active_incidents ? Math.min(10, Math.ceil(kpis.active_incidents / 2)) : 0}
              totalDots={10}
              isLoading={isKpisLoading || isTrendsLoading}
            />
            <StatCard
              icon={Clock}
              title="Avg Resolution"
              value={kpis?.avg_resolution_minutes != null ? kpis.avg_resolution_minutes : "—"}
              total={kpis?.avg_resolution_minutes != null ? "min" : ""}
              percentage={kpis?.avg_resolution_minutes != null ? 8 : undefined}
              usedDots={kpis?.avg_resolution_minutes != null ? 8 : 0}
              totalDots={kpis?.avg_resolution_minutes != null ? 10 : 0}
              variant="accent"
              isLoading={isKpisLoading}
            />
          </motion.div>

          {/* ── ROW 3: Statistics chart ── */}
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.4 }}
            className="col-span-12 lg:col-span-4 min-w-0"
          >
            <div className="card">
              {isTrendsLoading ? (
                <div className="flex items-center justify-center h-full min-h-[200px]">
                  <Skeleton width="100%" height={200} />
                </div>
              ) : (
                <StatisticsPanel data={trendData} />
              )}
            </div>
          </motion.div>

          {/* Emerging Hotspots */}
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.4 }}
            className="col-span-12 md:col-span-6 lg:col-span-4 min-w-0"
          >
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div className="flex items-center justify-between p-5 border-b border-border">
                <h3 className="text-sm font-bold text-text-1" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <TrendingUp size={16} color="var(--err)" /> Emerging Hotspots
                </h3>
              </div>
              {isRiskZonesLoading ? (
                <div className="flex flex-col gap-3 p-4">
                  <Skeleton height={50} />
                  <Skeleton height={50} />
                  <Skeleton height={50} />
                </div>
              ) : (
                <motion.div initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.05 } } }}>
                  {topRiskZones.map(zone => (
                    <motion.div
                      variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 } }}
                      key={zone.corridor}
                      className="flex flex-col gap-2 p-4 border-b border-border cursor-pointer hover:bg-surface-raised hover:translate-x-1 transition-all"
                      onClick={() => router.push('/stations')}
                    >
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-sm font-semibold text-text-1">{zone.corridor}</span>
                        {zone.rate_ratio > 1.5 && (
                          <span style={{
                            padding: '2px 8px', borderRadius: 9999,
                            background: '#FEE2E2', color: '#DC2626',
                            fontSize: 10, fontWeight: 700, textTransform: 'uppercase'
                          }}>
                            Emerging Risk Zone
                          </span>
                        )}
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-text-2">
                          {zone.rate_ratio > 1 ? '+' : ''}{Math.round((zone.rate_ratio - 1) * 100)}% month-over-month
                        </span>
                        <span className="text-[11px] font-mono text-text-2">{zone.incident_count_30d} incidents</span>
                      </div>
                    </motion.div>
                  ))}
                  {topRiskZones.length === 0 && <EmptyState message="No emerging risks detected" />}
                </motion.div>
              )}
            </div>
          </motion.div>

          {/* Station Readiness */}
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.4 }}
            className="col-span-12 md:col-span-6 lg:col-span-4 min-w-0"
          >
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div className="flex items-center justify-between p-5 border-b border-border">
                <h3 className="text-sm font-bold text-text-1">Station Readiness</h3>
                <Link href="/stations" className="text-xs text-text-2 flex items-center gap-1 no-underline hover:text-text-1 hover:-translate-y-0.5 transition-transform">
                  All <ArrowUpRight size={14} />
                </Link>
              </div>
              {isReadinessLoading ? (
                <div className="flex flex-col gap-3 p-4">
                  <Skeleton height={50} />
                  <Skeleton height={50} />
                  <Skeleton height={50} />
                </div>
              ) : (
                <motion.div initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.05 } } }}>
                  {top5.map(station => (
                    <motion.div
                      variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 } }}
                      key={station.station}
                      className="flex flex-col gap-2 p-4 border-b border-border cursor-pointer hover:bg-surface-raised hover:translate-x-1 transition-all"
                      onClick={() => router.push('/stations')}
                    >
                      <div className="flex justify-between items-center">
                        <span className="text-xs font-semibold text-text-1">{station.station}</span>
                        <span className="text-[11px] text-text-2">{station.active_incidents} active</span>
                      </div>
                      <ReadinessBar score={Number(station.readiness_score)} />
                    </motion.div>
                  ))}
                  {top5.length === 0 && <EmptyState message="No station data" />}
                </motion.div>
              )}
            </div>
          </motion.div>
        </div>
      {/* Real-time notification toasts */}
      <AnimatePresence>
        {newIncident && (
          <IncidentToast incident={newIncident} onClose={clearNewIncident} />
        )}
        {testToast && (
          <IncidentToast incident={testToast} onClose={() => setTestToast(null)} />
        )}
      </AnimatePresence>

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
