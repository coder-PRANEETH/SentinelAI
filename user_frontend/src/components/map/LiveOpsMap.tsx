"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { BENGALURU_STATIONS } from "@/lib/stationsData";

/**
 * LiveOpsMap — the public landing page's hero map. Two layers:
 *   1. An ambient "emergency operations" backdrop (flowing routes, pulsing
 *      stations/incidents, drifting vehicles) that plays when no trip is
 *      active, plus real 3D building extrusions and full pan/zoom/tilt
 *      interactivity.
 *   2. An interactive "plan a trip" mode: the visitor types a destination,
 *      we resolve their live location, geocode the destination (Nominatim),
 *      fetch a real driving route (OSRM), then fly the camera through a
 *      cinematic Google-Maps-style navigation: fit-to-route, tilt into 3D,
 *      and follow a moving puck along the road with the camera banking to
 *      match heading.
 *
 * Everything runs on free, keyless services (OpenFreeMap tiles, OSRM's
 * public routing demo, Nominatim geocoding) — no paid map APIs.
 */

const MAP_STYLE = "https://tiles.openfreemap.org/styles/dark";
const CENTER: [number, number] = [77.615, 12.965];
const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";
const OSRM_URL = "https://router.project-osrm.org/route/v1/driving";

type RouteDef = { coords: [number, number][]; color: string };

/** Catmull-Rom spline smoothing so zig-zag waypoints read as gentle curves. */
function smoothRoute(points: [number, number][], segmentsPerSpan = 8): [number, number][] {
  if (points.length < 3) return points;
  const pts = [points[0], ...points, points[points.length - 1]];
  const out: [number, number][] = [];
  for (let i = 1; i < pts.length - 2; i++) {
    const [p0x, p0y] = pts[i - 1];
    const [p1x, p1y] = pts[i];
    const [p2x, p2y] = pts[i + 1];
    const [p3x, p3y] = pts[i + 2];
    for (let s = 0; s < segmentsPerSpan; s++) {
      const t = s / segmentsPerSpan;
      const t2 = t * t;
      const t3 = t2 * t;
      const x =
        0.5 *
        (2 * p1x +
          (-p0x + p2x) * t +
          (2 * p0x - 5 * p1x + 4 * p2x - p3x) * t2 +
          (-p0x + 3 * p1x - 3 * p2x + p3x) * t3);
      const y =
        0.5 *
        (2 * p1y +
          (-p0y + p2y) * t +
          (2 * p0y - 5 * p1y + 4 * p2y - p3y) * t2 +
          (-p0y + 3 * p1y - 3 * p2y + p3y) * t3);
      out.push([x, y]);
    }
  }
  out.push(points[points.length - 1]);
  return out;
}

const LIME = "#cdff50";
const CYAN = "#3df2ff";

// Multi-point routes threaded through Bengaluru — built from real station
// coordinates so the curves hug realistic parts of the city. The cyan group
// leans east/right so the right side of the screen (where the map is most
// visible, behind the left card panel) always has visible live movement.
const RAW_ROUTES: RouteDef[] = [
  {
    color: LIME,
    coords: [
      [77.615, 12.965],
      [77.598, 12.979],
      [77.574, 12.974],
      [77.551, 12.993],
      [77.522, 13.004],
    ],
  },
  {
    color: CYAN,
    coords: [
      [77.615, 12.965],
      [77.632, 12.951],
      [77.656, 12.956],
      [77.679, 12.935],
      [77.708, 12.924],
    ],
  },
];

const ROUTES: RouteDef[] = RAW_ROUTES.map((r) => ({
  color: r.color,
  coords: smoothRoute(r.coords),
}));

// Incident hotspots (red pulses) scattered near the routes.
const INCIDENTS: [number, number][] = [
  [77.612, 12.948],
  [77.645, 12.962],
  [77.58, 12.992],
  [77.668, 12.94],
  [77.6, 12.918],
  [77.7, 12.96],
];

type IncidentMarker = {
  id: string;
  coordinates: [number, number];
};

// ── Generic path math (shared by ambient vehicles + the trip puck) ───────

