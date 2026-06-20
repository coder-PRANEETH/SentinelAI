/** Minimal inline SVG icon set — avoids pulling in an icon library for v1. */

type IconProps = { size?: number; color?: string };

export function CarIcon({ size = 28, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8">
      <path d="M5 11l1.5-4.5A2 2 0 0 1 8.4 5h7.2a2 2 0 0 1 1.9 1.5L19 11" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="3" y="11" width="18" height="6" rx="2" />
      <circle cx="7.5" cy="17.5" r="1.5" fill={color} />
      <circle cx="16.5" cy="17.5" r="1.5" fill={color} />
    </svg>
  );
}

export function AlertTriangleIcon({ size = 28, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8">
      <path d="M12 3.5l9 16h-18l9-16z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 10v4" strokeLinecap="round" />
      <circle cx="12" cy="17" r="0.9" fill={color} />
    </svg>
  );
}

export function OctagonIcon({ size = 28, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8">
      <path d="M8 3h8l5 5v8l-5 5H8l-5-5V8l5-5z" strokeLinejoin="round" />
      <path d="M9 9l6 6M15 9l-6 6" strokeLinecap="round" />
    </svg>
  );
}

export function HeartPulseIcon({ size = 28, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8">
      <path
        d="M20.5 8.5c0-2.5-2-4.5-4.5-4.5-1.6 0-3 .8-3.9 2.1C11.2 4.8 9.8 4 8.2 4 5.7 4 3.7 6 3.7 8.5c0 4 5 7.5 8.4 10.8 3.3-3.3 8.4-6.8 8.4-10.8z"
        strokeLinejoin="round"
      />
      <path d="M5 10h2.5l1.5 3 2-5 1.5 3H16" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function LocationPinIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8">
      <path d="M12 21s7-7.2 7-12a7 7 0 1 0-14 0c0 4.8 7 12 7 12z" strokeLinejoin="round" />
      <circle cx="12" cy="9" r="2.5" />
    </svg>
  );
}

export function ShieldCheckIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8">
      <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" strokeLinejoin="round" />
      <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function CheckCircleIcon({ size = 64, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.6">
      <circle cx="12" cy="12" r="9.5" />
      <path d="M8 12.5l2.6 2.6L16 9.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export const ICON_MAP: Record<string, (p: IconProps) => React.ReactElement> = {
  car: CarIcon,
  "alert-triangle": AlertTriangleIcon,
  octagon: OctagonIcon,
  "heart-pulse": HeartPulseIcon,
};
