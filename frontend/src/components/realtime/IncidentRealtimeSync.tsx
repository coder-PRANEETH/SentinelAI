'use client';

import { useEffect, useRef, useState } from 'react';
import { Bell, X, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { useSWRConfig } from 'swr';
import { api, Incident, IncidentDetail } from '@/lib/api';
import { getSupabaseClient } from '@/lib/supabase';

const TOAST_DURATION_MS = 8000;

type RealtimeIncidentRow = Partial<IncidentDetail> & {
  incident_id?: string;
};

function upsertIncident(list: Incident[] = [], incident: Incident): Incident[] {
  const next = list.filter(item => item.incident_id !== incident.incident_id);
  return [incident, ...next];
}

function normalizeIncident(row: RealtimeIncidentRow, detail?: IncidentDetail | null): Incident {
  const source = detail ?? (row as IncidentDetail);
  return {
    incident_id: row.incident_id ?? source.incident_id ?? '',
    incident_type: row.incident_type ?? source.incident_type ?? 'Unknown Incident',
    status: row.status ?? source.status ?? 'REPORTED',
    latitude: row.latitude ?? source.latitude ?? null,
    longitude: row.longitude ?? source.longitude ?? null,
    predicted_priority: row.predicted_priority ?? source.predicted_priority,
    corridor: row.corridor ?? source.corridor,
    location: row.location ?? source.location ?? null,
    event_cause: row.event_cause ?? source.event_cause ?? null,
    vehicle_type: row.vehicle_type ?? source.vehicle_type ?? null,
    reported_at: row.reported_at ?? source.reported_at,
    created_at: row.created_at ?? source.created_at,
  };
}

function IncidentToast({
  incident,
  onClose,
}: {
  incident: Incident;
  onClose: () => void;
}) {
  return (
    <div
      style={{
        position: 'fixed',
        right: 24,
        bottom: 24,
        zIndex: 99999,
        width: 340,
        borderRadius: 14,
        background: '#111111',
        color: '#FFFFFF',
        boxShadow: '0 16px 40px rgba(0, 0, 0, 0.28)',
        padding: '14px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <Bell size={14} color="#CDFF50" />
          <div style={{ fontSize: 12, fontWeight: 800, color: '#CDFF50', textTransform: 'uppercase', letterSpacing: 0 }}>
            New Incident Reported
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close incident notification"
          style={{
            border: 'none',
            background: 'transparent',
            color: '#9CA3AF',
            cursor: 'pointer',
            padding: 0,
            display: 'inline-flex',
          }}
        >
          <X size={14} />
        </button>
      </div>

      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 15, fontWeight: 700, lineHeight: 1.35, marginBottom: 4 }}>
          {incident.incident_type || 'Unknown Incident'}
        </div>
        <div style={{ fontSize: 12, color: '#D1D5DB', lineHeight: 1.4 }}>
          {incident.location || incident.corridor || incident.incident_id}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <span style={{ fontSize: 11, color: '#9CA3AF', fontFamily: 'monospace' }}>
          {incident.incident_id}
        </span>
        <Link
          href={`/incidents/${incident.incident_id}`}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            fontWeight: 600,
            color: '#111111',
            background: '#CDFF50',
            borderRadius: 9999,
            padding: '8px 12px',
            textDecoration: 'none',
          }}
        >
          View Incident <ExternalLink size={12} />
        </Link>
      </div>
    </div>
  );
}

export function IncidentRealtimeSync() {
  const supabase = getSupabaseClient();
  const { mutate } = useSWRConfig();
  const [toastIncident, setToastIncident] = useState<Incident | null>(null);
  const toastTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!supabase) return;

    const showToast = (incident: Incident) => {
      setToastIncident(incident);
      if (toastTimerRef.current) {
        window.clearTimeout(toastTimerRef.current);
      }
      toastTimerRef.current = window.setTimeout(() => {
        setToastIncident(null);
      }, TOAST_DURATION_MS);
    };

    const refreshDerivedData = () => {
      void mutate('/analytics/kpis');
      void mutate('/stations');
      void mutate('/station-readiness');
      void mutate('/analytics/trends');
      void mutate('/analytics/histogram');
      void mutate('/analytics/corridors');
    };

    const channel = supabase
      .channel('public:incidents:insert')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'incidents' },
        async payload => {
          const row = (payload.new ?? {}) as RealtimeIncidentRow;
          const incidentId = row.incident_id;

          if (!incidentId) return;

          const immediateIncident = normalizeIncident(row);

          mutate('/incidents/active', (current: Incident[] | undefined) => {
            return upsertIncident(current ?? [], immediateIncident);
          }, false);

          mutate('/incidents/heatmap', (current: Incident[] | undefined) => {
            return upsertIncident(current ?? [], immediateIncident);
          }, false);

          showToast(immediateIncident);
          refreshDerivedData();

          try {
            const detail = await api.incidents.get(incidentId);
            const normalized = normalizeIncident(row, detail);

            mutate('/incidents/active', (current: Incident[] | undefined) => {
              return upsertIncident(current ?? [], normalized);
            }, false);

            mutate('/incidents/heatmap', (current: Incident[] | undefined) => {
              return upsertIncident(current ?? [], normalized);
            }, false);

            setToastIncident(prev => (prev?.incident_id === normalized.incident_id ? normalized : prev));
          } catch {
            // Keep the realtime row even if the detail fetch races or momentarily fails.
          }
        }
      )
      .subscribe();

    return () => {
      if (toastTimerRef.current) {
        window.clearTimeout(toastTimerRef.current);
      }
      void supabase.removeChannel(channel);
    };
  }, [mutate, supabase]);

  if (!toastIncident) return null;

  return <IncidentToast incident={toastIncident} onClose={() => setToastIncident(null)} />;
}
