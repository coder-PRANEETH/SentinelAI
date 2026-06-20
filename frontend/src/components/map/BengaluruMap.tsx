'use client';
import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Station, RiskZone, Incident } from '@/lib/api';

/**
 * BengaluruMap — Mapbox GL JS implementation.
 * Style: light-v11 (professional, NOT satellite, NOT dark/cyber)
 * PROHIBITED: neon, glow, bright heatmaps, animated particles
 *
 * Layers (all toggleable):
 * - Station markers (color-coded by readiness)
 * - Incident pins (color-coded by priority, clustered)
 * - Heatmap (risk zones, muted amber/red)
 * - Risk zone polygons
 * - Dispatch route line
 *
 * Set NEXT_PUBLIC_MAPBOX_TOKEN in .env.local
 */

function createStationMarker(readinessScore: number): HTMLElement {
  const color =
    readinessScore > 70  ? '#CDFF50' : // Neon Lime
    readinessScore >= 40 ? '#FF9900' : // Neon Orange
    '#FF3366';                         // Neon Pink/Red

  const wrapper = document.createElement('div');
  wrapper.style.cssText = `
    position: relative;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  `;

  // Soft neon glow
  const glow = document.createElement('div');
  glow.style.cssText = `
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: ${color};
    opacity: 0.25;
    filter: blur(4px);
  `;

  // Sharp ring
  const pin = document.createElement('div');
  pin.innerHTML = `
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="10" cy="10" r="8" fill="#111111" stroke="${color}" stroke-width="2.5" />
      <circle cx="10" cy="10" r="3" fill="${color}" />
    </svg>
  `;
  pin.style.cssText = `
    position: relative;
    z-index: 1;
    line-height: 0;
  `;

  wrapper.appendChild(glow);
  wrapper.appendChild(pin);
  return wrapper;
}

const PRIORITY_COLORS: Record<string, string> = {
  P1: '#FF3366', // Critical — Red
  P2: '#FF9900', // High — Orange
  P3: '#FFCC00', // Medium — Yellow
  P4: '#00E5FF', // Low — Cyan
};

// In-progress gets a distinctive blue
const STATUS_COLOR_OVERRIDE: Record<string, string> = {
  IN_PROGRESS: '#3B82F6',
};

function getIncidentColor(priority: string, status?: string): string {
  if (status && STATUS_COLOR_OVERRIDE[status]) return STATUS_COLOR_OVERRIDE[status];
  return PRIORITY_COLORS[priority] ?? '#6B7280';
}

// Inject pulse keyframe once into document
if (typeof document !== 'undefined') {
  const styleId = 'sentinel-pulse-style';
  if (!document.getElementById(styleId)) {
    const s = document.createElement('style');
    s.id = styleId;
    s.textContent = `
      @keyframes sentinelPulse {
        0%   { transform: scale(0.8); opacity: 0.8; }
        50%  { transform: scale(1.6); opacity: 0.2; }
        100% { transform: scale(0.8); opacity: 0.0; }
      }
    `;
    document.head.appendChild(s);
  }
}

function createIncidentMarker(priority: string, status?: string): HTMLElement {
  const color = getIncidentColor(priority, status);
  const isP1 = priority === 'P1';

  const wrapper = document.createElement('div');
  wrapper.style.cssText = `
    position: relative;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  `;

  // Pulsing halo — faster for P1
  const pulse = document.createElement('div');
  pulse.style.cssText = `
    position: absolute;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: ${color};
    opacity: 0.7;
    animation: sentinelPulse ${isP1 ? '1.0s' : '2.2s'} ease-out infinite;
  `;

  // Static ring
  const ring = document.createElement('div');
  ring.style.cssText = `
    position: absolute;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 2.5px solid ${color};
    background: rgba(17,17,17,0.9);
  `;

  // Center dot
  const dot = document.createElement('div');
  dot.style.cssText = `
    position: absolute;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: ${color};
    z-index: 1;
  `;

  wrapper.appendChild(pulse);
  wrapper.appendChild(ring);
  wrapper.appendChild(dot);
  return wrapper;
}

const PRIORITY_BG: Record<string, string> = {
  P1: '#FEE2E2', P2: '#FEF3C7', P3: '#FEF9C3', P4: '#DBEAFE',
};
const PRIORITY_TEXT: Record<string, string> = {
  P1: '#DC2626', P2: '#D97706', P3: '#CA8A04', P4: '#2563EB',
};

