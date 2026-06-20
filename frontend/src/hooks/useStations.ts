'use client';
import useSWR from 'swr';
import { api, Station } from '@/lib/api';

const fetcher = () => api.stations.list();

export function useStations(refreshInterval = 30000) {
  const { data, error, isLoading, mutate } = useSWR<Station[]>(
    '/stations',
    fetcher,
    { refreshInterval }
  );
  return { stations: data ?? [], error, isLoading, mutate };
}
