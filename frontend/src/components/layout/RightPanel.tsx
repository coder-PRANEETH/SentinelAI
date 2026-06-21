'use client';

import { usePathname, useRouter } from 'next/navigation';
import { AlertTriangle, Clock, CheckCircle, Radio, ArrowUpRight, Activity } from 'lucide-react';
import Link from 'next/link';
import useSWRImmutable from 'swr/immutable';
import { api, Incident } from '@/lib/api';

const PRIORITY_COLORS: Record<string, { bg: string; text: string }> = {
  P1: { bg: '#FEE2E2', text: '#DC2626' },
  P2: { bg: '#FEF3C7', text: '#D97706' },
  P3: { bg: '#FEF9C3', text: '#A16207' },
  P4: { bg: '#DBEAFE', text: '#1D4ED8' },
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  REPORTED: <AlertTriangle size={12} style={{ color: '#D97706' }} />,
  UNDER_ASSESSMENT: <Clock size={12} style={{ color: '#6B7280' }} />,
  RESOURCES_ASSIGNED: <Radio size={12} style={{ color: '#2563EB' }} />,
  IN_PROGRESS: <Activity size={12} style={{ color: '#059669' }} />,
  RESOLVED: <CheckCircle size={12} style={{ color: '#059669' }} />,
};

function timeAgo(dateStr?: string): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function RightPanel() {
  const pathname = usePathname();
  const router = useRouter();

  const isDashboard = pathname === '/dashboard';

  const { data: incidents, isLoading } = useSWRImmutable(
    isDashboard ? '/incidents/active' : null,
    () => api.incidents.active()
  );

  const { data: kpis } = useSWRImmutable(
    isDashboard ? '/analytics/kpis' : null,
    () => api.analytics.kpis()
  );

  if (!isDashboard) {
    return null;
  }

  const recentFive = (incidents || []).slice(0, 5);
  const p1Count = (incidents || []).filter(i => i.predicted_priority === 'P1').length;

  return (
    <aside className="right-panel">

      {/* Quick stats strip */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <Link href="/incidents/new" style={{ textDecoration: 'none' }}>
          <div className="right-panel-grid-item">
            <div className="right-panel-grid-icon">
              <AlertTriangle size={15} style={{ color: '#DC2626' }} />
            </div>
            <div style={{ lineHeight: 1.2 }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#111111' }}>{kpis?.active_incidents ?? '—'}</div>
              <span className="right-panel-grid-label" style={{ fontSize: 11, color: '#6B7280', fontWeight: 500 }}>Active</span>
            </div>
          </div>
        </Link>

        <Link href="/stations" style={{ textDecoration: 'none' }}>
          <div className="right-panel-grid-item">
            <div className="right-panel-grid-icon">
              <Radio size={15} style={{ color: '#2563EB' }} />
            </div>
            <div style={{ lineHeight: 1.2 }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#111111' }}>{kpis?.resources_deployed ?? '—'}</div>
              <span className="right-panel-grid-label" style={{ fontSize: 11, color: '#6B7280', fontWeight: 500 }}>Deployed</span>
            </div>
          </div>
        </Link>

        <div className="right-panel-grid-item" style={{ cursor: 'default' }}>
          <div className="right-panel-grid-icon">
            <Clock size={15} style={{ color: '#D97706' }} />
          </div>
          <div style={{ lineHeight: 1.2 }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#111111' }}>
              {kpis?.avg_resolution_minutes != null ? `${kpis.avg_resolution_minutes}m` : '—'}
            </div>
            <span className="right-panel-grid-label" style={{ fontSize: 11, color: '#6B7280', fontWeight: 500 }}>Avg Resolve</span>
          </div>
        </div>

        <div className="right-panel-grid-item" style={{ cursor: 'default' }}>
          <div className="right-panel-grid-icon">
            <Activity size={15} style={{ color: p1Count > 0 ? '#DC2626' : '#9CA3AF' }} />
          </div>
          <div style={{ lineHeight: 1.2 }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: p1Count > 0 ? '#DC2626' : '#111111' }}>{p1Count}</div>
            <span className="right-panel-grid-label" style={{ fontSize: 11, color: '#6B7280', fontWeight: 500 }}>P1 Critical</span>
          </div>
        </div>
      </div>

      {/* Live Activity Feed */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Live Activity
        </div>
        <Link href="/dashboard" style={{ fontSize: 11, color: '#9CA3AF', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 3 }}>
          All <ArrowUpRight size={10} />
        </Link>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {isLoading ? (
          <div style={{ fontSize: 12, color: '#9CA3AF', textAlign: 'center', padding: '16px 0' }}>
            Loading…
          </div>
        ) : recentFive.length === 0 ? (
          <div style={{ fontSize: 12, color: '#9CA3AF', textAlign: 'center', padding: '16px 0' }}>
            No active incidents
          </div>
        ) : (
          recentFive.map(inc => {
            const priority = inc.predicted_priority ?? 'P4';
            const c = PRIORITY_COLORS[priority] ?? { bg: '#F3F4F6', text: '#6B7280' };
            const statusIcon = STATUS_ICONS[inc.status] ?? <Clock size={12} style={{ color: '#9CA3AF' }} />;

            return (
              <div
                key={inc.incident_id}
                className="right-panel-link"
                onClick={() => router.push(`/incidents/${inc.incident_id}`)}
                style={{ flexDirection: 'column', gap: 6, alignItems: 'stretch', cursor: 'pointer' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {statusIcon}
                    <span style={{
                      padding: '1px 7px', borderRadius: 9999,
                      fontSize: 10, fontWeight: 700,
                      background: c.bg, color: c.text,
                    }}>
                      {priority}
                    </span>
                  </div>
                  <span style={{ fontSize: 10, color: '#9CA3AF' }}>{timeAgo(inc.created_at)}</span>
                </div>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#111111', lineHeight: 1.3 }}>
                  {inc.incident_type || 'Unknown'}
                </div>
                <div style={{ fontSize: 11, color: '#6B7280' }}>
                  {inc.corridor || inc.location || inc.incident_id}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Pending actions */}
      {p1Count > 0 && (
        <div style={{
          padding: '10px 14px', background: '#FEE2E2', borderRadius: 12,
          border: '1px solid #FECACA',
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#DC2626', marginBottom: 4 }}>
            ⚠ {p1Count} Critical Incident{p1Count > 1 ? 's' : ''} Require Attention
          </div>
          <Link
            href="/dashboard"
            style={{ fontSize: 11, color: '#DC2626', fontWeight: 600, textDecoration: 'none' }}
          >
            Review Now →
          </Link>
        </div>
      )}
    </aside>
  );
}