function renderIncidentCard(incident: {
  incident_id: string;
  incident_type: string;
  corridor: string;
  predicted_priority?: string;
  status: string;
}): string {
  const priority = incident.predicted_priority || 'P4';
  const bg = PRIORITY_BG[priority] ?? '#F3F4F6';
  const text = PRIORITY_TEXT[priority] ?? '#374151';

  return `
    <div style="
      background: white;
      border: 1px solid #E5E5E5;
      border-radius: 14px;
      padding: 12px 16px;
      width: max-content;
      box-shadow: 0 8px 24px rgba(0,0,0,0.12);
      font-family: Inter, system-ui, sans-serif;
      display: flex;
      align-items: center;
      gap: 16px;
    ">
      <!-- ID -->
      <span style="font-size:11px;color:#9CA3AF;font-weight:500;white-space:nowrap;letter-spacing:0.03em">
        ${incident.incident_id}
      </span>

      <!-- Type -->
      <span style="font-size:13px;font-weight:600;color:#111111;white-space:nowrap">
        ${incident.incident_type}
      </span>

      <!-- Corridor -->
      <span style="font-size:12px;color:#6B7280;white-space:nowrap;flex:1">
        ${incident.corridor || ''}
      </span>

      <!-- Priority badge -->
      <span style="
        background:${bg};
        color:${text};
        font-size:11px;
        font-weight:700;
        padding:3px 10px;
        border-radius:9999px;
        white-space:nowrap;
        letter-spacing:0.03em;
      ">
        ${priority}
      </span>

      <!-- Status -->
      <span style="font-size:11px;color:#6B7280;white-space:nowrap;font-weight:500">
        ${(incident.status || 'UNKNOWN').replace(/_/g, ' ')}
      </span>
    </div>
  `;
}

function renderStationCard(station: {
  station_name: string;
  readiness_score: number;
  available_officers: number;
  available_vehicles: number;
  active_incidents: number;
}): string {
  const readColor =
    station.readiness_score > 70  ? '#16A34A' :
    station.readiness_score >= 40 ? '#EA580C' : '#DC2626';

  return `
    <div style="
      background: white;
      border: 1px solid #E5E5E5;
      border-radius: 14px;
      padding: 12px 16px;
      width: max-content;
      min-width: 260px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.12);
      font-family: Inter, system-ui, sans-serif;
    ">
      <div style="font-size:13px;font-weight:600;color:#111111;margin-bottom:8px">
        ${station.station_name}
      </div>
      <div style="display:flex;align-items:center;gap:16px">
        <div style="display:flex;flex-direction:column;align-items:center">
          <span style="font-size:18px;font-weight:700;color:${readColor}">
            ${Math.round(station.readiness_score)}
          </span>
          <span style="font-size:10px;color:#9CA3AF;font-weight:500">READINESS</span>
        </div>
        <div style="width:1px;height:28px;background:#E5E5E5"></div>
        <div style="display:flex;flex-direction:column;align-items:center">
          <span style="font-size:16px;font-weight:600;color:#111">${station.available_officers}</span>
          <span style="font-size:10px;color:#9CA3AF">OFFICERS</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center">
          <span style="font-size:16px;font-weight:600;color:#111">${station.available_vehicles}</span>
          <span style="font-size:10px;color:#9CA3AF">VEHICLES</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center">
          <span style="font-size:16px;font-weight:600;color:#111">${station.active_incidents}</span>
          <span style="font-size:10px;color:#9CA3AF">ACTIVE</span>
        </div>
      </div>
    </div>
  `;
}

const MAP_CONFIG = {
  style: 'https://tiles.openfreemap.org/styles/dark',
  center: [77.5946, 12.9716] as [number, number],
  zoom: 15,
  pitch: 60,
  bearing: -20,
  minZoom: 10,
  maxZoom: 20,
};

interface BengaluruMapProps {
  stations?: Station[];
  incidents?: Incident[];
  riskZones?: RiskZone[];
  onStationClick?: (station: Station) => void;
  onIncidentClick?: (incident: Incident) => void;
  height?: string;
  showLayerControls?: boolean;
}

