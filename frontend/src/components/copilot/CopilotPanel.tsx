'use client';
import { PredictResponse } from '@/api/finalEndpointsApi';
import { ConfidenceArc } from '@/components/shared/ConfidenceArc';
import { LoadingState } from '@/components/shared/LoadingState';

/**
 * CopilotPanel — AI Incident Copilot.
 * Shown as right column on incident submission page.
 * All colors use design tokens. No gradients. No glow.
 */

interface CopilotPanelProps {
  prediction: PredictResponse | null;
  isLoading?: boolean;
}

const PRIORITY_TINTS: Record<string, string> = {
  high: 'rgba(229,62,62,0.06)',
  low: 'rgba(66,153,225,0.06)',
};

function PriorityBadge({ priority }: { priority: 'high' | 'low' }) {
  const colors = priority === 'high'
    ? { bg: '#FEE2E2', text: '#DC2626' }
    : { bg: '#DBEAFE', text: '#1D4ED8' };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', padding: '3px 10px',
      borderRadius: '9999px', fontSize: '11px', fontWeight: 700,
      backgroundColor: colors.bg, color: colors.text, letterSpacing: '0.03em',
    }}>
      {priority.toUpperCase()}
    </span>
  );
}

function ClosureIndicator({ prob, required }: { prob: number; required: boolean }) {
  const cls = prob < 30 ? 'closure-low' : prob < 60 ? 'closure-mid' : 'closure-high';
  const label = prob < 30 ? 'Unlikely' : prob < 60 ? 'Monitor' : 'Likely';
  return (
    <div style={{ textAlign: 'center' }}>
      <div className={cls} style={{ fontSize: '18px', fontWeight: 700 }}>{prob.toFixed(0)}%</div>
      <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: '2px' }}>{label}</div>
      <div style={{ fontSize: '10px', color: 'var(--muted)' }}>Rec: {required ? 'Yes' : 'No'}</div>
    </div>
  );
}

export function CopilotPanel({ prediction, isLoading }: CopilotPanelProps) {
  if (isLoading) {
    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          AI Incident Copilot
        </div>
        {/* Skeleton cards */}
        {[1, 2, 3].map(i => (
          <div key={i} className="skeleton" style={{ height: '80px', borderRadius: '12px' }} />
        ))}
      </div>
    );
  }

  if (!prediction) {
    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          AI Incident Copilot
        </div>
        <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--muted)', fontSize: '12px' }}>
          Submit an incident to see AI predictions.
        </div>
      </div>
    );
  }

  const p = prediction.predictions;
  const priority = p.priority;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header */}
      <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        AI Incident Copilot
      </div>

      {/* Priority metrics row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
        {/* Priority card */}
        <div
          className="card"
          style={{
            padding: '14px',
            background: PRIORITY_TINTS[priority] ?? 'var(--surface)',
            display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center',
          }}
        >
          <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Priority</span>
          <PriorityBadge priority={priority} />
          <ConfidenceArc value={p.priority_confidence} size={70} />
          <span style={{ fontSize: '10px', color: 'var(--muted)' }}>{p.priority_confidence.toFixed(0)}% conf.</span>
        </div>

        {/* Resolution card */}
        <div className="card" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Resolution</span>
          <span style={{ fontSize: '20px', fontWeight: 700 }}>{p.expected_resolution_minutes.toFixed(0)} min</span>
        </div>

        {/* Road closure card */}
        <div className="card" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Road Closure</span>
          <ClosureIndicator prob={p.road_closure_probability} required={p.road_closure_required} />
        </div>
      </div>
    </div>
  );
}