function pathMetrics(coords: [number, number][]) {
  const cum = [0];
  let total = 0;
  for (let i = 1; i < coords.length; i++) {
    const dx = coords[i][0] - coords[i - 1][0];
    const dy = coords[i][1] - coords[i - 1][1];
    total += Math.hypot(dx, dy);
    cum.push(total);
  }
  return { cum, total: total || 1 };
}

function positionAlong(
  coords: [number, number][],
  cum: number[],
  total: number,
  t: number
): { point: [number, number]; index: number; heading: number } {
  const dist = Math.min(Math.max(t, 0), 1) * total;
  for (let i = 1; i < cum.length; i++) {
    if (dist <= cum[i] || i === cum.length - 1) {
      const segStart = cum[i - 1];
      const segLen = cum[i] - segStart || 1;
      const f = (dist - segStart) / segLen;
      const a = coords[i - 1];
      const b = coords[i];
      const point: [number, number] = [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
      return { point, index: i - 1, heading: bearingBetween(a, b) };
    }
  }
  return { point: coords[coords.length - 1], index: coords.length - 1, heading: 0 };
}

function bearingBetween(a: [number, number], b: [number, number]): number {
  const lon1 = (a[0] * Math.PI) / 180;
  const lon2 = (b[0] * Math.PI) / 180;
  const lat1 = (a[1] * Math.PI) / 180;
  const lat2 = (b[1] * Math.PI) / 180;
  const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function haversineKm(a: [number, number], b: [number, number]): number {
  const R = 6371;
  const dLat = ((b[1] - a[1]) * Math.PI) / 180;
  const dLon = ((b[0] - a[0]) * Math.PI) / 180;
  const lat1 = (a[1] * Math.PI) / 180;
  const lat2 = (b[1] * Math.PI) / 180;
  const sinDLat = Math.sin(dLat / 2);
  const sinDLon = Math.sin(dLon / 2);
  const h = sinDLat * sinDLat + Math.cos(lat1) * Math.cos(lat2) * sinDLon * sinDLon;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

type Vehicle = {
  route: [number, number][];
  color: string;
  cum: number[];
  total: number;
  t: number;
  speed: number;
};

function buildVehicle(route: RouteDef, speed: number, offset: number): Vehicle {
  const { cum, total } = pathMetrics(route.coords);
  return { route: route.coords, color: route.color, cum, total, t: offset, speed };
}

// ── Cinematic intro: buildings rising from flat footprints + a slowly
// orbiting "sun" that sweeps light across the extruded skyline ───────────

/** Building height expression scaled by a 0..1 growth progress, so the
 *  skyline can animate from flat footprints up to full height. */
function buildingsHeightExpression(progress: number) {
  return [
    "interpolate",
    ["linear"],
    ["zoom"],
    13, 0,
    13.5, ["*", progress, ["coalesce", ["get", "render_height"], ["get", "height"], 15]],
  ] as unknown as maplibregl.ExpressionSpecification;
}

/** Eases building heights from 0 to full over `durationMs`. Reports each
 *  requestAnimationFrame id via `onRaf` so the caller can cancel on unmount. */
function animateBuildingGrowth(map: maplibregl.Map, durationMs: number, onRaf: (id: number) => void) {
  const start = performance.now();
  const step = (now: number) => {
    const p = Math.min(1, (now - start) / durationMs);
    const eased = 1 - Math.pow(1 - p, 3);
    if (map.getLayer("ops-3d-buildings")) {
      map.setPaintProperty("ops-3d-buildings", "fill-extrusion-height", buildingsHeightExpression(eased));
    }
    if (p < 1) onRaf(requestAnimationFrame(step));
  };
  onRaf(requestAnimationFrame(step));
}

/** Canvas-based pulsing-dot StyleImage (the canonical MapLibre technique). */
function makePulsingDot(map: maplibregl.Map, rgb: string, period: number) {
  const size = 130;
  let ctx: CanvasRenderingContext2D | null = null;
  return {
    width: size,
    height: size,
    data: new Uint8Array(size * size * 4),
    onAdd() {
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      ctx = canvas.getContext("2d");
    },
    render() {
      if (!ctx) return false;
      const t = (performance.now() % period) / period;
      const inner = (size / 2) * 0.18;
      const outer = inner + (size / 2 - inner) * t;
      ctx.clearRect(0, 0, size, size);

      ctx.beginPath();
      ctx.arc(size / 2, size / 2, outer, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${rgb}, ${0.45 * (1 - t)})`;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(size / 2, size / 2, inner, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${rgb}, 1)`;
      ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
      ctx.lineWidth = 2 + 3 * (1 - t);
      ctx.shadowColor = `rgba(${rgb}, 0.9)`;
      ctx.shadowBlur = 12;
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.stroke();

      this.data = new Uint8Array(ctx.getImageData(0, 0, size, size).data);
      map.triggerRepaint();
      return true;
    },
  } as maplibregl.StyleImageInterface;
}

/** 1x1 transparent RGBA pixel — used to silently satisfy any sprite image the
 *  style references but the sprite sheet doesn't ship (e.g. "wood-pattern"
 *  on OpenFreeMap's dark style), instead of leaving it to log a console
 *  warning and render a broken/black tile fill. */
function transparentPlaceholder(): maplibregl.StyleImageInterface {
  return { width: 1, height: 1, data: new Uint8Array(4) };
}

function emptyGeojson(): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: [] };
}

function lineFeature(coords: [number, number][]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: coords } }],
  };
}

