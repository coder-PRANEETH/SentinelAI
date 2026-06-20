"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoPoint, SafeLocation } from "@/types/incident";

/**
 * PublicMap — MapLibre GL JS map for the public incident-reporting site.
 * Reuses the same tile style and marker visual language as the operator
 * frontend's BengaluruMap (dark OpenFreeMap tiles, lime/dark marker style)
 * but stripped down to just: user location pin + safe-location pins.
 */

const MAP_CONFIG = {
  style: "https://tiles.openfreemap.org/styles/dark",
  center: [77.5946, 12.9716] as [number, number],
  zoom: 13,
  minZoom: 9,
  maxZoom: 19,
};

function createUserMarker(): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.style.cssText = `
    position: relative; width: 36px; height: 36px;
    display: flex; align-items: center; justify-content: center;
    will-change: transform;
  `;
  wrapper.innerHTML = `
    <div style="position:absolute;width:32px;height:32px;border-radius:50%;background:#4299E1;opacity:0.25;filter:blur(3px);"></div>
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="8" fill="#0a0a0a" stroke="#4299E1" stroke-width="3" />
      <circle cx="10" cy="10" r="3" fill="#4299E1" />
    </svg>
  `;
  return wrapper;
}

function createSafeMarker(type: SafeLocation["type"], rank: number): HTMLElement {
  const color = type === "police_station" ? "#CDFF50" : "#FF9900";
  const wrapper = document.createElement("div");
  wrapper.style.cssText = `
    position: relative; width: 34px; height: 34px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; will-change: transform;
  `;
  wrapper.innerHTML = `
    <div style="position:absolute;width:30px;height:30px;border-radius:50%;background:${color};opacity:0.2;filter:blur(3px);"></div>
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
      <circle cx="11" cy="11" r="9" fill="#0a0a0a" stroke="${color}" stroke-width="2.5" />
      <text x="11" y="15" text-anchor="middle" font-size="11" font-weight="700" fill="${color}" font-family="Inter, sans-serif">${rank}</text>
    </svg>
  `;
  return wrapper;
}

interface PublicMapProps {
  userLocation: GeoPoint | null;
  safeLocations?: SafeLocation[];
  height?: string;
}

export function PublicMap({ userLocation, safeLocations = [], height = "360px" }: PublicMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const [isMapLoaded, setIsMapLoaded] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_CONFIG.style,
      center: userLocation
        ? [userLocation.longitude, userLocation.latitude]
        : MAP_CONFIG.center,
      zoom: userLocation ? 14 : MAP_CONFIG.zoom,
      minZoom: MAP_CONFIG.minZoom,
      maxZoom: MAP_CONFIG.maxZoom,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    mapRef.current = map;

    let resizeTimer: ReturnType<typeof setTimeout> | null = null;
    let initialFire = true;
    const resizeObserver = new ResizeObserver(() => {
      if (initialFire) {
        initialFire = false;
        return;
      }
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => mapRef.current?.resize(), 50);
    });
    resizeObserver.observe(containerRef.current);

    map.on("load", () => {
      map.resize();
      setIsMapLoaded(true);
    });

    return () => {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeObserver.disconnect();
      markersRef.current.forEach((m) => m.remove());
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update markers whenever location/safe-locations change.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapLoaded) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    if (userLocation) {
      const marker = new maplibregl.Marker({ element: createUserMarker(), anchor: "center" })
        .setLngLat([userLocation.longitude, userLocation.latitude])
        .addTo(map);
      markersRef.current.push(marker);
    }

    safeLocations.forEach((loc, idx) => {
      const marker = new maplibregl.Marker({
        element: createSafeMarker(loc.type, idx + 1),
        anchor: "center",
      })
        .setLngLat([loc.longitude, loc.latitude])
        .addTo(map);
      markersRef.current.push(marker);
    });

    if (userLocation) {
      map.flyTo({
        center: [userLocation.longitude, userLocation.latitude],
        zoom: safeLocations.length ? 12.5 : 14,
        duration: 800,
        essential: true,
      });
    }
  }, [userLocation, safeLocations, isMapLoaded]);

  return (
    <div
      style={{
        height,
        width: "100%",
        position: "relative",
        borderRadius: "20px",
        overflow: "hidden",
        border: "1px solid var(--color-border)",
      }}
    >
      <div ref={containerRef} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
      {!userLocation && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(10,10,10,0.55)",
            color: "#A0A0A0",
            fontSize: "13px",
            fontWeight: 500,
            pointerEvents: "none",
          }}
        >
          Enable location to see your position
        </div>
      )}
    </div>
  );
}
