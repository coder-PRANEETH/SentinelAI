'use client';
import { useState } from 'react';
import useSWR from 'swr';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { PageHeading } from '@/components/layout/PageHeading';
import { KPICard } from '@/components/shared/KPICard';
import { LoadingState, ErrorState } from '@/components/shared/LoadingState';
import { IncidentDensityMap } from '@/components/map/IncidentDensityMap';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { Skeleton } from '@/components/shared/Skeleton';

/**
 * Analytics Dashboard — SUPERVISOR and ADMIN roles only.
 * Charts use Recharts with design system colors. No 3D, no pie, no donut.
 */
export default function AnalyticsPage({ hideHeading = false }: { hideHeading?: boolean } = {}) {
  const { hasRole, isAuthenticated } = useAuth();
  const router = useRouter();

  // Role guard
  useEffect(() => {
    if (isAuthenticated && !hasRole('SUPERVISOR', 'ADMIN')) {
      router.replace('/dashboard');
    }
  }, [isAuthenticated, hasRole, router]);

  const { data: accuracy, isLoading: accLoading } = useSWR('/analytics/model-accuracy', api.analytics.modelAccuracy);
  const { data: trends, isLoading: trendsLoading } = useSWR('/analytics/trends', () => api.analytics.trends(30));
  const { data: histogram, isLoading: histLoading } = useSWR('/analytics/histogram', () => api.analytics.histogram(30));
  const { data: corridors, isLoading: corridorsLoading } = useSWR('/analytics/corridors', api.analytics.corridors);
  
  // Fetch up to 1000 recent incidents so the heatmap has enough density to render visible blobs
  const { data: incidents } = useSWR('/incidents/heatmap', () => api.incidents.list({ limit: 1000 }));

  return (
    <>
      {!hideHeading && <PageHeading title="Analytics" />}
      <motion.div 
        initial="hidden" animate="visible" 
        variants={{ visible: { transition: { staggerChildren: 0.1 } } }}
        className="flex-1 px-7 pb-7 overflow-auto"
      >

          {/* Row 1: Model accuracy KPIs */}
          <motion.div variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }} style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
            <KPICard
              label="Priority Accuracy"
              value={accuracy ? `${accuracy.priority_accuracy.toFixed(1)}%` : '—'}
              isLoading={accLoading}
            />
            <KPICard
              label="Avg Resolution Error"
              value={accuracy ? `${Math.round(accuracy.avg_resolution_error_minutes)} min` : '—'}
              isLoading={accLoading}
            />
            <KPICard
              label="Road Closure Accuracy"
              value={accuracy ? `${accuracy.road_closure_accuracy.toFixed(1)}%` : '—'}
              isLoading={accLoading}
            />
            <KPICard
              label="Feedback Records"
              value={accuracy?.feedback_count ?? '—'}
              isLoading={accLoading}
            />
          </motion.div>

          {/* Row 2: Charts side by side */}
          <motion.div variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }} style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '16px', marginBottom: '24px' }}>
            {/* Incident trend line chart */}
            <div className="chart-container">
              <h3 style={{ fontSize: '13px', fontWeight: 700, marginBottom: '16px' }}>Incident Trend (Last 30 Days)</h3>
              {trendsLoading ? <Skeleton width="100%" height={240} /> : (
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={trends ?? []}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--muted)' }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '10px', fontSize: '12px' }}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                    <Line type="monotone" dataKey="P1" stroke="#E53E3E" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="P2" stroke="#F6AD55" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="P3" stroke="#ECC94B" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="P4" stroke="#4299E1" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Resolution time histogram */}
            <div className="chart-container">
              <h3 style={{ fontSize: '13px', fontWeight: 700, marginBottom: '16px' }}>Resolution Time Distribution</h3>
              {histLoading ? <Skeleton width="100%" height={240} /> : (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={histogram ?? []}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="bucket" tick={{ fontSize: 10, fill: 'var(--muted)' }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '10px', fontSize: '12px' }} />
                    <Bar dataKey="count" fill="var(--lime)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </motion.div>

          {/* Row 3: Incident Density Map */}
          <motion.div variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }} className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: '24px', display: 'flex', flexDirection: 'column', height: '480px' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', fontSize: '14px', fontWeight: 700, background: 'var(--surface)', zIndex: 2 }}>
              Incident Density Map
            </div>
            <div style={{ flex: 1, position: 'relative' }}>
              <IncidentDensityMap incidents={incidents ?? []} height="100%" />
            </div>
          </motion.div>

          {/* Row 4: Corridor performance table */}
          <motion.div variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }} className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', fontSize: '14px', fontWeight: 700 }}>
              Corridor Performance
            </div>
            {corridorsLoading ? (
              <div className="flex flex-col gap-3 p-5">
                <Skeleton height={40} />
                <Skeleton height={40} />
                <Skeleton height={40} />
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Corridor</th>
                    <th>Incidents</th>
                    <th>Avg Resolution</th>
                    <th>P1 Rate</th>
                    <th>Most Common Type</th>
                  </tr>
                </thead>
                <motion.tbody initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.05 } } }}>
                  {(corridors ?? []).map(c => (
                    <motion.tr variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 } }} key={c.corridor} className="hover:bg-gray-50 transition-colors cursor-pointer">
                      <td style={{ fontWeight: 500 }}>{c.corridor}</td>
                      <td>{c.incident_count}</td>
                      <td>{Math.round(c.avg_resolution_minutes)} min</td>
                      <td>
                        <span style={{ color: c.p1_rate > 0.5 ? 'var(--p1)' : 'var(--ink)' }}>
                          {(c.p1_rate * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td style={{ color: 'var(--color-text-secondary)' }}>{c.most_common_type}</td>
                    </motion.tr>
                  ))}
                </motion.tbody>
              </table>
            )}
          </motion.div>
      </motion.div>
    </>
  );
}