// ── Trip planning ──────────────────────────────────────────────────────

type TripStatus = "idle" | "locating" | "searching" | "routing" | "active" | "error";

type TripInfo = { distanceKm: number; durationMin: number; destinationLabel: string };

function getCurrentPosition(): Promise<[number, number]> {
  return new Promise((resolve, reject) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      reject(new Error("Geolocation isn't supported on this device."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve([pos.coords.longitude, pos.coords.latitude]),
      () => reject(new Error("Couldn't access your location — check location permissions.")),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
    );
  });
}

async function geocodeDestination(query: string): Promise<{ point: [number, number]; label: string }> {
  const params = new URLSearchParams({
    q: query,
    format: "json",
    limit: "1",
    countrycodes: "in",
    viewbox: "77.35,13.2,77.95,12.75",
    bounded: "0",
  });
  const res = await fetch(`${NOMINATIM_URL}?${params.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error("Destination search failed — try again.");
  const data = (await res.json()) as Array<{ lat: string; lon: string; display_name: string }>;
  if (!data.length) throw new Error(`Couldn't find "${query}". Try a more specific address.`);
  return { point: [parseFloat(data[0].lon), parseFloat(data[0].lat)], label: data[0].display_name };
}

async function fetchDrivingRoute(
  origin: [number, number],
  destination: [number, number]
): Promise<{ coords: [number, number][]; distanceKm: number; durationMin: number }> {
  const url = `${OSRM_URL}/${origin[0]},${origin[1]};${destination[0]},${destination[1]}?overview=full&geometries=geojson`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("routing_failed");
  const data = await res.json();
  const route = data?.routes?.[0];
  if (!route) throw new Error("routing_failed");
  return {
    coords: route.geometry.coordinates as [number, number][],
    distanceKm: route.distance / 1000,
    durationMin: route.duration / 60,
  };
}

const AMBIENT_LAYERS = [
  "ops-route-glow",
  "ops-route-base",
  "ops-route-flow",
  "ops-vehicles-glow",
  "ops-vehicles-core",
];

export function LiveOpsMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [tilesConfirmed, setTilesConfirmed] = useState(false);
  const [incidentMarkers, setIncidentMarkers] = useState<IncidentMarker[]>(
    INCIDENTS.map((coordinates, index) => ({
      id: `seed-${index}`,
      coordinates,
    }))
  );

  // Trip state
  const [destinationInput, setDestinationInput] = useState("");
  const [tripStatus, setTripStatus] = useState<TripStatus>("idle");
  const [tripError, setTripError] = useState<string | null>(null);
  const [tripInfo, setTripInfo] = useState<TripInfo | null>(null);

  const introRafRef = useRef(0);
  const originMarkerRef = useRef<maplibregl.Marker | null>(null);
  const destMarkerRef = useRef<maplibregl.Marker | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const prefersReducedMotion =
      typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Always boot on the cheap ambient camera (modest zoom/pitch) so the
    // initial tile request is small and "load" fires fast and reliably.
    // The cinematic close-up is a *flyTo* after load, not the starting
    // camera — an animated approach streams tiles in progressively along
    // the path, whereas opening directly on a steep, high-zoom horizon
    // shot can make the very first tile batch huge enough that "load"
    // takes many seconds (or longer) to fire on a cold/slow connection.
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: CENTER,
      zoom: 11.4,
      minZoom: 9,
      maxZoom: 19,
      pitch: 30,
      bearing: 0,
      attributionControl: false,
    });
    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");

    let raf = 0;
    let dashStep = 0;
    let settleTimer: ReturnType<typeof setTimeout> | null = null;
    let introTimer1: ReturnType<typeof setTimeout> | null = null;
    let introTimer2: ReturnType<typeof setTimeout> | null = null;
    let introTimer3: ReturnType<typeof setTimeout> | null = null;
    const vehicles: Vehicle[] = [];

    map.on("styleimagemissing", (e) => {
      if (map.hasImage(e.id)) return;
      map.addImage(e.id, transparentPlaceholder());
    });

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    map.on("load", () => {
      map.resize();

      // ── Real 3D buildings (extruded from OpenMapTiles building footprints) ──
      if (map.getLayer("building")) {
        map.setLayoutProperty("building", "visibility", "none");
      }
      map.addLayer({
        id: "ops-3d-buildings",
        source: "openmaptiles",
        "source-layer": "building",
        type: "fill-extrusion",
        minzoom: 12.5,
        paint: {
          "fill-extrusion-color": [
            "interpolate",
            ["linear"],
            ["coalesce", ["get", "render_height"], ["get", "height"], 15],
            0, "#1c2420",
            40, "#27352c",
            120, "#33433a",
          ],
          "fill-extrusion-height": buildingsHeightExpression(prefersReducedMotion ? 1 : 0),
          "fill-extrusion-base": [
            "coalesce",
            ["get", "render_min_height"],
            ["get", "min_height"],
            0,
          ],
          "fill-extrusion-opacity": 0.88,
        },
      });

      // ── Moody night sky + a "sun" that slowly orbits the skyline,
      // sweeping directional light across the extruded buildings ───────
      map.setSky({
        "sky-color": "#02050a",
        "horizon-color": "#0c241d",
        "sky-horizon-blend": 0.7,
        "atmosphere-blend": 0.6,
      });
      map.setLight({ anchor: "map", color: "#bfe9ff", intensity: 0.55, position: [1.4, 210, 35] });

      // ── Cinematic intro flythrough: dive in from the ambient overview
      // into a close 3D skyline shot with buildings rising from flat
      // footprints, hold briefly, then pull back out. Skipped for
      // prefers-reduced-motion (buildings already at full height). ──────
      if (!prefersReducedMotion) {
        introTimer1 = setTimeout(() => {
          map.flyTo({ center: CENTER, zoom: 16.2, pitch: 70, bearing: -35, duration: 2400, curve: 1.3, speed: 0.85, essential: true });
        }, 200);
        introTimer2 = setTimeout(() => {
          animateBuildingGrowth(map, 1500, (id) => {
            introRafRef.current = id;
          });
        }, 2300);
        introTimer3 = setTimeout(() => {
          map.flyTo({ center: CENTER, zoom: 11.4, pitch: 30, bearing: 0, duration: 2600, curve: 1.4, speed: 0.9, essential: true });
        }, 4800);
      }

      // ── Route sources (data-driven color: lime/cyan per route) ───────
      const routeFeatures = ROUTES.map((r, i) => ({
        type: "Feature" as const,
        properties: { id: i, color: r.color },
        geometry: { type: "LineString" as const, coordinates: r.coords },
      }));

      map.addSource("ops-routes", {
        type: "geojson",
        data: { type: "FeatureCollection", features: routeFeatures },
      });

      map.addLayer({
        id: "ops-route-glow",
        type: "line",
        source: "ops-routes",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ["get", "color"],
          "line-width": 11,
          "line-opacity": 0.28,
          "line-blur": 7,
        },
      });

      map.addLayer({
        id: "ops-route-base",
        type: "line",
        source: "ops-routes",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ["get", "color"],
          "line-width": 2.6,
          "line-opacity": 0.55,
        },
      });

      map.addLayer({
        id: "ops-route-flow",
        type: "line",
        source: "ops-routes",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#f4ffe0",
          "line-width": 3,
          "line-opacity": 1,
        },
      });

      // ── Pulsing markers ────────────────────────────────────────────
      map.addImage("pulse-lime", makePulsingDot(map, "205, 255, 80", 1800), { pixelRatio: 2 });
      map.addImage("pulse-amber", makePulsingDot(map, "255, 153, 0", 2200), { pixelRatio: 2 });
      map.addImage("pulse-red", makePulsingDot(map, "229, 62, 62", 1400), { pixelRatio: 2 });

      map.addSource("ops-stations", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: BENGALURU_STATIONS.map((s) => ({
            type: "Feature" as const,
            properties: { kind: s.type },
            geometry: { type: "Point" as const, coordinates: [s.longitude, s.latitude] },
          })),
        },
      });

      map.addLayer({
        id: "ops-stations",
        type: "symbol",
        source: "ops-stations",
        layout: {
          "icon-image": ["match", ["get", "kind"], "police_station", "pulse-lime", "pulse-amber"],
          "icon-allow-overlap": true,
          "icon-size": 0.55,
        },
      });

      map.addSource("ops-incidents", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: incidentMarkers.map((marker) => ({
            type: "Feature" as const,
            properties: { id: marker.id },
            geometry: { type: "Point" as const, coordinates: marker.coordinates },
          })),
        },
      });

      map.addLayer({
        id: "ops-incidents",
        type: "symbol",
        source: "ops-incidents",
        layout: { "icon-image": "pulse-red", "icon-allow-overlap": true, "icon-size": 0.65 },
      });

      // ── Moving vehicles ────────────────────────────────────────────
      ROUTES.forEach((r, i) => {
        vehicles.push(buildVehicle(r, 0.00007 + i * 0.00001, (i * 0.21) % 1));
        vehicles.push(buildVehicle(r, 0.00006, (i * 0.21 + 0.5) % 1));
      });

      map.addSource("ops-vehicles", { type: "geojson", data: emptyGeojson() });

      map.addLayer({
        id: "ops-vehicles-glow",
        type: "circle",
        source: "ops-vehicles",
        paint: { "circle-radius": 12, "circle-color": ["get", "color"], "circle-opacity": 0.3, "circle-blur": 1 },
      });

      map.addLayer({
        id: "ops-vehicles-core",
        type: "circle",
        source: "ops-vehicles",
        paint: {
          "circle-radius": 3.6,
          "circle-color": "#ffffff",
          "circle-stroke-color": ["get", "color"],
          "circle-stroke-width": 1.8,
        },
      });

      // ── Trip route layers (hidden/empty until a trip is planned) ───
      map.addSource("trip-route-full", { type: "geojson", data: emptyGeojson() });
      map.addSource("trip-route-progress", { type: "geojson", data: emptyGeojson() });

      map.addLayer({
        id: "trip-route-full-glow",
        type: "line",
        source: "trip-route-full",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": CYAN, "line-width": 9, "line-opacity": 0.18, "line-blur": 6 },
      });
      map.addLayer({
        id: "trip-route-full-base",
        type: "line",
        source: "trip-route-full",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#9fb8bd", "line-width": 3, "line-opacity": 0.55, "line-dasharray": [0.2, 1.6] },
      });
      map.addLayer({
        id: "trip-route-progress-glow",
        type: "line",
        source: "trip-route-progress",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": LIME, "line-width": 13, "line-opacity": 0.4, "line-blur": 8 },
      });
      map.addLayer({
        id: "trip-route-progress-base",
        type: "line",
        source: "trip-route-progress",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#f4ffe0", "line-width": 4.5, "line-opacity": 1 },
      });

      // ── Animation loop ─────────────────────────────────────────────
      const dashSequence: number[][] = [
        [0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0],
        [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5],
      ];

      let last = performance.now();
      let lastLightUpdate = 0;
      const tick = (now: number) => {
        const dt = now - last;
        last = now;

        const newStep = Math.floor((now / 55) % dashSequence.length);
        if (newStep !== dashStep && map.getLayer("ops-route-flow")) {
          map.setPaintProperty("ops-route-flow", "line-dasharray", dashSequence[newStep]);
          dashStep = newStep;
        }

        // slowly orbiting "sun" — sweeps directional light across the
        // extruded skyline (full revolution roughly every 70s)
        if (now - lastLightUpdate > 220) {
          lastLightUpdate = now;
          const azimuth = (now / 1000) * 5.1;
          map.setLight({ anchor: "map", color: "#bfe9ff", intensity: 0.55, position: [1.4, azimuth % 360, 35] });
        }

        const features = vehicles.map((v) => {
          v.t += v.speed * dt;
          if (v.t >= 1) v.t -= 1;
          const { point } = positionAlong(v.route, v.cum, v.total, v.t);
          return { type: "Feature" as const, properties: { color: v.color }, geometry: { type: "Point" as const, coordinates: point } };
        });
        const src = map.getSource("ops-vehicles") as maplibregl.GeoJSONSource | undefined;
        src?.setData({ type: "FeatureCollection", features });

        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);

      // Reaching "load" already means the style fetched and parsed
      // successfully — that's the failure mode this fallback guards
      // against (OpenFreeMap unreachable). Individual tile 404s beyond
      // data coverage (common at the intro's steep, far-horizon pitch)
      // are normal and shouldn't keep the CSS scene up forever.
      settleTimer = setTimeout(() => setTilesConfirmed(true), 900);
    });

    return () => {
      cancelAnimationFrame(raf);
      cancelAnimationFrame(introRafRef.current);
      if (settleTimer) clearTimeout(settleTimer);
      if (introTimer1) clearTimeout(introTimer1);
      if (introTimer2) clearTimeout(introTimer2);
      if (introTimer3) clearTimeout(introTimer3);
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
    };
    // Initialization effect must only run once on mount to avoid destroying the map instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const src = map.getSource("ops-incidents") as maplibregl.GeoJSONSource | undefined;
    if (!src) return;
    src.setData({
      type: "FeatureCollection",
      features: incidentMarkers.map((marker) => ({
        type: "Feature" as const,
        properties: { id: marker.id },
        geometry: { type: "Point" as const, coordinates: marker.coordinates },
      })),
    });
  }, [incidentMarkers]);

  useEffect(() => {
    const handleIncident = (event: Event) => {
      const detail = (event as CustomEvent<{ incident_id?: string; latitude?: number | null; longitude?: number | null }>).detail;
      if (!detail?.incident_id || detail.latitude == null || detail.longitude == null) return;
      setIncidentMarkers((current) => {
        if (current.some((marker) => marker.id === detail.incident_id)) return current;
        return [...current, { id: detail.incident_id as string, coordinates: [detail.longitude as number, detail.latitude as number] }];
      });
    };
    window.addEventListener("sentinel:new-incident", handleIncident);
    return () => window.removeEventListener("sentinel:new-incident", handleIncident);
  }, []);

  const setAmbientVisibility = useCallback((visible: boolean) => {
    const map = mapRef.current;
    if (!map) return;
    AMBIENT_LAYERS.forEach((id) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    });
  }, []);

  const clearTrip = useCallback(() => {
    const map = mapRef.current;
    originMarkerRef.current?.remove();
    destMarkerRef.current?.remove();
    originMarkerRef.current = null;
    destMarkerRef.current = null;
    if (map) {
      (map.getSource("trip-route-full") as maplibregl.GeoJSONSource | undefined)?.setData(emptyGeojson());
      (map.getSource("trip-route-progress") as maplibregl.GeoJSONSource | undefined)?.setData(emptyGeojson());
      setAmbientVisibility(true);
      map.flyTo({ center: CENTER, zoom: 11.4, pitch: 30, bearing: 0, duration: 1600 });
    }
    setTripStatus("idle");
    setTripError(null);
    setTripInfo(null);
    setDestinationInput("");
  }, [setAmbientVisibility]);

  const planTrip = useCallback(async () => {
    const map = mapRef.current;
    if (!map || !destinationInput.trim()) return;
    if (!map.getSource("trip-route-full") || !map.getSource("trip-route-progress")) {
      setTripStatus("error");
      setTripError("Map is still loading — try again in a moment.");
      return;
    }

    setTripError(null);
    setTripInfo(null);
    setTripStatus("locating");

    let origin: [number, number];
    try {
      origin = await getCurrentPosition();
    } catch {
      origin = CENTER; // fall back to the city center so the demo still works without location access
    }

    setTripStatus("searching");
    let destination: [number, number];
    let destinationLabel = destinationInput.trim();
    try {
      const geocoded = await geocodeDestination(destinationInput.trim());
      destination = geocoded.point;
      destinationLabel = geocoded.label;
    } catch (err) {
      setTripStatus("error");
      setTripError(err instanceof Error ? err.message : "Couldn't find that destination.");
      return;
    }

    setTripStatus("routing");
    let routeCoords: [number, number][];
    let distanceKm: number;
    let durationMin: number;
    try {
      const route = await fetchDrivingRoute(origin, destination);
      routeCoords = route.coords;
      distanceKm = route.distanceKm;
      durationMin = route.durationMin;
    } catch {
      // OSRM unreachable — fall back to a smoothed straight line so the
      // feature still demonstrates the route/camera experience.
      routeCoords = origin[0] === destination[0] && origin[1] === destination[1] ? [origin] : smoothRoute([origin, destination]);
      distanceKm = haversineKm(origin, destination);
      durationMin = (distanceKm / 35) * 60; // assume ~35km/h average city pace
    }

    if (routeCoords.length < 2) {
      setTripStatus("error");
      setTripError("That destination is too close to your current location.");
      return;
    }

    setAmbientVisibility(false);

    // Just draw the path — the full route, drawn once, no moving puck or
    // chase camera. "trip-route-progress" is left empty so only the dimmer
    // "full" line layers are visible.
    (map.getSource("trip-route-full") as maplibregl.GeoJSONSource | undefined)?.setData(lineFeature(routeCoords));
    (map.getSource("trip-route-progress") as maplibregl.GeoJSONSource | undefined)?.setData(lineFeature(routeCoords));

    const originEl = document.createElement("div");
    originEl.className = "ops-trip-marker ops-trip-marker--origin";
    originEl.innerHTML = `<span class="ops-trip-marker-pulse"></span><span class="ops-trip-marker-core"></span>`;
    originMarkerRef.current?.remove();
    originMarkerRef.current = new maplibregl.Marker({ element: originEl, anchor: "center" }).setLngLat(origin).addTo(map);

    const destEl = document.createElement("div");
    destEl.className = "ops-trip-marker ops-trip-marker--dest";
    destEl.innerHTML = `<span class="ops-trip-marker-pin"></span>`;
    destMarkerRef.current?.remove();
    destMarkerRef.current = new maplibregl.Marker({ element: destEl, anchor: "bottom" }).setLngLat(destination).addTo(map);

    // Fit the whole route on screen and leave it there — no flyTo chase.
    const bounds = routeCoords.reduce(
      (b, c) => b.extend(c),
      new maplibregl.LngLatBounds(routeCoords[0], routeCoords[0])
    );
    map.fitBounds(bounds, { padding: { top: 170, bottom: 140, left: 60, right: 60 }, pitch: 0, bearing: 0, duration: 1000 });

    setTripInfo({ distanceKm, durationMin, destinationLabel });
    setTripStatus("active");
  }, [destinationInput, setAmbientVisibility]);

  return (
    <>
      <div ref={containerRef} className="ops-map-canvas" />
      <MapFallbackScene hidden={tilesConfirmed} />
      <TripPlanner
        destinationInput={destinationInput}
        onDestinationInputChange={setDestinationInput}
        status={tripStatus}
        error={tripError}
        info={tripInfo}
        onPlan={planTrip}
        onClear={clearTrip}
      />
    </>
  );
}

