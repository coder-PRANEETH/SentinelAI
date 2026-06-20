"use client";

import Link from "next/link";
import { LiveOpsMap } from "@/components/map/LiveOpsMap";

// Header nav links. Per the brief, Car Breakdown opens the dedicated form;
// the rest enter the generic report flow. (The shared INCIDENT_TYPES list —
// used by /report — is intentionally left untouched.)
const LANDING_LINKS = [
  { id: "car_breakdown", label: "Car Breakdown", href: "/report/car-breakdown" },
  { id: "accident", label: "Accident", href: "/report" },
  { id: "road_block", label: "Road Block", href: "/report" },
  { id: "medical_emergency", label: "Medical Emergency", href: "/report" },
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

      <aside className="ops-map-labels" aria-hidden="true">
        <div className="ops-map-label">
          <span className="ops-map-label-dot ops-map-label-dot--lime" />
          <div>
            <div className="ops-map-label-title">Live routes</div>
            <div className="ops-map-label-value">7 active corridors</div>
          </div>
        </div>
        <div className="ops-map-label">
          <span className="ops-map-label-dot ops-map-label-dot--cyan" />
          <div>
            <div className="ops-map-label-title">Nearest responders</div>
            <div className="ops-map-label-value">3 within 5 km</div>
          </div>
        </div>
        <div className="ops-map-label">
          <span className="ops-map-label-dot ops-map-label-dot--amber" />
          <div>
            <div className="ops-map-label-title">Safe zones</div>
            <div className="ops-map-label-value">11 verified</div>
          </div>
        </div>
      </aside>

      <p className="ops-footer-note">
        In a life-threatening emergency, always call your local emergency number first.
      </p>
    </div>
  );
}
