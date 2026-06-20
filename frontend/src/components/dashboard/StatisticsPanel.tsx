'use client';

import { BarChart2 } from 'lucide-react';
import { CapsuleBarChart } from '@/components/charts/CapsuleBarChart';

interface TrendData {
  date: string;
  count: number;
}

export function StatisticsPanel({ data }: { data: TrendData[] }) {
  // Transform data for CapsuleBarChart
  // We need values between 0 and 1. We'll find max to normalize.
  const maxVal = Math.max(...(data.map(d => d.count) || [0]), 10);

  const chartData = data.map((d, i) => ({
    label: d.date,
    value: d.count / maxVal,
    highlighted: i === data.length - 1, // highlight the last one
  }));

  return (
    <div style={{ padding: '4px' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '20px' }}>
        <div className="flex items-center gap-2">
          <BarChart2 size={16} className="text-text-2" />
          <span className="text-base font-semibold text-text-1">Incident Trends</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-xs text-text-1 font-medium">
              <span className="w-2 h-2 rounded-full inline-block" style={{ background: '#111111' }} />
              Incidents
            </span>
            <span className="flex items-center gap-1.5 text-xs text-text-2">
              <span className="w-2 h-2 rounded-full inline-block" style={{ background: '#CDFF50' }} />
              Avg Baseline
            </span>
          </div>
          <select className="text-sm border border-border rounded-pill px-3 py-1.5 bg-surface text-text-1 cursor-pointer">
            <option>Last 7 days</option>
            <option>Last 30 days</option>
          </select>
        </div>
      </div>

      <CapsuleBarChart data={chartData} height={260} />
    </div>
  );
}
