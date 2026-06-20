interface ReadinessBarProps {
  score: number;
}

export function ReadinessBar({ score }: ReadinessBarProps) {
  let colorClass = 'readiness-high';
  if (score < 40) colorClass = 'readiness-low';
  else if (score <= 70) colorClass = 'readiness-mid';

  return (
    <div className="flex items-center gap-3">
      <div className="readiness-bar-track flex-1">
        <div 
          className={`readiness-bar-fill ${colorClass}`}
          style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
        />
      </div>
      <span className="text-[11px] font-bold text-text-1 w-6 text-right">
        {Math.round(score)}
      </span>
    </div>
  );
}
