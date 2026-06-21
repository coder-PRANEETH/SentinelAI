'use client';
import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Station, RiskZone, Incident } from '@/lib/api';

/**
 * BengaluruMap — MapLibre GL JS implementation.
 * Style: dark (OpenFreeMap vector tiles)
 * Props:
 * - highlightedIncidentId: focuses one incident marker (enlarged + bright ring) and flies to it
 * - flyToIncident: auto-center map to first incident on mount (used in detail page)
 *
 * Layers (all toggleable):
 * - Station markers (color-coded by readiness)
 * - Incident pins (color-coded by priority)
 * - Heatmap (risk zones, muted amber/red)
 */

function createStationMarker(readinessScore: number, stationName: string): HTMLElement {
  // Use same thresholds as Stations & Resources page
  const color =
    readinessScore >= 70 ? '#16A34A' : // Green (High)
      readinessScore >= 40 ? '#EA580C' : // Orange (Medium)
        '#DC2626';                       // Red (Low)

  const wrapper = document.createElement('div');
  // NOTE: Do NOT add `transition` here — MapLibre uses CSS transform to position
  // markers, and any transition on transform causes markers to visually drift on pan.
  wrapper.style.cssText = `
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    will-change: transform;
    gap: 4px;
    z-index: 5;
  `;

  // Distinct Shield/Badge shape for station
  const badge = document.createElement('div');
  badge.innerHTML = `
    <svg width="28" height="32" viewBox="0 0 24 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2L3 6V13C3 18.5 7.05 23.74 12 25C16.95 23.74 21 18.5 21 13V6L12 2Z" fill="#111111" stroke="${color}" stroke-width="2.5" stroke-linejoin="round"/>
      <path d="M12 8V18M8 13H16" stroke="${color}" stroke-width="2" stroke-linecap="round"/>
    </svg>
  `;
  badge.style.cssText = `
    position: relative;
    z-index: 1;
    line-height: 0;
    pointer-events: none;
    filter: drop-shadow(0 4px 6px rgba(0,0,0,0.5));
  `;

  // Label under the badge
  const label = document.createElement('div');
  label.textContent = stationName;
  label.style.cssText = `
    background: rgba(17, 17, 17, 0.85);
    color: #FFFFFF;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    border: 1px solid rgba(255,255,255,0.1);
    white-space: nowrap;
    pointer-events: none;
    text-shadow: 0 1px 2px rgba(0,0,0,0.8);
    letter-spacing: 0.02em;
  `;

  wrapper.appendChild(badge);
  wrapper.appendChild(label);
  return wrapper;
}