function TripPlanner({
  destinationInput,
  onDestinationInputChange,
  status,
  error,
  info,
  onPlan,
  onClear,
}: {
  destinationInput: string;
  onDestinationInputChange: (value: string) => void;
  status: TripStatus;
  error: string | null;
  info: TripInfo | null;
  onPlan: () => void;
  onClear: () => void;
}) {
  const isBusy = status === "locating" || status === "searching" || status === "routing";
  const hasTrip = status === "active" || isBusy;

  const statusLabel =
    status === "locating"
      ? "Finding your location…"
      : status === "searching"
      ? "Searching destination…"
      : status === "routing"
      ? "Plotting route…"
      : null;

  return (
    <div className="ops-trip-bar" role="search">
      <form
        className="ops-trip-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (!isBusy) onPlan();
        }}
      >
        <span className="ops-trip-icon" aria-hidden="true">
          ⌖
        </span>
        <input
          className="ops-trip-input"
          type="text"
          placeholder="Where are you headed? (e.g. MG Road, Bengaluru)"
          value={destinationInput}
          onChange={(e) => onDestinationInputChange(e.target.value)}
          disabled={isBusy}
        />
        {hasTrip ? (
          <button type="button" className="ops-trip-clear" onClick={onClear} aria-label="Clear route">
            ✕
          </button>
        ) : null}
        <button type="submit" className="ops-trip-go" disabled={isBusy || !destinationInput.trim()}>
          {isBusy ? "…" : "Go"}
        </button>
      </form>

      {statusLabel ? <div className="ops-trip-status">{statusLabel}</div> : null}
      {error ? <div className="ops-trip-status ops-trip-status--error">{error}</div> : null}

      {info ? (
        <div className="ops-trip-info">
          <span className="ops-trip-info-dest">{info.destinationLabel.split(",").slice(0, 2).join(", ")}</span>
          <span className="ops-trip-info-stats">
            {info.distanceKm.toFixed(1)} km · {Math.round(info.durationMin)} min
          </span>
        </div>
      ) : null}

    </div>
  );
}

