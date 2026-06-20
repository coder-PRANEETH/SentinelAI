'use client';
import { ReactNode } from 'react';

interface KPICardProps {
  label: string;
  value: string | number;
  subtext?: string;
  trend?: 'up' | 'down' | 'stable';
  icon?: ReactNode;
  accentBg?: boolean;  // lime-tinted highlight card (like the reference)
  isLoading?: boolean;
}

export function KPICard({
  label, value, subtext, trend, icon, accentBg = false, isLoading,
}: KPICardProps) {
  return (
    <div
      className="card"
      style={{
        minHeight: '120px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        background: accentBg ? 'var(--lime)' : 'var(--surface)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <span
          className="kpi-label"
          style={{ color: accentBg ? 'rgba(17,17,17,0.6)' : undefined }}
        >
          {label}
        </span>
        {icon && (
          <span style={{
            width: 32, height: 32, borderRadius: '9px',
            background: accentBg ? 'rgba(0,0,0,0.08)' : 'var(--bg)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: accentBg ? 'var(--ink)' : 'var(--muted)',
          }}>
            {icon}
          </span>
        )}
      </div>

      {/* Value */}
      {isLoading ? (
        <div className="skeleton" style={{ height: '36px', width: '55%', marginTop: '14px' }} />
      ) : (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '12px' }}>
          <span className="kpi-value">{value}</span>
          {trend === 'up'   && <span style={{ color: 'var(--ok)',   fontSize: '13px', fontWeight: 600 }}>↑</span>}
          {trend === 'down' && <span style={{ color: 'var(--err)',  fontSize: '13px', fontWeight: 600 }}>↓</span>}
          {trend === 'stable' && <span style={{ color: 'var(--muted)', fontSize: '13px' }}>→</span>}
        </div>
      )}

      {subtext && !isLoading && (
        <span style={{
          fontSize: '11px',
          color: accentBg ? 'rgba(17,17,17,0.5)' : 'var(--muted)',
          marginTop: '4px',
        }}>
          {subtext}
        </span>
      )}
    </div>
  );
}