const PRIORITY_COLORS: Record<string, string> = {
  P1: '#E35D5D',
  P2: '#EAB308',
  P3: '#B9E63F',   // Brand Lime
  P4: '#64748B',
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

function createIncidentMarker(priority: string, status?: string, highlighted = false): HTMLElement {
  const color = getIncidentColor(priority, status);
  const isP1 = priority === 'P1';

  const size = highlighted ? 56 : 44;
  const ringSize = highlighted ? 28 : 20;
  const dotSize = highlighted ? 10 : 7;
  const pulseSize = highlighted ? 40 : 30;
  const ringBorder = highlighted ? '3.5px' : '2.5px';

  const wrapper = document.createElement('div');
  // NOTE: Do NOT add `transition` here — MapLibre uses CSS transform to position
  // markers, and any transition on transform causes markers to visually drift on pan.
  wrapper.style.cssText = `
    position: relative;
    width: ${size}px;
    height: ${size}px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    will-change: transform;
    ${highlighted ? 'filter: drop-shadow(0 0 8px ' + color + ');' : ''}
    z-index: ${highlighted ? 10 : 1};
  `;

  // Pulsing halo — faster for P1 or highlighted
  const pulse = document.createElement('div');
  pulse.style.cssText = `
    position: absolute;
    width: ${pulseSize}px;
    height: ${pulseSize}px;
    border-radius: 50%;
    background: ${color};
    opacity: ${highlighted ? 0.85 : 0.7};
    animation: sentinelPulse ${(isP1 || highlighted) ? '1.0s' : '2.2s'} ease-out infinite;
    pointer-events: none;
  `;

  // Static ring
  const ring = document.createElement('div');
  ring.style.cssText = `
    position: absolute;
    width: ${ringSize}px;
    height: ${ringSize}px;
    border-radius: 50%;
    border: ${ringBorder} solid ${color};
    background: rgba(17,17,17,0.9);
    ${highlighted ? 'box-shadow: 0 0 0 3px ' + color + '44;' : ''}
  `;

  // Center dot
  const dot = document.createElement('div');
  dot.style.cssText = `
    position: absolute;
    width: ${dotSize}px;
    height: ${dotSize}px;
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
  reported_at?: string;
}): string {
  const priority = incident.predicted_priority || 'P4';
  const bg = PRIORITY_BG[priority] ?? 'rgba(255,255,255,0.1)';
  const text = PRIORITY_TEXT[priority] ?? '#FFFFFF';

  // Format date if available
  const dateStr = incident.reported_at ? new Date(incident.reported_at).toLocaleString('en-IN', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  }) : 'Just now';

  return `
    <div style="
      background: rgba(17, 17, 17, 0.85);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 14px;
      padding: 12px 16px;
      width: max-content;
      box-shadow: 0 10px 40px rgba(0,0,0,0.5);
      font-family: Inter, system-ui, sans-serif;
      display: flex;
      flex-direction: column;
      gap: 8px;
    ">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px;">
        <span style="font-size:13px;font-weight:600;color:#FFFFFF;white-space:nowrap">
          ${incident.incident_type}
        </span>
        <span style="
          background:${bg};
          color:${text};
          font-size:10px;
          font-weight:700;
          padding:3px 8px;
          border-radius:9999px;
          white-space:nowrap;
          letter-spacing:0.03em;
        ">
          ${priority}
        </span>
      </div>

      <div style="display: flex; flex-direction: column; gap: 4px;">
        <span style="font-size:12px;color:#A0A0A0;white-space:nowrap">
          ${incident.corridor || 'Unknown location'}
        </span>
        <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 4px;">
          <span style="font-size:11px;color:#6B7280;white-space:nowrap;font-weight:500">
            ${(incident.status || 'UNKNOWN').replace(/_/g, ' ')}
          </span>
          <span style="font-size:11px;color:#6B7280;white-space:nowrap">
            ${dateStr}
          </span>
        </div>
      </div>
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
    station.readiness_score > 70 ? '#16A34A' :
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
  /** ID of the incident to visually highlight (enlarged ring + fly-to). */
  highlightedIncidentId?: string | null;
  /** If true, automatically fly to the first incident with coordinates on load. */
  flyToIncident?: boolean;
}

export function BengaluruMap({
  stations = [],
  incidents = [],
  riskZones = [],
  onStationClick,
  onIncidentClick,
  height = '480px',
  showLayerControls = true,
  highlightedIncidentId = null,
  flyToIncident = false,
}: BengaluruMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const hoverCardRef = useRef<HTMLDivElement | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const incidentMarkersRef = useRef<maplibregl.Marker[]>([]);

  const [layers, setLayers] = useState({
    stations: false,
    incidents: true,
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

    // Debounce resize calls and skip the very first synchronous fire that
    // ResizeObserver emits on observe() — calling resize() before the GL canvas
    // has rendered its first frame corrupts tile loading (black areas on pan).
    let resizeTimer: ReturnType<typeof setTimeout> | null = null;
    let initialFire = true;
    const resizeObserver = new ResizeObserver(() => {
      if (initialFire) {
        initialFire = false;
        return;
      }
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (mapRef.current) mapRef.current.resize();
      }, 50);
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
      // Ensure the map knows its final container size before starting to load tiles.
      // Without this, tiles for newly-panned areas can render as black squares.
      map.resize();
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
    });

    return () => {
      if (resizeTimer) clearTimeout(resizeTimer);
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
    if (!map || !isMapLoaded) return;

    // Clear existing markers
    markersRef.current.forEach(m => m.remove());
    markersRef.current = [];

    if (!layers.stations) return;

    stations.forEach(station => {
      if (!station.latitude || !station.longitude) return;

      if (!station.latitude || !station.longitude) return;
      const score = Number(station.readiness_score);
      const el = createStationMarker(score, station.station_name);

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

        const top = rect.top + point.y;
        if (top < 150) {
          hoverCardRef.current.style.transform = 'translate(-50%, 16px)';
        } else {
          hoverCardRef.current.style.transform = 'translate(-50%, calc(-100% - 16px))';
        }

        hoverCardRef.current.style.left = `${left}px`;
        hoverCardRef.current.style.top = `${top}px`;
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

  // ── Update incident markers when incidents or highlighted ID changes ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapLoaded) return;

    incidentMarkersRef.current.forEach(m => m.remove());
    incidentMarkersRef.current = [];

    if (!layers.incidents) return;

    incidents.forEach(inc => {
      if (!inc.latitude || !inc.longitude) return;

      const p = inc.predicted_priority || 'P4';
      const isHighlighted = highlightedIncidentId === inc.incident_id;
      const el = createIncidentMarker(p, inc.status, isHighlighted);

      const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([Number(inc.longitude), Number(inc.latitude)])
        .addTo(map);

      console.log(`Marker incident ${inc.incident_id}: [${Number(inc.longitude)}, ${Number(inc.latitude)}]`);

      el.addEventListener('mouseenter', () => {
        if (!hoverCardRef.current || !mapContainer.current) return;
        hoverCardRef.current.dataset.source = 'marker';
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        hoverCardRef.current.innerHTML = renderIncidentCard(inc as any);
        const point = map.project([inc.longitude!, inc.latitude!]);
        const rect = mapContainer.current.getBoundingClientRect();

        let left = rect.left + point.x;
        if (left + 220 > window.innerWidth) left = window.innerWidth - 220 - 16;
        if (left - 220 < 0) left = 220 + 16;

        const top = rect.top + point.y;
        if (top < 150) {
          hoverCardRef.current.style.transform = 'translate(-50%, 16px)';
        } else {
          hoverCardRef.current.style.transform = 'translate(-50%, calc(-100% - 16px))';
        }

        hoverCardRef.current.style.left = `${left}px`;
        hoverCardRef.current.style.top = `${top}px`;
        hoverCardRef.current.style.opacity = '1';
      });

      el.addEventListener('mouseleave', () => {
        if (hoverCardRef.current && hoverCardRef.current.dataset.source === 'marker') {
          hoverCardRef.current.style.opacity = '0';
        }
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

    return () => {
    };
  }, [incidents, layers.incidents, onIncidentClick, isMapLoaded, highlightedIncidentId]);

  // ── Fly to highlighted incident ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapLoaded) return;
    if (!highlightedIncidentId) return;

    const target = incidents.find(i => i.incident_id === highlightedIncidentId);
    if (target?.latitude && target?.longitude) {
      map.flyTo({
        center: [target.longitude, target.latitude],
        zoom: Math.max(map.getZoom(), 15),
        duration: 900,
        essential: true,
      });
    }
  }, [highlightedIncidentId, incidents, isMapLoaded]);

  // ── Fly to single incident on initial load (flyToIncident mode) or auto-center ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapLoaded) return;

    const target = incidents.find(i => i.latitude && i.longitude);
    if (target?.latitude && target?.longitude) {
      if (flyToIncident) {
        map.flyTo({
          center: [target.longitude, target.latitude],
          zoom: 16,
          duration: 800,
          essential: true,
        });
      } else if (incidents.length === 1) {
        map.setCenter([target.longitude, target.latitude]);
      }
    }
  }, [flyToIncident, incidents, isMapLoaded]);

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
            <label className="map-checkbox-row" style={{ color: '#FFFFFF', fontSize: '13px', fontWeight: 500, margin: 0, padding: 0, display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={layers.stations}
                onChange={e => setLayers(l => ({ ...l, stations: e.target.checked }))}
                className="map-checkbox"
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <svg width="14" height="16" viewBox="0 0 24 28" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2L3 6V13C3 18.5 7.05 23.74 12 25C16.95 23.74 21 18.5 21 13V6L12 2Z" fill="#111111" stroke="#16A34A" strokeWidth="3" strokeLinejoin="round"/>
                  <path d="M12 8V18M8 13H16" stroke="#16A34A" strokeWidth="2.5" strokeLinecap="round"/>
                </svg>
                Station Markers
              </div>
            </label>
            <label className="map-checkbox-row" style={{ color: '#FFFFFF', fontSize: '13px', fontWeight: 500, margin: 0, padding: 0, display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={layers.incidents}
                onChange={e => setLayers(l => ({ ...l, incidents: e.target.checked }))}
                className="map-checkbox"
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <svg width="14" height="14" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="10" cy="10" r="8" fill="#111111" stroke="#E35D5D" strokeWidth="3" />
                  <circle cx="10" cy="10" r="3" fill="#E35D5D" />
                </svg>
                Incident Pins
              </div>
            </label>
          </div>
        </div>
      )}

    </div>
  );
}
