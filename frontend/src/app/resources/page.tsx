'use client';
import { useState, Suspense } from 'react';
import useSWR from 'swr';
import { PageHeading } from '@/components/layout/PageHeading';
import { LoadingState, ErrorState, EmptyState } from '@/components/shared/LoadingState';
import { Station } from '@/lib/api';
import { useStations } from '@/hooks/useStations';
import {
  getStation, getStationReadiness, allocateResources, releaseResources,
  STATION_RESOURCE_CAPS, FinalApiError,
} from '@/api/finalEndpointsApi';
import { useSearchParams } from 'next/navigation';
import { ArrowUpCircle, ArrowDownCircle, Loader2, Package } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Skeleton } from '@/components/shared/Skeleton';

/**
 * Resource Command Center.
 * - Station selector dropdown.
 * - Allocate / Release actions per resource type (final_endpoints has no
 *   route to change a station's total caps, so inventory limits are read-only).
 */
function ResourcesContent({ hideHeading = false }: { hideHeading?: boolean } = {}) {
  const params = useSearchParams();
  const defaultStation = params.get('station') ?? '';

  const { stations } = useStations(30000);
  const [selectedStation, setSelectedStation] = useState(defaultStation);

  const { data: station, isLoading, error, mutate } = useSWR<Station>(
    selectedStation ? `/stations/${selectedStation}` : null,
    async () => {
      const [resources, readiness] = await Promise.all([
        getStation(selectedStation),
        getStationReadiness(selectedStation),
      ]);
      const r = Array.isArray(readiness) ? undefined : readiness;
      return {
        station_id: resources.station,
        station_name: resources.station,
        latitude: null,
        longitude: null,
        readiness_score: r?.readiness_score ?? 0,
        available_officers: resources.officers,
        available_vehicles: resources.vehicles,
        available_tow_trucks: resources.tow_trucks,
        available_barricades: resources.barricades,
        active_incidents: r?.active_incidents ?? 0,
        total_officers: STATION_RESOURCE_CAPS.officers,
        total_vehicles: STATION_RESOURCE_CAPS.vehicles,
        total_tow_trucks: STATION_RESOURCE_CAPS.tow_trucks,
        total_barricades: STATION_RESOURCE_CAPS.barricades,
      };
    }
  );

  const resourceRows = station ? [
    { type: 'officers', label: 'Officers', total: station.total_officers ?? 0, available: station.available_officers },
    { type: 'vehicles', label: 'Patrol Vehicles', total: station.total_vehicles ?? 0, available: station.available_vehicles },
    { type: 'tow_trucks', label: 'Tow Trucks', total: station.total_tow_trucks ?? 0, available: station.available_tow_trucks },
    { type: 'barricades', label: 'Barricades', total: station.total_barricades ?? 0, available: station.available_barricades },
  ] : [];

  const [actionQty, setActionQty] = useState<Record<string, string>>({});
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');

  const getQty = (type: string) => {
    const n = parseInt(actionQty[type] ?? '1', 10);
    return isNaN(n) || n <= 0 ? null : n;
  };

  const runAction = async (type: string, label: string, kind: 'allocate' | 'release') => {
    const qty = getQty(type);
    if (qty == null) { setActionError('Enter a valid quantity.'); return; }

    setActionLoading(`${type}-${kind}`);
    setActionError('');
    setActionSuccess('');
    try {
      if (kind === 'allocate') {
        await allocateResources(selectedStation, { [type]: qty });
        setActionSuccess(`Allocated ${qty} ${label.toLowerCase()} from ${station?.station_name}.`);
      } else {
        await releaseResources(selectedStation, { [type]: qty });
        setActionSuccess(`Released ${qty} ${label.toLowerCase()} back to ${station?.station_name}.`);
      }
      mutate();
    } catch (e) {
      setActionError((e as FinalApiError).message || `Failed to ${kind} resources.`);
    } finally {
      setActionLoading(null);
    }
  };

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
              <Package size={18} color="#111111" strokeWidth={2.5} />
            </span>
            Resource Command Center
          </>
        } />
      )}
      <motion.div 
        initial="hidden" animate="visible" 
        variants={{ visible: { transition: { staggerChildren: 0.1 } } }}
        className="flex-1 px-4 md:px-7 pb-7 overflow-auto"
      >
          {/* Station selector */}
          <motion.div variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }} style={{ marginBottom: '20px', maxWidth: '400px' }}>
            <div className="form-group">
              <label className="form-label">Select Station</label>
              <select
                id="station-select"
                className="form-input"
                style={{ borderRadius: '9999px', height: '38px', padding: '0 14px' }}
                value={selectedStation}
                onChange={e => { setSelectedStation(e.target.value); setActionError(''); setActionSuccess(''); }}
              >
                <option value="">Choose a station…</option>
                {stations.map(s => (
                  <option key={s.station_id} value={s.station_id}>{s.station_name}</option>
                ))}
              </select>
            </div>
          </motion.div>

          {!selectedStation && (
            <motion.div variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }} style={{ marginTop: '48px' }}>
              <EmptyState message="Select a station from the dropdown above to view and manage its inventory." />
            </motion.div>
          )}

          {selectedStation && isLoading && (
            <motion.div variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }} className="flex flex-col gap-4 p-4 card max-w-[900px]">
              <Skeleton height={40} />
              <Skeleton height={40} />
              <Skeleton height={40} />
            </motion.div>
          )}
          {selectedStation && error && <ErrorState message="Failed to load station." onRetry={mutate} />}

          {station && (
            <motion.div 
              variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }}
              className="card" style={{ padding: 0, overflow: 'hidden', maxWidth: '900px' }}
            >
              <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ fontSize: '14px', fontWeight: 700 }}>{station.station_name}</h2>
                <span style={{ fontSize: '12px', color: 'var(--muted)' }}>
                  Readiness: <strong>{Math.round(Number(station.readiness_score))}</strong>
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="data-table min-w-[600px] w-full">
                  <thead>
                  <tr>
                    <th>Resource Type</th>
                    <th>Total</th>
                    <th>Available</th>
                    <th>Deployed</th>
                    <th style={{ minWidth: '220px' }}>Action</th>
                  </tr>
                </thead>
                <motion.tbody initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.05 } } }}>
                  {resourceRows.map(row => {
                    const deployed = row.total - row.available;
                    const allocating = actionLoading === `${row.type}-allocate`;
                    const releasing = actionLoading === `${row.type}-release`;
                    return (
                      <motion.tr variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 } }} key={row.type} className="hover:bg-gray-50 transition-colors">
                        <td style={{ fontWeight: 500 }}>{row.label}</td>
                        <td>{row.total}</td>
                        <td style={{ color: 'var(--muted)' }}>{row.available}</td>
                        <td style={{ color: deployed > 0 ? 'var(--warn)' : 'var(--muted)' }}>
                          {deployed}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <input
                              type="number"
                              min={1}
                              value={actionQty[row.type] ?? '1'}
                              onChange={e => setActionQty(prev => ({ ...prev, [row.type]: e.target.value }))}
                              className="form-input transition-all focus:ring-2 focus:ring-gray-300"
                              style={{ width: '56px', padding: '6px 8px', borderRadius: '8px', fontSize: '13px', height: 'auto', outline: 'none' }}
                            />
                            <button
                              onClick={() => runAction(row.type, row.label, 'allocate')}
                              disabled={allocating || releasing}
                              title="Allocate (deduct from available)"
                              className="hover:scale-[1.02] active:scale-95 transition-all focus:ring-2 focus:ring-gray-300 focus:outline-none"
                              style={{ padding: '6px 10px', border: '1px solid var(--color-border)', borderRadius: '9999px', background: '#FFFFFF', cursor: 'pointer', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 600, color: '#111111' }}
                            >
                              {allocating ? <Loader2 size={12} className="animate-spin" /> : <ArrowUpCircle size={12} />} Allocate
                            </button>
                            <button
                              onClick={() => runAction(row.type, row.label, 'release')}
                              disabled={allocating || releasing}
                              title="Release (return to available)"
                              className="hover:scale-[1.02] active:scale-95 transition-all focus:ring-2 focus:ring-gray-300 focus:outline-none"
                              style={{ padding: '6px 10px', border: '1px solid var(--color-border)', borderRadius: '9999px', background: '#FFFFFF', cursor: 'pointer', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 600, color: '#111111' }}
                            >
                              {releasing ? <Loader2 size={12} className="animate-spin" /> : <ArrowDownCircle size={12} />} Release
                            </button>
                          </div>
                        </td>
                      </motion.tr>
                    );
                  })}
                </motion.tbody>
              </table>
              </div>

              <AnimatePresence>
                {actionError && (
                  <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} style={{ padding: '8px 20px', fontSize: '12px', color: 'var(--p1)' }}>{actionError}</motion.div>
                )}
                {actionSuccess && (
                  <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} style={{ padding: '8px 20px', fontSize: '12px', color: 'var(--ok)' }}>{actionSuccess}</motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
      </motion.div>
    </>
  );
}

export default function ResourcesPage({ hideHeading = false }: { hideHeading?: boolean } = {}) {
  return (
    <Suspense fallback={<div className="flex flex-col gap-4"><Skeleton height={60} /><Skeleton height={60} /><Skeleton height={60} /></div>}>
      <ResourcesContent hideHeading={hideHeading} />
    </Suspense>
  );
}
