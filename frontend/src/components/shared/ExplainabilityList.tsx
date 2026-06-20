'use client';
import { useState } from 'react';
import { Check } from 'lucide-react';

/**
 * ExplainabilityList — collapsible bullet list of AI reasoning strings.
 * "Show reasoning" toggle. Each reason prefixed with checkmark icon.
 */

interface ExplainabilityListProps {
  reasons: string[];
  label?: string;
}

export function ExplainabilityList({ reasons, label = 'Reasoning' }: ExplainabilityListProps) {
  const [expanded, setExpanded] = useState(false);

  if (!reasons || reasons.length === 0) return null;

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
      <button
        onClick={() => setExpanded(e => !e)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: '12px',
          fontWeight: 600,
          color: 'var(--muted)',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}
      >
        <span>▾ {label}</span>
        <span>{expanded ? 'Hide' : 'Show'}</span>
      </button>

      {expanded && (
        <div style={{ padding: '0 14px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {reasons.map((reason, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
              <Check size={12} style={{ color: 'var(--ok)', marginTop: '2px', flexShrink: 0 }} />
              <span style={{ fontSize: '12px', color: 'var(--ink)', lineHeight: '1.5' }}>
                {reason}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
