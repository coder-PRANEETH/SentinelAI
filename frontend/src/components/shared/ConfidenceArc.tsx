'use client';

/**
 * ConfidenceArc — SVG donut arc displaying prediction confidence %.
 * Used in AI Copilot panel. Clean SVG, no animations.
 */

interface ConfidenceArcProps {
  value: number;   // 0–100
  label?: string;
  size?: number;
}

export function ConfidenceArc({ value, label, size = 90 }: ConfidenceArcProps) {
  const clamp = Math.max(0, Math.min(100, value));
  const r = (size / 2) - 10;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;
  const dashoffset = circumference - (clamp / 100) * circumference;

  const strokeColor =
    clamp >= 80 ? 'var(--ok)' :
    clamp >= 60 ? 'var(--warn)' :
    'var(--err)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Track */}
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke="var(--border)"
          strokeWidth="8"
        />
        {/* Arc */}
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke={strokeColor}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={dashoffset}
          strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`}
        />
        <text
          x={cx} y={cy}
          className="confidence-arc-value"
          style={{ fontSize: size < 80 ? '14px' : '18px', fontWeight: 700, fill: 'var(--ink)', textAnchor: 'middle', dominantBaseline: 'middle' }}
        >
          {Math.round(clamp)}%
        </text>
      </svg>
      {label && (
        <span style={{ fontSize: '10px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>
          {label}
        </span>
      )}
    </div>
  );
}
