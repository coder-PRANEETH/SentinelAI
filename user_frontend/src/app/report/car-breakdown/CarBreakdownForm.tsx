"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { ReportProgressSteps } from "@/components/ReportProgressSteps";
import { LocationPermissionBanner } from "@/components/LocationPermissionBanner";
import { UserMapPanel } from "@/components/UserMapPanel";
import { useGeolocation } from "@/hooks/useGeolocation";
import { geocodeAddress } from "@/lib/api";
import { saveDraftReport } from "@/lib/reportStore";
import type { GeoPoint, IncidentTypeId } from "@/types/incident";

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

// Each incident type gets its own heading, two relevant detail selects, and
// a description placeholder — so picking "Medical Emergency" (etc.) on the
// landing page / /report actually shows medical-emergency-relevant fields
// instead of the car-breakdown vehicle/issue fields.
const TYPE_CONFIG: Record<
  IncidentTypeId,
  {
    heading: string;
    subheading: string;
    fieldALabel: string;
    fieldAOptions: string[];
    fieldBLabel: string;
    fieldBOptions: string[];
    descriptionPlaceholder: string;
  }
> = {
  car_breakdown: {
    heading: "Tell us what happened",
    subheading: "A few quick details help responders prepare before they arrive.",
    fieldALabel: "Vehicle type",
    fieldAOptions: VEHICLE_TYPES,
    fieldBLabel: "Issue type",
    fieldBOptions: ISSUE_TYPES,
    descriptionPlaceholder: "E.g. Car stopped suddenly on the flyover, hazard lights on...",
  },
  accident: {
    heading: "Tell us about the accident",
    subheading: "A few quick details help responders prepare before they arrive.",
    fieldALabel: "Vehicle(s) involved",
    fieldAOptions: VEHICLE_TYPES,
    fieldBLabel: "Severity",
    fieldBOptions: ["Minor (no injuries)", "Injuries reported", "Multi-vehicle", "Vehicle overturned"],
    descriptionPlaceholder: "E.g. Two cars collided at the signal, one person injured...",
  },
  road_block: {
    heading: "Tell us about the road block",
    subheading: "A few quick details help responders clear the way faster.",
    fieldALabel: "Type of block",
    fieldAOptions: ["Debris", "Construction", "Flooding", "Fallen tree", "Protest / Gathering", "Other"],
    fieldBLabel: "Road status",
    fieldBOptions: ["Partially blocked", "Fully blocked"],
    descriptionPlaceholder: "E.g. Fallen tree blocking both lanes near the junction...",
  },
  medical_emergency: {
    heading: "Tell us about the medical emergency",
    subheading: "A few quick details help responders bring the right help.",
    fieldALabel: "Patient status",
    fieldAOptions: ["Conscious & responsive", "Conscious, distressed", "Unconscious", "Not breathing normally"],
    fieldBLabel: "Type of emergency",
    fieldBOptions: ["Cardiac / chest pain", "Breathing difficulty", "Injury / bleeding", "Fainting", "Other"],
    descriptionPlaceholder: "E.g. Person collapsed near the bus stop, conscious but in pain...",
  },
};

export function CarBreakdownForm() {
  const searchParams = useSearchParams();
  const incidentTypeId = (searchParams.get("type") as IncidentTypeId) || "car_breakdown";

  // Keying on incidentTypeId remounts the form fresh whenever the chosen
  // incident type changes, so each type's fields/state start clean instead
  // of carrying over stale selections from a previous type.
  return <CarBreakdownFormFields key={incidentTypeId} incidentTypeId={incidentTypeId} />;
}

function CarBreakdownFormFields({ incidentTypeId }: { incidentTypeId: IncidentTypeId }) {
  const router = useRouter();
  const config = TYPE_CONFIG[incidentTypeId] ?? TYPE_CONFIG.car_breakdown;

  const { location, status, error, requestLocation } = useGeolocation();
  const [manualLocation, setManualLocation] = useState<GeoPoint | null>(null);
  const [manualLocationLabel, setManualLocationLabel] = useState<string | null>(null);

  const [fieldA, setFieldA] = useState(config.fieldAOptions[0]);
  const [fieldB, setFieldB] = useState(config.fieldBOptions[0]);
  const [description, setDescription] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [locationRequiredError, setLocationRequiredError] = useState<string | null>(null);

  const effectiveLocation = location ?? manualLocation;

  const handleManualLocationSubmit = async (address: string) => {
    const { point, label } = await geocodeAddress(address);
    setManualLocation(point);
    setManualLocationLabel(label.split(",").slice(0, 2).join(", "));
    setLocationRequiredError(null);
  };

  const handleFindSafeLocation = () => {
    if (!effectiveLocation) {
      setLocationRequiredError(
        "We need your location to find help nearby — enable location access or enter it manually above."
      );
      return;
    }
    setLocationRequiredError(null);
    setSubmitting(true);
    saveDraftReport({
      incidentTypeId,
      vehicleType: fieldA,
      issueType: fieldB,
      description,
      phoneNumber: phoneNumber || undefined,
      location: effectiveLocation,
    });
    router.push("/report/safe-location");
  };

  return (
    <PageShell>
      <ReportProgressSteps currentStep={2} />
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>{config.heading}</h1>
      <p style={{ fontSize: 14, color: "var(--color-text-2)", marginBottom: 24 }}>{config.subheading}</p>

      <div style={{ marginBottom: 20 }}>
        <LocationPermissionBanner
          status={status}
          error={error}
          onRequest={requestLocation}
          hasManualLocation={!!manualLocation}
          manualLocationLabel={manualLocationLabel}
          onManualLocationSubmit={handleManualLocationSubmit}
        />
        {locationRequiredError && (
          <div style={{ fontSize: 12, color: "var(--color-danger)", marginTop: 8 }}>{locationRequiredError}</div>
        )}
      </div>

      <div className="card fade-up" style={{ marginBottom: 20 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
          <Field label={config.fieldALabel}>
            <select className="sel-input" value={fieldA} onChange={(e) => setFieldA(e.target.value)}>
              {config.fieldAOptions.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
          <Field label={config.fieldBLabel}>
            <select className="sel-input" value={fieldB} onChange={(e) => setFieldB(e.target.value)}>
              {config.fieldBOptions.map((v) => (
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
            placeholder={config.descriptionPlaceholder}
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
        <UserMapPanel title="Your current location" userLocation={effectiveLocation} height="280px" />
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
