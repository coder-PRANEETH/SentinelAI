'use client';
import { PredictResponse } from '@/lib/api';
import { ConfidenceArc } from '@/components/shared/ConfidenceArc';
import { ExplainabilityList } from '@/components/shared/ExplainabilityList';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { LoadingState } from '@/components/shared/LoadingState';
import { AlertTriangle, ArrowRight, User, Car, Truck, Construction } from 'lucide-react';
import { useRouter } from 'next/navigation';

/**
 * CopilotPanel — AI Incident Copilot.
 * Shown as right column on incident submission page.
 * All colors use design tokens. No gradients. No glow.
 */

interface CopilotPanelProps {
  prediction: PredictResponse | null;
  isLoading?: boolean;
  incidentId?: string;
}

const PRIORITY_TINTS: Record<string, string> = {
  P1: 'rgba(229,62,62,0.06)',
  P2: 'rgba(246,173,85,0.08)',
  P3: 'rgba(236,201,75,0.08)',
  P4: 'rgba(66,153,225,0.06)',
};

function ClosureIndicator({ prob, rec }: { prob: number; rec: string }) {
  const cls = prob < 30 ? 'closure-low' : prob < 60 ? 'closure-mid' : 'closure-high';
  const label = prob < 30 ? 'Unlikely' : prob < 60 ? 'Monitor' : 'Likely';
  return (
    <div style={{ textAlign: 'center' }}>
      <div className={cls} style={{ fontSize: '18px', fontWeight: 700 }}>{prob.toFixed(0)}%</div>
      <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: '2px' }}>{label}</div>
    </div>
  );
}

function ResourceChip({ icon, count, label }: { icon: React.ReactNode; count: number; label: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px', padding: '10px', background: 'var(--bg)', borderRadius: '10px', minWidth: '60px' }}>
      {icon}
      <span style={{ fontSize: '16px', fontWeight: 700, color: 'var(--ink)' }}>{count}</span>
      <span style={{ fontSize: '10px', color: 'var(--muted)', textAlign: 'center', lineHeight: 1.2 }}>{label}</span>
    </div>
  );
}

export function CopilotPanel({ prediction, isLoading, incidentId }: CopilotPanelProps) {
  const router = useRouter();

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
  const priority = p.predicted_priority as 'P1' | 'P2' | 'P3' | 'P4';
  const resources = prediction.recommended_resources;
  const historical = prediction.historical_context;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header */}
      <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        AI Incident Copilot
      </div>

      {/* Low confidence warning */}
      {historical?.low_confidence_warning && (
        <div className="warning-banner">
          <AlertTriangle size={14} style={{ color: 'var(--warn)', flexShrink: 0, marginTop: '1px' }} />
          <span>Limited historical precedent for this incident type. AI recommendations may be less reliable.</span>
        </div>
      )}

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
          <StatusBadge priority={priority} />
          <ConfidenceArc value={p.priority_confidence} size={70} />
          <span style={{ fontSize: '10px', color: 'var(--muted)' }}>{p.priority_confidence.toFixed(0)}% conf.</span>
        </div>

        {/* Resolution card */}
        <div className="card" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Resolution</span>
          <span style={{ fontSize: '20px', fontWeight: 700 }}>{p.predicted_resolution_minutes} min</span>
          <span style={{ fontSize: '10px', color: 'var(--muted)' }}>({p.resolution_range.low}–{p.resolution_range.high})</span>
        </div>

        {/* Road closure card */}
        <div className="card" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Road Closure</span>
          <ClosureIndicator prob={p.road_closure_probability} rec={p.road_closure_recommendation} />
          <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Rec: {p.road_closure_recommendation}</span>
        </div>
      </div>

      {/* Historical baseline */}
      {historical && (
        <div className="card" style={{ padding: '12px 16px' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
            Historical Baseline
          </div>
          <div style={{ fontSize: '12px', color: 'var(--ink)', lineHeight: 1.7 }}>
            Similar cases: <strong>{historical.total_similar}</strong> found &nbsp;·&nbsp;
            Avg {historical.average_resolution_time ?? '?'} min &nbsp;·&nbsp;
            Common priority: <strong>{historical.historical_priority ?? 'Unknown'}</strong>
          </div>
        </div>
      )}

      {/* Reasoning */}
      <ExplainabilityList reasons={[...p.priority_reasons, ...p.closure_reasons]} />

      {/* Similar cases */}
      {historical && historical.similar_cases.length > 0 && (
        <div className="card" style={{ padding: '12px 16px' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px' }}>
            Similar Cases
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {historical.similar_cases.slice(0, 3).map((c, i) => (
              <div key={i} style={{ padding: '8px 10px', background: 'var(--bg)', borderRadius: '8px', fontSize: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                  <span style={{ fontWeight: 600 }}>{c.corridor || 'Unknown corridor'}</span>
                  <span style={{ color: 'var(--muted)' }}>{c.resolution_mins ? `${c.resolution_mins} min` : '—'}</span>
                </div>
                <div style={{ color: 'var(--muted)' }}>{c.event_cause} · Priority {c.priority} · {Math.round(c.similarity_score * 100)}% match</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommended resources */}
      <div className="card" style={{ padding: '12px 16px' }}>
        <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px' }}>
          Recommended Resources
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <ResourceChip icon={<User size={16} style={{ color: 'var(--muted)' }} />} count={resources.officers} label="Officers" />
          <ResourceChip icon={<Car size={16} style={{ color: 'var(--muted)' }} />} count={resources.vehicles} label="Vehicles" />
          <ResourceChip icon={<Truck size={16} style={{ color: 'var(--muted)' }} />} count={resources.tow_trucks} label="Tow Trucks" />
          <ResourceChip icon={<Construction size={16} style={{ color: 'var(--muted)' }} />} count={resources.barricades} label="Barricades" />
        </div>
      </div>

      {/* Dispatch CTA */}
      {incidentId && (
        <button
          id="proceed-to-dispatch"
          className="btn-accent"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={() => router.push(`/incidents/${incidentId}/dispatch`)}
        >
          Proceed to Dispatch <ArrowRight size={14} />
        </button>
      )}
    </div>
  );
}
