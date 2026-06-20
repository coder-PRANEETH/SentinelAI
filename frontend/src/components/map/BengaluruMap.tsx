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
    readinessScore > 70  ? '#B9E63F' : // High Readiness
    readinessScore >= 40 ? '#EAB308' : // Medium Readiness
    '#E35D5D';                         // Low Readiness

  const wrapper = document.createElement('div');
  wrapper.style.cssText = `
    position: relative;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  `;

  // Sharp ring with white fill
  const pin = document.createElement('div');
  pin.innerHTML = `
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="10" cy="10" r="8" fill="#FFFFFF" stroke="${color}" stroke-width="2.5" />
      <circle cx="10" cy="10" r="3" fill="${color}" />
    </svg>
  `;
  pin.style.cssText = `
    position: relative;
    z-index: 1;
    line-height: 0;
  `;

  wrapper.appendChild(pin);
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
        0%   { transform: scale(0.8); opacity: 0.5; }
        50%  { transform: scale(1.6); opacity: 0.15; }
        100% { transform: scale(0.8); opacity: 0.0; }
      }
    `;
    document.head.appendChild(s);
  }
}

function createIncidentMarker(priority: string, status?: string, isSelected?: boolean): HTMLElement {
  const color = getIncidentColor(priority, status);
  const isP1 = priority === 'P1';

  const wrapper = document.createElement('div');
  const size = isSelected ? 48 : 40;
  wrapper.style.cssText = `
    position: relative;
    width: ${size}px;
    height: ${size}px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  `;

  // Highlight ring if selected
  if (isSelected) {
    const highlight = document.createElement('div');
    highlight.style.cssText = `
      position: absolute;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      border: 3px solid #B9E63F;
      background: transparent;
      z-index: 0;
    `;
    wrapper.appendChild(highlight);
  }

  // Pulsing halo — subtle pulse allowed ONLY for P1
  if (isP1) {
    const pulse = document.createElement('div');
    pulse.style.cssText = `
      position: absolute;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: ${color};
      opacity: 0.3;
      animation: sentinelPulse 2.0s ease-out infinite;
      z-index: 0;
    `;
    wrapper.appendChild(pulse);
  }

  // Static ring
  const ring = document.createElement('div');
  const ringSize = isSelected ? 18 : 14;
  ring.style.cssText = `
    position: absolute;
    width: ${ringSize}px;
    height: ${ringSize}px;
    border-radius: 50%;
    border: 2px solid ${color};
    background: #FFFFFF;
    z-index: 1;
  `;

  // Center dot
  const dot = document.createElement('div');
  const dotSize = isSelected ? 8 : 6;
  dot.style.cssText = `
    position: absolute;
    width: ${dotSize}px;
    height: ${dotSize}px;
    border-radius: 50%;
    background: ${color};
    z-index: 2;
  `;

  wrapper.appendChild(ring);
  wrapper.appendChild(dot);
  return wrapper;
}

const PRIORITY_BG: Record<string, string> = {
  P1: '#FEE2E2', P2: '#FEF3C7', P3: '#EBF7D4', P4: '#F1F5F9',
};
const PRIORITY_TEXT: Record<string, string> = {
  P1: '#E35D5D', P2: '#EAB308', P3: '#7C9E1B', P4: '#64748B',
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
    station.readiness_score > 70  ? '#B9E63F' :
    station.readiness_score >= 40 ? '#EAB308' : '#E35D5D';

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
  style: 'https://tiles.openfreemap.org/styles/positron',
  center: [77.5946, 12.9716] as [number, number],
  zoom: 15,
  pitch: 35,
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
  selectedIncidentId?: string;
}

export function BengaluruMap({
  stations = [],
  incidents = [],
  riskZones = [],
  onStationClick,
  onIncidentClick,
  height = '480px',
  showLayerControls = true,
  selectedIncidentId,
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

    // Apply Command Center Light style rules
    map.on('style.load', () => {
      // Land / Background color
      if (map.getLayer('background')) {
        map.setPaintProperty('background', 'background-color', '#FAFAFA');
      }

      // Water color
      if (map.getLayer('water')) {
        map.setPaintProperty('water', 'fill-color', '#EAF4FF');
      }

      // Road colors
      const roadLayers = [
        'highway_motorway_inner',
        'highway_motorway_casing',
        'highway_major_inner',
        'highway_major_casing',
        'highway_minor',
        'highway_path',
        'road_pier'
      ];
      roadLayers.forEach(id => {
        if (map.getLayer(id)) {
          map.setPaintProperty(id, 'line-color', '#DADADA');
        }
      });

      // Label text colors
      const labelLayers = [
        'place_city_large',
        'place_city',
        'place_town',
        'place_village',
        'place_suburb',
        'place_other',
        'place_state',
        'place_country_major',
        'place_country_minor',
        'place_country_other'
      ];
      labelLayers.forEach(id => {
        if (map.getLayer(id)) {
          map.setPaintProperty(id, 'text-color', '#111111');
        }
      });

      const minorLabelLayers = [
        'highway_name_other',
        'highway_name_motorway',
        'water_name'
      ];
      minorLabelLayers.forEach(id => {
        if (map.getLayer(id)) {
          map.setPaintProperty(id, 'text-color', '#6B7280');
        }
      });
    });

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
          'fill-extrusion-color': isDark ? '#2C2C2C' : '#ECECEC',
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
          'fill-extrusion-opacity': 0.35,
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
              0.4, 'rgba(185,230,63,0.20)', // Low Risk
              0.8, 'rgba(234,179,8,0.25)',  // Medium Risk
              1, 'rgba(227,93,93,0.30)',    // High Risk
            ],
            'heatmap-opacity': 0.6,
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
      const isSelected = inc.incident_id === selectedIncidentId || (incidents.length === 1 && inc.incident_id === incidents[0].incident_id);
      const el = createIncidentMarker(p, inc.status, isSelected);

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
  }, [incidents, layers.incidents, onIncidentClick, isMapLoaded, selectedIncidentId]);

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
          background: '#FFFFFF', border: '1px solid #E5E5E5',
          borderRadius: '16px', padding: '16px',
          display: 'flex', flexDirection: 'column', gap: '12px',
          boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
          zIndex: 10,
        }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#6B7280', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Map Layers
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[
              { key: 'stations', label: 'Station Markers' },
              { key: 'incidents', label: 'Incident Pins' },
              { key: 'heatmap', label: 'Risk Heatmap' },
              { key: 'coverage', label: 'Coverage Radius' },
            ].map(({ key, label }) => (
              <label key={key} className="map-checkbox-row" style={{ color: '#111111', fontSize: '13px', fontWeight: 500, margin: 0, padding: 0 }}>
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
