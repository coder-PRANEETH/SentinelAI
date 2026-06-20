"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { ReportProgressSteps } from "@/components/ReportProgressSteps";
import { LocationPermissionBanner } from "@/components/LocationPermissionBanner";
import { UserMapPanel } from "@/components/UserMapPanel";
import { useGeolocation } from "@/hooks/useGeolocation";
import { saveDraftReport } from "@/lib/reportStore";
import type { IncidentTypeId } from "@/types/incident";

const VEHICLE_TYPES = ["Car", "Two-wheeler", "Auto Rickshaw", "Bus", "Truck / Heavy Vehicle", "Other"];
const ISSUE_TYPES = [
  "Engine failure",
  "Flat tyre",
  "Battery / Electrical",
  "Overheating",
  "Out of fuel",
  "Collision damage",
  "Other",
];

export function CarBreakdownForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const incidentTypeId = (searchParams.get("type") as IncidentTypeId) || "car_breakdown";

  const { location, status, error, requestLocation } = useGeolocation();

  const [vehicleType, setVehicleType] = useState(VEHICLE_TYPES[0]);
  const [issueType, setIssueType] = useState(ISSUE_TYPES[0]);
  const [description, setDescription] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleFindSafeLocation = () => {
    setSubmitting(true);
    saveDraftReport({
      incidentTypeId,
      vehicleType,
      issueType,
      description,
      phoneNumber: phoneNumber || undefined,
      location,
    });
    router.push("/report/safe-location");
  };

  return (
    <PageShell>
      <ReportProgressSteps currentStep={2} />
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Tell us what happened</h1>
      <p style={{ fontSize: 14, color: "var(--color-text-2)", marginBottom: 24 }}>
        A few quick details help responders prepare before they arrive.
      </p>

      <div style={{ marginBottom: 20 }}>
        <LocationPermissionBanner status={status} error={error} onRequest={requestLocation} />
      </div>

      <div className="card fade-up" style={{ marginBottom: 20 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
          <Field label="Vehicle type">
            <select className="sel-input" value={vehicleType} onChange={(e) => setVehicleType(e.target.value)}>
              {VEHICLE_TYPES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Issue type">
            <select className="sel-input" value={issueType} onChange={(e) => setIssueType(e.target.value)}>
              {ISSUE_TYPES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field label="Describe what happened">
          <textarea
            className="sel-input"
            rows={4}
            placeholder="E.g. Car stopped suddenly on the flyover, hazard lights on..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            style={{ resize: "vertical", fontFamily: "inherit" }}
          />
        </Field>

        <Field label="Phone number (optional)">
          <input
            className="sel-input"
            type="tel"
            placeholder="+91 90000 00000"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
          />
        </Field>
      </div>

      <div className="fade-up" style={{ marginBottom: 24 }}>
        <UserMapPanel title="Your current location" userLocation={location} height="280px" />
      </div>

      <button
        onClick={handleFindSafeLocation}
        disabled={submitting}
        className="btn-primary"
        style={{ width: "100%", fontSize: 15 }}
      >
        Find Safe Location →
      </button>

      <style>{`
        .sel-input {
          width: 100%;
          background: var(--color-surface-raised);
          border: 1px solid var(--color-border);
          border-radius: 12px;
          padding: 10px 12px;
          color: var(--color-text-1);
          font-size: 14px;
          outline: none;
          transition: border-color 0.15s ease;
        }
        .sel-input:focus {
          border-color: var(--color-accent);
        }
      `}</style>
    </PageShell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--color-text-2)", marginBottom: 6 }}>
        {label}
      </label>
      {children}
    </div>
  );
}
