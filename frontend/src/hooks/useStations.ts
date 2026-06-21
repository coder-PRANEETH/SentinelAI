'use client';
import useSWR from 'swr';
import { Station } from '@/lib/api';
import { listStations, listStationReadiness, STATION_RESOURCE_CAPS } from '@/api/finalEndpointsApi';

async function fetcher(): Promise<Station[]> {
  const [resources, readiness] = await Promise.all([listStations(), listStationReadiness()]);
  const readinessByStation = new Map(readiness.map(r => [r.station, r]));

  // Simple string hash function for stable random coordinates
  const hashString = (str: string) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) hash = Math.imul(31, hash) + str.charCodeAt(i) | 0;
    return hash;
  };

  return resources.map(res => {
    const r = readinessByStation.get(res.station);
    
    // Generate a stable pseudo-random coordinate around Bengaluru center (12.9716, 77.5946)
    // using the station name's hash. Range: ~ ±0.15 degrees
    const hash = hashString(res.station);
    const latOffset = ((hash % 1000) / 1000 - 0.5) * 0.3;
    const lngOffset = (((hash / 1000 | 0) % 1000) / 1000 - 0.5) * 0.3;
    
    return {
      station_id: res.station,
      station_name: res.station,
      latitude: 12.9716 + latOffset,
      longitude: 77.5946 + lngOffset,
      readiness_score: r?.readiness_score ?? 0,
      available_officers: res.officers,
      available_vehicles: res.vehicles,
      available_tow_trucks: res.tow_trucks,
      available_barricades: res.barricades,
      active_incidents: r?.active_incidents ?? 0,
      total_officers: STATION_RESOURCE_CAPS.officers,
      total_vehicles: STATION_RESOURCE_CAPS.vehicles,
      total_tow_trucks: STATION_RESOURCE_CAPS.tow_trucks,
      total_barricades: STATION_RESOURCE_CAPS.barricades,
    };
  });
}

export function useStations(refreshInterval = 30000) {
  const { data, error, isLoading, mutate } = useSWR<Station[]>(
    '/stations',
    fetcher,
    { refreshInterval }
  );
  return { stations: data ?? [], error, isLoading, mutate };
}
