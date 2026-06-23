'use client';

import { usePathname, useRouter } from 'next/navigation';
import { AlertTriangle, Clock, CheckCircle, Radio, ArrowUpRight, Activity } from 'lucide-react';
import Link from 'next/link';
import useSWRImmutable from 'swr/immutable';
import { api, Incident } from '@/lib/api';

const PRIORITY_COLORS: Record<string, { bg: string; text: string; iconBg: string; iconText: string }> = {
  P1: { bg: '#EF4444', text: '#FFFFFF', iconBg: 'rgba(239, 68, 68, 0.15)', iconText: '#EF4444' },
  P2: { bg: '#F59E0B', text: '#FFFFFF', iconBg: 'rgba(245, 158, 11, 0.15)', iconText: '#F59E0B' },
  P3: { bg: '#EAB308', text: '#111111', iconBg: 'rgba(234, 179, 8, 0.15)', iconText: '#EAB308' },
  P4: { bg: '#3B82F6', text: '#FFFFFF', iconBg: 'rgba(59, 130, 246, 0.15)', iconText: '#3B82F6' },
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  REPORTED: <AlertTriangle size={12} style={{ color: '#F59E0B' }} />,
  UNDER_ASSESSMENT: <Clock size={12} style={{ color: '#A0A0A0' }} />,
  RESOURCES_ASSIGNED: <Radio size={12} style={{ color: '#3B82F6' }} />,
  IN_PROGRESS: <Activity size={12} style={{ color: '#10B981' }} />,
  RESOLVED: <CheckCircle size={12} style={{ color: '#10B981' }} />,
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
  const p1Incidents = (incidents || []).filter(i => i.predicted_priority === 'P1' || i.predicted_priority === 'High');
  const p1Count = p1Incidents.length;
  const firstP1 = p1Incidents.length > 0 ? p1Incidents[0] : null;

  return (
    <aside className="right-panel">

      {/* Quick stats strip */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
        <Link href="/incidents/new" style={{ textDecoration: 'none' }}>
          <div className="right-panel-grid-item">
            <div className="right-panel-grid-icon">
              <AlertTriangle size={15} style={{ color: '#FFFFFF' }} />
            </div>
            <div style={{ lineHeight: 1.2 }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#FFFFFF' }}>{kpis?.active_incidents ?? '—'}</div>
              <span className="right-panel-grid-label" style={{ fontSize: 11, color: '#A0A0A0', fontWeight: 500 }}>Active</span>
            </div>
          </div>
        </Link>

        <Link href="/stations" style={{ textDecoration: 'none' }}>
          <div className="right-panel-grid-item">
            <div className="right-panel-grid-icon">
              <Radio size={15} style={{ color: '#FFFFFF' }} />
            </div>
            <div style={{ lineHeight: 1.2 }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#FFFFFF' }}>{kpis?.resources_deployed ?? '—'}</div>
              <span className="right-panel-grid-label" style={{ fontSize: 11, color: '#A0A0A0', fontWeight: 500 }}>Deployed</span>
            </div>
          </div>
        </Link>

        <div className="right-panel-grid-item" style={{ cursor: 'default' }}>
          <div className="right-panel-grid-icon">
            <Clock size={15} style={{ color: '#FFFFFF' }} />
          </div>
          <div style={{ lineHeight: 1.2 }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#FFFFFF' }}>
              {kpis?.avg_resolution_minutes != null ? `${kpis.avg_resolution_minutes}m` : '—'}
            </div>
            <span className="right-panel-grid-label" style={{ fontSize: 11, color: '#A0A0A0', fontWeight: 500 }}>Avg Resolve</span>
          </div>
        </div>

        <div className="right-panel-grid-item" style={{ borderColor: p1Count > 0 ? '#EF4444' : '#2A2A2A', cursor: 'default' }}>
          <div className="right-panel-grid-icon" style={{ background: p1Count > 0 ? 'rgba(239, 68, 68, 0.15)' : '#2A2A2A' }}>
            <AlertTriangle size={15} style={{ color: p1Count > 0 ? '#EF4444' : '#A0A0A0' }} />
          </div>
          <div style={{ lineHeight: 1.2 }}>
            <div style={{ fontSize: 24, fontWeight: 900, color: p1Count > 0 ? '#EF4444' : '#FFFFFF' }}>{p1Count}</div>
            <span className="right-panel-grid-label" style={{ fontSize: 11, color: p1Count > 0 ? '#EF4444' : '#A0A0A0', fontWeight: 700 }}>P1 Critical</span>
          </div>
        </div>
      </div>

      {/* Live Activity Feed */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, padding: '0 4px' }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Live Activity
        </div>
        <Link href="/dashboard" style={{ fontSize: 11, color: '#9CA3AF', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 3 }}>
          All <ArrowUpRight size={10} />
        </Link>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
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
            const c = PRIORITY_COLORS[priority] ?? { bg: '#2A2A2A', text: '#FFFFFF', iconBg: '#2A2A2A', iconText: '#A0A0A0' };

            return (
              <Link
                key={inc.incident_id}
                href={`/incidents/${encodeURIComponent(inc.incident_id)}`}
                className="right-panel-link"
                style={{ flexDirection: 'column', padding: '14px 16px', gap: 8, alignItems: 'stretch', cursor: 'pointer', textDecoration: 'none' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className="right-panel-link-icon" style={{ background: c.iconBg, width: 24, height: 24, borderRadius: 6 }}>
                      <Activity size={12} style={{ color: c.iconText }} />
                    </div>
                    <span style={{
                      padding: '2px 8px', borderRadius: 9999,
                      fontSize: 10, fontWeight: 700,
                      background: c.bg, color: c.text,
                    }}>
                      {priority}
                    </span>
                  </div>
                  <span style={{ fontSize: 11, color: '#A0A0A0', fontWeight: 500 }}>{timeAgo(inc.created_at)}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#FFFFFF', lineHeight: 1.3 }}>
                    {inc.incident_type || 'Unknown'}
                  </div>
                  <div style={{ fontSize: 12, color: '#A0A0A0', fontWeight: 500 }}>
                    {inc.corridor || inc.location || inc.incident_id}
                  </div>
                </div>
              </Link>
            );
          })
        )}
      </div>

      {/* Pending actions */}
      {p1Count > 0 && (
        <div style={{
          padding: '10px 14px', background: 'rgba(239, 68, 68, 0.15)', borderRadius: 12,
          border: '1px solid rgba(239, 68, 68, 0.3)',
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#EF4444', marginBottom: 4 }}>
            ⚠ {p1Count} Critical Incident{p1Count > 1 ? 's' : ''} Require Attention
          </div>
          <Link
            href={firstP1 ? `/incidents/${encodeURIComponent(firstP1.incident_id)}` : '/dashboard'}
            style={{ fontSize: 11, color: '#EF4444', fontWeight: 600, textDecoration: 'none' }}
          >
            Review Now →
          </Link>
        </div>
      )}
    </aside>
  );
}
