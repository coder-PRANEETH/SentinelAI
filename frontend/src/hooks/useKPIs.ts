'use client';
import useSWR from 'swr';
import { api, KPIData, getToken } from '@/lib/api';

const fetcher = () => api.analytics.kpis();

export function useKPIs(refreshInterval = 30000) {
  const token = getToken();
  const { data, error, isLoading, mutate } = useSWR<KPIData>(
    token ? '/analytics/kpis' : null,
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
