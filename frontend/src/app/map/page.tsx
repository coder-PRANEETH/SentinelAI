'use client';
import dynamic from 'next/dynamic';
import useSWR from 'swr';
import { api } from '@/lib/api';
import { useStations } from '@/hooks/useStations';
import { PageHeading } from '@/components/layout/PageHeading';
import { LoadingState } from '@/components/shared/LoadingState';
import { Map as MapIcon } from 'lucide-react';

const BengaluruMap = dynamic(
  () => import('@/components/map/BengaluruMap').then(m => m.BengaluruMap),
  { ssr: false, loading: () => <div className="card h-full flex items-center justify-center"><LoadingState message="Loading map…" /></div> }
);

function useActiveIncidents() {
  return useSWR('/incidents/active', () => api.incidents.active(), { refreshInterval: 15000 });
}

export default function MapPage() {
  const { stations } = useStations(30000);
  const { data: activeIncidents } = useActiveIncidents();

  return (
    <div className="flex flex-col h-full">
      <PageHeading title={
        <>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              backgroundColor: '#CDFF50',
              flexShrink: 0,
            }}
          >
            <MapIcon size={18} color="#111111" strokeWidth={2.5} />
          </span>
          Live Map View
        </>
      } />

      <div className="flex-1 px-7 pb-7">
        <div style={{ position: 'relative', height: '100%' }}>
          <div className="card" style={{ padding: 0, position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <BengaluruMap
              stations={stations}
              incidents={activeIncidents || []}
              height="100%"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
