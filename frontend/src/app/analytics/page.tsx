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
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

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

  return (
    <>
      {!hideHeading && <PageHeading title="Analytics" />}
      <div className="flex-1 px-7 pb-7 overflow-auto">

          {/* Row 1: Model accuracy KPIs */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
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
          </div>

          {/* Row 2: Charts side by side */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '16px', marginBottom: '24px' }}>
            {/* Incident trend line chart */}
            <div className="chart-container">
              <h3 style={{ fontSize: '13px', fontWeight: 700, marginBottom: '16px' }}>Incident Trend (Last 30 Days)</h3>
              {trendsLoading ? <LoadingState message="Loading trends…" /> : (
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
              {histLoading ? <LoadingState message="Loading histogram…" /> : (
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
          </div>

          {/* Row 3: Corridor performance table */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', fontSize: '14px', fontWeight: 700 }}>
              Corridor Performance
            </div>
            {corridorsLoading ? (
              <LoadingState message="Loading corridor data…" />
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
                <tbody>
                  {(corridors ?? []).map(c => (
                    <tr key={c.corridor}>
                      <td style={{ fontWeight: 500 }}>{c.corridor}</td>
                      <td>{c.incident_count}</td>
                      <td>{Math.round(c.avg_resolution_minutes)} min</td>
                      <td>
                        <span style={{ color: c.p1_rate > 0.5 ? 'var(--p1)' : 'var(--ink)' }}>
                          {(c.p1_rate * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td style={{ color: 'var(--color-text-secondary)' }}>{c.most_common_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
      </div>
    </>
  );
}
