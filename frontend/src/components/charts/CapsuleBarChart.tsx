import { useEffect, useRef, useState } from 'react';

interface CapsuleBarData {
  label: string;
  value: number;
  projected?: boolean;
  highlighted?: boolean;
  accentColor?: string;
}

interface CapsuleBarChartProps {
  data: CapsuleBarData[];
  height?: number;
  barWidth?: number;
  barGap?: number;
  topColor?: string;
  bottomColor?: string;
  showYAxis?: boolean;
}

export function CapsuleBarChart({
  data,
  height = 300,
  barWidth = 32,
  barGap = 14,
  topColor = '#111111',
  bottomColor = '#CDFF50',
  showYAxis = true,
}: CapsuleBarChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(0);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(entries => {
      if (entries[0]) {
        // Add a small safety buffer to prevent horizontal scroll
        setContainerWidth(Math.floor(entries[0].contentRect.width) - 4);
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const marginTop = 24; // Space for badges at top
  const chartHeight = height - 40 - marginTop; // reserve space for x-axis and badges
  const yAxisWidth = showYAxis ? 40 : 0;
  
  // Calculate dynamic gap if container is wider than default
  const defaultTotalWidth = data.length * (barWidth + barGap);
  const availableWidth = containerWidth > 0 ? containerWidth - yAxisWidth : defaultTotalWidth;
  
  // Ensure gap is at least the default barGap, but cap it so they don't look completely disjointed
  const dynamicGap = data.length > 1 
    ? Math.min(80, Math.max(barGap, (availableWidth - (data.length * barWidth)) / (data.length - 1)))
    : barGap;

  const totalWidth = data.length * barWidth + (data.length - 1) * dynamicGap;

  const renderBar = (d: CapsuleBarData, x: number, chartHeight: number, barW: number, isLast: boolean) => {
    const totalH = chartHeight;
    const splitY = marginTop + totalH * (1 - d.value);
    const rx = barW / 2;

    if (d.projected) {
      return (
        <g key={d.label}>
          <rect
            x={x} y={marginTop} width={barW} height={totalH}
            rx={rx} ry={rx}
            fill="none"
            stroke="#D0D0D0"
            strokeWidth={2}
            strokeDasharray="5,4"
          />
        </g>
      );
    }

    const currentBottomColor = d.accentColor || bottomColor;

    return (
      <g key={d.label}>
        {/* Full capsule — dark color */}
        <rect x={x} y={marginTop} width={barW} height={totalH} rx={rx} ry={rx} fill={topColor} />

        {/* Bottom lime portion — clip to bottom of capsule */}
        <clipPath id={`clip-${x}`}>
          <rect x={x} y={marginTop} width={barW} height={totalH} rx={rx} ry={rx} />
        </clipPath>
        <rect
          x={x} y={splitY} width={barW} height={marginTop + totalH - splitY}
          fill={currentBottomColor}
          clipPath={`url(#clip-${x})`}
        />

        {/* Circle dot at top of bar */}
        <circle
          cx={x + barW / 2}
          cy={marginTop + 10}
          r={5}
          fill="#111111"
          stroke="#FFFFFF"
          strokeWidth={2}
        />

        {/* Percentage badge if highlighted */}
        {d.highlighted && (
          <g>
            <rect
              x={isLast ? x - 44 : x + barW + 4} y={splitY - 12}
              width={40} height={22}
              rx={6} fill="#111111"
            />
            <text
              x={isLast ? x - 24 : x + barW + 24} y={splitY + 3}
              textAnchor="middle"
              fill="#FFFFFF"
              fontSize={11}
              fontWeight={600}
            >
              {Math.round(d.value * 100)}%
            </text>
          </g>
        )}
      </g>
    );
  };

  return (
    <div ref={containerRef} style={{ width: '100%', overflowX: 'auto', paddingBottom: '8px' }}>
      <svg width={Math.max(totalWidth + yAxisWidth, containerWidth)} height={height} style={{ minWidth: '100%' }}>
        {showYAxis && (
          <g transform="translate(0, 0)">
            {[0.2, 0.4, 0.6, 0.8, 1.0].map((tick) => {
              const y = marginTop + chartHeight * (1 - tick);
              return (
                <text
                  key={tick}
                  x={32}
                  y={y + 4}
                  textAnchor="end"
                  fill="#A0A0A0"
                  fontSize={11}
                  fontWeight={500}
                >
                  {tick.toFixed(1)}
                </text>
              );
            })}
          </g>
        )}
        <g transform={`translate(${yAxisWidth}, 0)`}>
          {data.map((d, i) => {
            const x = i * (barWidth + dynamicGap);
            const isLast = i === data.length - 1;
            return (
              <g key={i}>
                {renderBar(d, x, chartHeight, barWidth, isLast)}
                <text
                  x={x + barWidth / 2}
                  y={height - 15}
                  textAnchor="middle"
                  fill="#6B6B6B"
                  fontSize={12}
                  fontWeight={500}
                >
                  {d.label}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