/**
 * Pure CSS/SVG ambient scene shown on top of the live map until tiles are
 * confirmed loaded. Gives the same "alive emergency ops" read (grid roads,
 * glowing dots, animated curved routes) even if OpenFreeMap is unreachable.
 */
function MapFallbackScene({ hidden }: { hidden: boolean }) {
  return (
    <div className={`ops-fallback${hidden ? " ops-fallback--hidden" : ""}`} aria-hidden="true">
      <div className="ops-fallback-grid" />
      <svg className="ops-fallback-svg" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice">
        <path
          className="ops-fallback-route ops-fallback-route--lime"
          d="M120,560 C260,480 320,620 460,520 S 680,420 760,500 880,560 1040,460"
        />
        <path
          className="ops-fallback-route ops-fallback-route--cyan"
          d="M180,180 C320,260 380,140 520,220 S 760,300 860,210 1000,150 1100,260"
        />
        <path
          className="ops-fallback-route ops-fallback-route--lime"
          d="M300,720 C420,620 540,700 660,600 S 860,520 980,620 1080,700 1140,640"
        />
        <path
          className="ops-fallback-route ops-fallback-route--cyan"
          d="M60,360 C200,320 260,420 400,380 S 620,300 700,400 840,460 960,380"
        />
        {[
          [180, 560], [460, 520], [760, 500], [1040, 460],
          [320, 260], [520, 220], [860, 210],
          [660, 600], [980, 620],
          [260, 420], [700, 400],
        ].map(([cx, cy], i) => (
          <circle
            key={i}
            className={`ops-fallback-dot ${i % 3 === 0 ? "ops-fallback-dot--red" : ""}`}
            cx={cx}
            cy={cy}
            r={i % 3 === 0 ? 5 : 4}
            style={{ animationDelay: `${(i % 5) * 0.35}s` }}
          />
        ))}
      </svg>
    </div>
  );
}
