"use client";

import { useCallback, useState } from "react";
import type { GeoPoint } from "@/types/incident";

export type GeolocationStatus = "idle" | "requesting" | "granted" | "denied" | "unsupported";

interface UseGeolocationResult {
  location: GeoPoint | null;
  status: GeolocationStatus;
  error: string | null;
  requestLocation: () => void;
}

export function useGeolocation(): UseGeolocationResult {
  const [location, setLocation] = useState<GeoPoint | null>(null);
  const [status, setStatus] = useState<GeolocationStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const requestLocation = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setStatus("unsupported");
      setError("Geolocation is not supported on this device.");
      return;
    }

    setStatus("requesting");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        });
        setStatus("granted");
        setError(null);
      },
      (err) => {
        setStatus("denied");
        setError(err.message || "Unable to access your location.");
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
    );
  }, []);

  return { location, status, error, requestLocation };
}
