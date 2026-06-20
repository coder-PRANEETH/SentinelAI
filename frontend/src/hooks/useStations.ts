'use client';
import useSWR from 'swr';
import { Station } from '@/lib/api';
import { listStations, listStationReadiness, STATION_RESOURCE_CAPS } from '@/api/finalEndpointsApi';

async function fetcher(): Promise<Station[]> {
  const [resources, readiness] = await Promise.all([listStations(), listStationReadiness()]);
  const readinessByStation = new Map(readiness.map(r => [r.station, r]));

  return resources.map(res => {
    const r = readinessByStation.get(res.station);
    return {
      station_id: res.station,
      station_name: res.station,
      latitude: null,
      longitude: null,
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
