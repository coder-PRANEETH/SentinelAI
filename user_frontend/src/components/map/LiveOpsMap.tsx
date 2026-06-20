"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { BENGALURU_STATIONS } from "@/lib/stationsData";

/**
 * LiveOpsMap — a full-screen, ambient "emergency operations" map backdrop for
 * the public landing page. Reuses the same dark OpenFreeMap style as
 * {@link PublicMap}, but is purely decorative (non-interactive) and layered
 * with live activity:
 *   - flowing animated route lines in lime + cyan, curved via spline smoothing
 *   - soft glow lines underneath the routes
 *   - pulsing station markers (lime) + incident markers (red)
 *   - emergency vehicles drifting along the routes (interpolated points)
 *
 * A CSS/SVG "fallback scene" sits on top of the live map and only fades away
 * once MapLibre confirms tiles have actually rendered — if OpenFreeMap is
 * slow/unreachable the page still shows an animated, on-brand scene instead
 * of a blank/black rectangle.
 *
 * Everything runs on a single requestAnimationFrame loop and free tiles —
 * no paid map APIs.
 */

const MAP_STYLE = "https://tiles.openfreemap.org/styles/dark";
const CENTER: [number, number] = [77.615, 12.965];

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
      [77.5946, 12.9716],
      [77.6, 12.96],
      [77.6245, 12.9352],
      [77.6905, 12.9352],
      [77.6974, 12.9591],
    ],
  },
  {
    color: LIME,
    coords: [
      [77.4926, 13.0264],
      [77.554, 13.0218],
      [77.597, 13.0358],
      [77.6412, 12.9719],
      [77.6245, 12.9352],
    ],
  },
  {
    color: LIME,
    coords: [
      [77.5856, 12.9079],
      [77.5938, 12.925],
      [77.5946, 12.9716],
      [77.5468, 12.9255],
      [77.521, 13.0335],
    ],
  },
  {
    color: CYAN,
    coords: [
      [77.6602, 12.8452],
      [77.6245, 12.9352],
      [77.6974, 12.9591],
      [77.7499, 12.9698],
    ],
  },
  {
    color: CYAN,
    coords: [
      [77.62, 12.992],
      [77.658, 12.962],
      [77.621, 12.935],
      [77.668, 12.915],
      [77.715, 12.945],
      [77.76, 12.97],
    ],
  },
  {
    color: CYAN,
    coords: [
      [77.6, 12.905],
      [77.645, 12.932],
      [77.615, 12.958],
      [77.668, 12.978],
      [77.705, 12.95],
      [77.74, 12.985],
    ],
  },
  {
    color: LIME,
    coords: [
      [77.55, 12.95],
      [77.585, 12.975],
      [77.61, 12.94],
      [77.64, 12.97],
      [77.665, 12.935],
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

type Vehicle = {
  route: [number, number][];
  color: string;
  cum: number[]; // cumulative segment lengths
  total: number;
  t: number; // 0..1 progress along the route
  speed: number; // progress per ms
};

function buildVehicle(route: RouteDef, speed: number, offset: number): Vehicle {
  const cum = [0];
  let total = 0;
  for (let i = 1; i < route.coords.length; i++) {
    const dx = route.coords[i][0] - route.coords[i - 1][0];
    const dy = route.coords[i][1] - route.coords[i - 1][1];
    total += Math.hypot(dx, dy);
    cum.push(total);
  }
  return { route: route.coords, color: route.color, cum, total, t: offset, speed };
}

function vehiclePosition(v: Vehicle): [number, number] {
  const dist = v.t * v.total;
  for (let i = 1; i < v.cum.length; i++) {
    if (dist <= v.cum[i]) {
      const segStart = v.cum[i - 1];
      const segLen = v.cum[i] - segStart || 1;
      const f = (dist - segStart) / segLen;
      const a = v.route[i - 1];
      const b = v.route[i];
      return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
    }
  }
  return v.route[v.route.length - 1];
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

      // expanding halo
      ctx.beginPath();
      ctx.arc(size / 2, size / 2, outer, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${rgb}, ${0.45 * (1 - t)})`;
      ctx.fill();

      // solid core + soft outer ring
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

export function LiveOpsMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [tilesConfirmed, setTilesConfirmed] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: CENTER,
      zoom: 11.4,
      minZoom: 9,
      maxZoom: 16,
      pitch: 0,
      bearing: 0,
      interactive: false, // purely ambient backdrop
      attributionControl: false,
    });
    mapRef.current = map;

    let raf = 0;
    let dashStep = 0;
    let settleTimer: ReturnType<typeof setTimeout> | null = null;
    let tileErrorCount = 0;
    const vehicles: Vehicle[] = [];

    // Any sprite image the style references but can't resolve (OpenFreeMap's
    // dark style is known to ask for a "wood-pattern" fill it doesn't ship)
    // gets a transparent placeholder instead of failing/console-warning.
    map.on("styleimagemissing", (e) => {
      if (map.hasImage(e.id)) return;
      map.addImage(e.id, transparentPlaceholder());
    });

    map.on("error", () => {
      tileErrorCount += 1;
    });

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    map.on("load", () => {
      map.resize();

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

      // wide outer glow under the routes
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

      // bright base line (clearly visible even without the flow dashes)
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

      // bright animated dashes flowing along the routes
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
      map.addImage("pulse-lime", makePulsingDot(map, "205, 255, 80", 1800), {
        pixelRatio: 2,
      });
      map.addImage("pulse-amber", makePulsingDot(map, "255, 153, 0", 2200), {
        pixelRatio: 2,
      });
      map.addImage("pulse-red", makePulsingDot(map, "229, 62, 62", 1400), {
        pixelRatio: 2,
      });

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
          "icon-image": [
            "match",
            ["get", "kind"],
            "police_station",
            "pulse-lime",
            "pulse-amber",
          ],
          "icon-allow-overlap": true,
          "icon-size": 0.55,
        },
      });

      map.addSource("ops-incidents", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: INCIDENTS.map((c) => ({
            type: "Feature" as const,
            properties: {},
            geometry: { type: "Point" as const, coordinates: c },
          })),
        },
      });

      map.addLayer({
        id: "ops-incidents",
        type: "symbol",
        source: "ops-incidents",
        layout: {
          "icon-image": "pulse-red",
          "icon-allow-overlap": true,
          "icon-size": 0.65,
        },
      });

      // ── Moving vehicles ────────────────────────────────────────────
      ROUTES.forEach((r, i) => {
        vehicles.push(buildVehicle(r, 0.00007 + i * 0.00001, (i * 0.21) % 1));
        // a second unit further down the line, for denser live movement
        vehicles.push(buildVehicle(r, 0.00006, (i * 0.21 + 0.5) % 1));
      });

      map.addSource("ops-vehicles", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      map.addLayer({
        id: "ops-vehicles-glow",
        type: "circle",
        source: "ops-vehicles",
        paint: {
          "circle-radius": 12,
          "circle-color": ["get", "color"],
          "circle-opacity": 0.3,
          "circle-blur": 1,
        },
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

      // ── Animation loop ─────────────────────────────────────────────
      const dashSequence: number[][] = [
        [0, 4, 3],
        [0.5, 4, 2.5],
        [1, 4, 2],
        [1.5, 4, 1.5],
        [2, 4, 1],
        [2.5, 4, 0.5],
        [3, 4, 0],
        [0, 0.5, 3, 3.5],
        [0, 1, 3, 3],
        [0, 1.5, 3, 2.5],
        [0, 2, 3, 2],
        [0, 2.5, 3, 1.5],
        [0, 3, 3, 1],
        [0, 3.5, 3, 0.5],
      ];

      let last = performance.now();
      const tick = (now: number) => {
        const dt = now - last;
        last = now;

        // flowing dashes
        const newStep = Math.floor((now / 55) % dashSequence.length);
        if (newStep !== dashStep && map.getLayer("ops-route-flow")) {
          map.setPaintProperty("ops-route-flow", "line-dasharray", dashSequence[newStep]);
          dashStep = newStep;
        }

        // advance vehicles
        const features = vehicles.map((v) => {
          v.t += v.speed * dt;
          if (v.t >= 1) v.t -= 1;
          return {
            type: "Feature" as const,
            properties: { color: v.color },
            geometry: { type: "Point" as const, coordinates: vehiclePosition(v) },
          };
        });
        const src = map.getSource("ops-vehicles") as maplibregl.GeoJSONSource | undefined;
        src?.setData({ type: "FeatureCollection", features });

        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);

      // Give tiles a moment to actually paint, then decide whether the live
      // map is healthy enough to reveal (fading the CSS/SVG fallback away).
      settleTimer = setTimeout(() => {
        if (tileErrorCount === 0) setTilesConfirmed(true);
      }, 900);
    });

    return () => {
      cancelAnimationFrame(raf);
      if (settleTimer) clearTimeout(settleTimer);
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <>
      <div ref={containerRef} className="ops-map-canvas" aria-hidden="true" />
      <MapFallbackScene hidden={tilesConfirmed} />
    </>
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
