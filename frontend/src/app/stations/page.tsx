'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Search, Radio } from 'lucide-react';
import { PageHeading } from '@/components/layout/PageHeading';
import { ReadinessBar } from '@/components/shared/ReadinessBar';
import { LoadingState, ErrorState } from '@/components/shared/LoadingState';
import { useStations } from '@/hooks/useStations';

type FilterLevel = 'all' | 'high' | 'mid' | 'low';

export default function StationsPage({ hideHeading = false }: { hideHeading?: boolean } = {}) {
  const { stations, isLoading, error, mutate } = useStations(30000);
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterLevel>('all');

  const filtered = stations.filter(s => {
    const matchSearch = s.station_name.toLowerCase().includes(search.toLowerCase());
    const score = Number(s.readiness_score);
    const matchFilter =
      filter === 'all' ? true :
      filter === 'high' ? score > 70 :
      filter === 'mid'  ? score >= 40 && score <= 70 :
      score < 40;
    return matchSearch && matchFilter;
  });

  const FILTERS: { key: FilterLevel; label: string }[] = [
    { key: 'all',  label: 'All' },
    { key: 'high', label: 'High (>70)' },
    { key: 'mid',  label: 'Medium (40–70)' },
    { key: 'low',  label: 'Low (<40)' },
  ];

  return (
    <>
      {!hideHeading && (
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
              <Radio size={18} color="#111111" strokeWidth={2.5} />
            </span>
            Station Network
          </>
        } />
      )}
      <div className="flex-1 px-7 pb-7 overflow-auto">

          {/* ── Page heading ─────────────────────────────────────────────── */}
          <div style={{ marginBottom: '24px' }}>
            <h2 style={{
              fontSize: '26px', fontWeight: 800, color: 'var(--ink)',
              letterSpacing: '-0.03em',
            }}>
              Stations &amp; Resources
            </h2>
            <p className="section-sub" style={{ marginTop: '4px' }}>
              {filtered.length} of {stations.length} stations
            </p>
          </div>

          {/* ── Controls ─────────────────────────────────────────────────── */}
          <div style={{
            display: 'flex', gap: '10px', marginBottom: '20px',
            alignItems: 'center', flexWrap: 'wrap',
          }}>
            {/* Search */}
            <div style={{ position: 'relative', maxWidth: '280px', flex: '1 1 200px' }}>
              <Search size={14} style={{
                position: 'absolute', left: '12px', top: '50%',
                transform: 'translateY(-50%)', color: 'var(--muted)', pointerEvents: 'none',
              }} />
              <input
                type="text"
                className="form-input"
                style={{ paddingLeft: '34px', borderRadius: '9999px', height: '36px' }}
                placeholder="Search stations…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                id="station-search"
              />
            </div>

            {/* Filter pills */}
            <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '4px' }}>
              {FILTERS.map(({ key, label }) => (
                <button
                  key={key}
                  className={`tab-pill ${filter === key ? 'active' : ''}`}
                  onClick={() => setFilter(key)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* ── Table ────────────────────────────────────────────────────── */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {isLoading ? (
              <LoadingState message="Loading stations…" />
            ) : error ? (
              <ErrorState message="Failed to load stations." onRetry={mutate} />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Station Name</th>
                    <th style={{ minWidth: '180px' }}>Readiness</th>
                    <th>Officers</th>
                    <th>Vehicles</th>
                    <th>Tow Trucks</th>
                    <th>Barricades</th>
                    <th>Active Inc.</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(station => (
                    <tr
                      key={station.station_id}
                      onClick={() => router.push(`/resources?station=${station.station_id}`)}
                    >
                      <td style={{ fontWeight: 600 }}>{station.station_name}</td>
                      <td>
                        <ReadinessBar score={Number(station.readiness_score)} />
                      </td>
                      <td>
                        {station.available_officers}
                        {station.total_officers ? <span style={{ color: 'var(--muted)' }}> / {station.total_officers}</span> : ''}
                      </td>
                      <td>
                        {station.available_vehicles}
                        {station.total_vehicles ? <span style={{ color: 'var(--muted)' }}> / {station.total_vehicles}</span> : ''}
                      </td>
                      <td>
                        {station.available_tow_trucks}
                        {station.total_tow_trucks ? <span style={{ color: 'var(--muted)' }}> / {station.total_tow_trucks}</span> : ''}
                      </td>
                      <td>
                        {station.available_barricades}
                        {station.total_barricades ? <span style={{ color: 'var(--muted)' }}> / {station.total_barricades}</span> : ''}
                      </td>
                      <td>
                        <span style={{
                          fontSize: '12px', fontWeight: 700,
                          color: station.active_incidents > 3 ? 'var(--err)' : 'var(--ink)',
                        }}>
                          {station.active_incidents}
                        </span>
                      </td>
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
