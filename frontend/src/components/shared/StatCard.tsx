import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  icon: LucideIcon;
  title: string;
  value?: number | string;
  total?: number | string;
  percentage: number;
  variant?: 'default' | 'accent' | 'dark';
  capacityDots?: number;
  usedDots?: number;
  totalDots?: number;
  isLoading?: boolean;
}

export function StatCard({
  icon: Icon,
  title,
  value,
  total,
  percentage,
  variant = 'default',
  usedDots = 0,
  totalDots = 10,
  isLoading
}: StatCardProps) {
  if (isLoading) {
    return (
      <div className={`card ${variant !== 'default' ? `card-${variant}` : ''} h-[160px] skeleton`} />
    );
  }

  const isAccent = variant === 'accent';
  const isDark = variant === 'dark';

  return (
    <div className={`card ${variant !== 'default' ? `card-${variant}` : ''}`}>
      <div className="stat-card-header">
        <div 
          className="stat-card-icon-wrap" 
          style={{ background: isAccent ? 'rgba(0,0,0,0.1)' : isDark ? '#2A2A2A' : '#F5F5F3' }}
        >
          <Icon size={16} color={isAccent ? '#111111' : isDark ? '#FFFFFF' : '#111111'} />
        </div>
        <span style={{ fontSize: '14px', fontWeight: 600, color: isDark ? '#FFFFFF' : '#111111' }}>
          {title}
        </span>
      </div>

      <div>
        {isLoading ? (
          <div style={{ width: 80, height: 38, background: 'rgba(0,0,0,0.08)', borderRadius: 8 }} />
        ) : (
          <div style={{
            fontSize: '38px',
            fontWeight: 800,
            lineHeight: 1.1,
            color: variant === 'accent' ? '#111111' : '#111111',
            display: 'flex',
            alignItems: 'baseline',
            gap: '4px',
          }}>
            <span>{value !== undefined && value !== null && !Number.isNaN(value) ? value : '—'}</span>
            {total && (
              <span style={{ fontSize: '13px', fontWeight: 400, color: '#6B6B6B' }}>
                {total}
              </span>
            )}
          </div>
        )}
        {percentage !== undefined && percentage !== null && (
          <span 
            className="stat-percentage-badge" 
            style={{ color: isDark ? '#FFFFFF' : '#111111', marginTop: '8px' }}
          >
            {typeof percentage === 'number' ? `${percentage}%` : percentage}
            {typeof percentage === 'number' && percentage !== 0 && (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: 4 }}>
                <path d={percentage > 0 ? "M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" : "M3 12a9 9 0 1 0 9-9c-2.52 0-4.93 1-6.74 2.74L3 8"} />
                <path d={percentage > 0 ? "M21 3v5h-5" : "M3 3v5h5"} />
              </svg>
            )}
          </span>
        )}
      </div>

      {totalDots !== undefined && totalDots > 0 && (
        <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '16px' }}>
          {Array.from({ length: totalDots }).map((_, i) => {
            const isFilled = i < usedDots;
            return (
              <div
                key={i}
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: '50%',
                  backgroundColor: isFilled
                    ? (variant === 'accent' ? 'rgba(0,0,0,0.45)' : '#111111')
                    : 'transparent',
                  border: isFilled
                    ? 'none'
                    : `2px dashed ${variant === 'accent' ? 'rgba(0,0,0,0.20)' : '#D0D0D0'}`,
                }}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
