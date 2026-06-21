'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Bell, ExternalLink, X } from 'lucide-react';
import { getSupabaseClient } from '@/lib/supabase';

type IncidentRow = {
  incident_id?: string;
  incident_type?: string | null;
  corridor?: string | null;
  location?: string | null;
  latitude?: number | null;
  longitude?: number | null;
};

const TOAST_LIFETIME_MS = 8000;

function IncidentToast({
  incident,
  onClose,
}: {
  incident: IncidentRow;
  onClose: () => void;
}) {
  return (
    <div
      style={{
        position: 'fixed',
        right: 20,
        bottom: 20,
        zIndex: 99999,
        width: 340,
        borderRadius: 16,
        padding: '14px 16px',
        background: '#111111',
        color: '#FFFFFF',
        boxShadow: '0 18px 40px rgba(0, 0, 0, 0.32)',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <Bell size={14} color="#CDFF50" />
          <div style={{ fontSize: 12, fontWeight: 800, color: '#CDFF50', textTransform: 'uppercase' }}>
            New Incident Reported
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close notification"
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
        <div style={{ fontSize: 12, color: '#D1D5DB', lineHeight: 1.45 }}>
          {incident.location || incident.corridor || incident.incident_id || 'Incident received'}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <span style={{ fontSize: 11, color: '#9CA3AF', fontFamily: 'monospace' }}>
          {incident.incident_id || 'pending-id'}
        </span>
        {incident.incident_id ? (
          <Link
            href="/report/success"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 12px',
              borderRadius: 9999,
              background: '#CDFF50',
              color: '#111111',
              textDecoration: 'none',
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            View Report <ExternalLink size={12} />
          </Link>
        ) : null}
      </div>
    </div>
  );
}

export function IncidentRealtimeSync() {
  const supabase = getSupabaseClient();
  const [toastIncident, setToastIncident] = useState<IncidentRow | null>(null);
  const toastTimerRef = useRef<number | null>(null);
  const lastIncidentIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!supabase) return;

    const showToast = (incident: IncidentRow) => {
      if (!incident.incident_id) return;
      if (lastIncidentIdRef.current === incident.incident_id) return;

      lastIncidentIdRef.current = incident.incident_id;
      setToastIncident(incident);

      if (toastTimerRef.current) {
        window.clearTimeout(toastTimerRef.current);
      }

      toastTimerRef.current = window.setTimeout(() => {
        setToastIncident(null);
      }, TOAST_LIFETIME_MS);
    };

    const channel = supabase
      .channel('public:incidents:insert')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'incidents' },
        payload => {
          const incident = (payload.new ?? {}) as IncidentRow;
          if (!incident.incident_id) return;

          showToast(incident);

          window.dispatchEvent(
            new CustomEvent('sentinel:new-incident', {
              detail: incident,
            })
          );
        }
      )
      .subscribe();

    return () => {
      if (toastTimerRef.current) {
        window.clearTimeout(toastTimerRef.current);
      }
      void supabase.removeChannel(channel);
    };
  }, [supabase]);

  if (!toastIncident) return null;

  return <IncidentToast incident={toastIncident} onClose={() => setToastIncident(null)} />;
}
