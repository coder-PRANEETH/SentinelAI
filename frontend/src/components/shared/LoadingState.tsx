'use client';
import { Loader2, AlertCircle } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
}
interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}
interface EmptyStateProps {
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function LoadingState({ message = 'Loading…', size = 'md' }: LoadingStateProps) {
  const iconSize = size === 'sm' ? 14 : size === 'lg' ? 24 : 18;
  const textSize = size === 'sm' ? '11px' : size === 'lg' ? '15px' : '13px';
  const padding  = size === 'sm' ? '12px' : size === 'lg' ? '48px' : '32px';
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: '10px', padding,
      color: 'var(--muted)',
    }}>
      <Loader2 size={iconSize} className="animate-spin" style={{ color: 'var(--muted)' }} />
      <span style={{ fontSize: textSize }}>{message}</span>
    </div>
  );
}

export function ErrorState({ message = 'Something went wrong.', onRetry }: ErrorStateProps) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: '12px', padding: '32px',
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: '50%',
        background: 'rgba(229,62,62,0.08)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <AlertCircle size={18} style={{ color: 'var(--err)' }} />
      </div>
      <span style={{ fontSize: '13px', color: 'var(--muted)', textAlign: 'center' }}>
        {message}
      </span>
      {onRetry && (
        <button className="btn-secondary" onClick={onRetry}
          style={{ fontSize: '12px', padding: '6px 16px' }}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ message = 'No data found.', actionLabel, onAction }: EmptyStateProps) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: '12px', padding: '48px 32px',
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: '50%',
        background: 'var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '20px', color: 'var(--muted)',
      }}>
        ○
      </div>
      <span style={{ fontSize: '13px', color: 'var(--muted)', textAlign: 'center' }}>
        {message}
      </span>
      {actionLabel && onAction && (
        <button className="btn-accent" onClick={onAction}
          style={{ fontSize: '12px', padding: '7px 18px' }}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}