export function BengaluruMap({
  stations = [],
  incidents = [],
  riskZones = [],
  onStationClick,
  onIncidentClick,
  height = '480px',
  showLayerControls = true,
}: BengaluruMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const hoverCardRef = useRef<HTMLDivElement | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const incidentMarkersRef = useRef<maplibregl.Marker[]>([]);

  const [layers, setLayers] = useState({
    stations: false,
    incidents: true,
    heatmap: false,
    coverage: false,
  });
  const [isMapLoaded, setIsMapLoaded] = useState(false);

  useEffect(() => {
    if (!mapContainer.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_CONFIG.style,
      center: MAP_CONFIG.center,
      zoom: MAP_CONFIG.zoom,
      pitch: MAP_CONFIG.pitch,
      bearing: MAP_CONFIG.bearing,
      minZoom: MAP_CONFIG.minZoom,
      maxZoom: MAP_CONFIG.maxZoom,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    mapRef.current = map;

    // Handle missing sprites in the OpenFreeMap style (e.g. wood-pattern)
    map.on('styleimagemissing', (e) => {
      if (e.id === 'wood-pattern') {
        const canvas = document.createElement('canvas');
        canvas.width = 1;
        canvas.height = 1;
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.fillStyle = 'rgba(0, 0, 0, 0)';
          ctx.fillRect(0, 0, 1, 1);
          const imgData = ctx.getImageData(0, 0, 1, 1);
          map.addImage('wood-pattern', imgData);
        }
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      map.resize();
    });
    resizeObserver.observe(mapContainer.current);

    if (!hoverCardRef.current) {
      const hoverCard = document.createElement('div');
      hoverCard.style.cssText = `
        position: fixed;
        z-index: 99999;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.15s ease;
        transform: translate(-50%, calc(-100% - 16px));
      `;
      document.body.appendChild(hoverCard);
      hoverCardRef.current = hoverCard;
    }

    map.on('move', () => {
      if (hoverCardRef.current) hoverCardRef.current.style.opacity = '0';
    });

    map.on('load', () => {
      setIsMapLoaded(true);

      // Hide default 2D building layer if it exists
      if (map.getLayer('building')) {
        map.setLayoutProperty('building', 'visibility', 'none');
      }

      // Add a 3D extruded building layer
      const isDark = MAP_CONFIG.style.includes('dark');
      map.addLayer({
        id: '3d-buildings',
        source: 'openmaptiles',
        'source-layer': 'building',
        type: 'fill-extrusion',
        minzoom: 13,
        paint: {
          'fill-extrusion-color': isDark ? '#2C2C2C' : '#EAEAEA',
          'fill-extrusion-height': [
            'coalesce',
            ['get', 'render_height'],
            ['get', 'height'],
            15,
          ],
          'fill-extrusion-base': [
            'coalesce',
            ['get', 'render_min_height'],
            ['get', 'min_height'],
            0,
          ],
          'fill-extrusion-opacity': 0.65,
        },
      });

      // ── Risk heatmap source (muted, professional) ──
      if (riskZones.length > 0) {
        map.addSource('risk-zones', {
          type: 'geojson',
          data: {
            type: 'FeatureCollection',
            features: riskZones.map(z => ({
              type: 'Feature',
              geometry: { type: 'Point', coordinates: [77.5946, 12.9716] }, // placeholder — actual corridor centroids
              properties: { risk_score: z.risk_score, corridor: z.corridor },
            })),
          },
        });

        map.addLayer({
          id: 'risk-heatmap',
          type: 'heatmap',
          source: 'risk-zones',
          layout: { visibility: 'none' },
          paint: {
            'heatmap-weight': ['interpolate', ['linear'], ['get', 'risk_score'], 0, 0, 100, 1],
            'heatmap-intensity': 0.8,
            'heatmap-radius': 40,
            'heatmap-color': [
              'interpolate', ['linear'], ['heatmap-density'],
              0, 'rgba(0,0,0,0)',
              0.4, 'rgba(246,173,85,0.35)',
              0.8, 'rgba(229,62,62,0.5)',
              1, 'rgba(229,62,62,0.65)',
            ],
            'heatmap-opacity': 0.7,
          },
        });
      }
    });

    return () => {
      resizeObserver.disconnect();
      if (hoverCardRef.current && hoverCardRef.current.parentNode) {
        hoverCardRef.current.parentNode.removeChild(hoverCardRef.current);
        hoverCardRef.current = null;
      }
      markersRef.current.forEach(m => m.remove());
      incidentMarkersRef.current.forEach(m => m.remove());
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Update station markers when stations change ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapLoaded || !map.isStyleLoaded()) return;

    // Clear existing markers
    markersRef.current.forEach(m => m.remove());
    markersRef.current = [];

    if (!layers.stations) return;

    stations.forEach(station => {
      if (!station.latitude || !station.longitude) return;

      if (!station.latitude || !station.longitude) return;
      const score = Number(station.readiness_score);
      const el = createStationMarker(score);

      const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([station.longitude!, station.latitude!])
        .addTo(map);

      el.addEventListener('mouseenter', () => {
        if (!hoverCardRef.current || !mapContainer.current) return;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        hoverCardRef.current.innerHTML = renderStationCard(station as any);
        const point = map.project([station.longitude!, station.latitude!]);
        const rect = mapContainer.current.getBoundingClientRect();
        
        let left = rect.left + point.x;
        if (left + 150 > window.innerWidth) left = window.innerWidth - 150 - 16;
        if (left - 150 < 0) left = 150 + 16;

        hoverCardRef.current.style.left = `${left}px`;
        hoverCardRef.current.style.top = `${rect.top + point.y}px`;
        hoverCardRef.current.style.opacity = '1';
      });

      el.addEventListener('mouseleave', () => {
        if (hoverCardRef.current) hoverCardRef.current.style.opacity = '0';
      });

      el.addEventListener('click', () => {
        if (onStationClick) onStationClick(station);
      });

      markersRef.current.push(marker);
    });
  }, [stations, layers.stations, onStationClick, isMapLoaded]);

  // ── Update incident markers when incidents change ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapLoaded || !map.isStyleLoaded()) return;

    incidentMarkersRef.current.forEach(m => m.remove());
    incidentMarkersRef.current = [];

    if (!layers.incidents) return;

    incidents.forEach(inc => {
      if (!inc.latitude || !inc.longitude) return;

      const p = inc.predicted_priority || 'P4';
      const el = createIncidentMarker(p, inc.status);

      const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([inc.longitude, inc.latitude])
        .addTo(map);

      el.addEventListener('mouseenter', () => {
        if (!hoverCardRef.current || !mapContainer.current) return;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        hoverCardRef.current.innerHTML = renderIncidentCard(inc as any);
        const point = map.project([inc.longitude!, inc.latitude!]);
        const rect = mapContainer.current.getBoundingClientRect();

        let left = rect.left + point.x;
        if (left + 220 > window.innerWidth) left = window.innerWidth - 220 - 16;
        if (left - 220 < 0) left = 220 + 16;

        hoverCardRef.current.style.left = `${left}px`;
        hoverCardRef.current.style.top = `${rect.top + point.y}px`;
        hoverCardRef.current.style.opacity = '1';
      });

      el.addEventListener('mouseleave', () => {
        if (hoverCardRef.current) hoverCardRef.current.style.opacity = '0';
      });

      el.addEventListener('click', () => {
        if (onIncidentClick) {
          onIncidentClick(inc);
        } else {
          // Default: navigate to incident detail
          window.location.href = `/incidents/${inc.incident_id}`;
        }
      });

      incidentMarkersRef.current.push(marker);
    });
  }, [incidents, layers.incidents, onIncidentClick, isMapLoaded]);

  // ── Toggle heatmap visibility ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    if (!map.getLayer('risk-heatmap')) return;
    map.setLayoutProperty('risk-heatmap', 'visibility', layers.heatmap ? 'visible' : 'none');
  }, [layers.heatmap]);

  return (
    <div className="map-container" style={{ height, flex: 1, position: 'relative', width: '100%', margin: 0, padding: 0, border: 'none' }}>
      <div ref={mapContainer} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />

      {/* Layer controls */}
      {showLayerControls && (
        <div style={{
          position: 'absolute', bottom: '24px', left: '24px',
          background: '#111111', border: '1px solid #333333',
          borderRadius: '16px', padding: '16px',
          display: 'flex', flexDirection: 'column', gap: '12px',
          boxShadow: '0 10px 40px rgba(0,0,0,0.5)',
          zIndex: 10,
        }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#A0A0A0', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Map Layers
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[
              { key: 'stations', label: 'Station Markers' },
              { key: 'incidents', label: 'Incident Pins' },
              { key: 'heatmap', label: 'Risk Heatmap' },
              { key: 'coverage', label: 'Coverage Radius' },
            ].map(({ key, label }) => (
              <label key={key} className="map-checkbox-row" style={{ color: '#FFFFFF', fontSize: '13px', fontWeight: 500, margin: 0, padding: 0 }}>
                <input
                  type="checkbox"
                  checked={layers[key as keyof typeof layers]}
                  onChange={e => setLayers(l => ({ ...l, [key]: e.target.checked }))}
                  className="map-checkbox"
                />
                {label}
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
