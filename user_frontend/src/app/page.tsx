"use client";

import Link from "next/link";
import { LiveOpsMap } from "@/components/map/LiveOpsMap";

// Header nav links — each one opens its own report form directly (skipping
// the generic /report type-picker), same as Car Breakdown always did.
const LANDING_LINKS = [
  { id: "car_breakdown", label: "Car Breakdown", href: "/report/car-breakdown" },
  { id: "accident", label: "Accident", href: "/report/car-breakdown?type=accident" },
  { id: "road_block", label: "Road Block", href: "/report/car-breakdown?type=road_block" },
  { id: "medical_emergency", label: "Medical Emergency", href: "/report/car-breakdown?type=medical_emergency" },
] as const;

export default function LandingPage() {
  return (
    <div className="ops-root">
      <LiveOpsMap />
      <div className="ops-overlay" aria-hidden="true" />
      <div className="ops-scanline" aria-hidden="true" />

      <header className="ops-header">
        <Link href="/" className="ops-brand">
          <span className="ops-brand-mark">S</span>
          <span className="ops-brand-name">SentinelAI</span>
        </Link>

        <nav className="ops-header-nav">
          {LANDING_LINKS.map((link) => (
            <Link key={link.id} href={link.href} className="ops-header-link">
              {link.label}
            </Link>
          ))}
        </nav>

        <Link href="/report" className="btn-primary ops-header-cta">
          Report Now →
        </Link>
      </header>

      <p className="ops-footer-note">
        In a life-threatening emergency, always call your local emergency number first.
      </p>
    </div>
  );
}
