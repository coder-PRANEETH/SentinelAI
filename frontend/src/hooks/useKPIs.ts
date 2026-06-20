'use client';
import useSWR from 'swr';
import { api, KPIData } from '@/lib/api';

const fetcher = () => api.analytics.kpis();

export function useKPIs(refreshInterval = 30000) {
  const { data, error, isLoading, mutate } = useSWR<KPIData>(
    '/analytics/kpis',
    fetcher,
    { refreshInterval }
  );
  return {
    kpis: data,
    error,
    isLoading,
    mutate,
  };
}
