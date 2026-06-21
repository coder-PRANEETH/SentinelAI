'use client';
import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Incident } from '@/lib/api';

const MAP_CONFIG = {
  style: 'https://tiles.openfreemap.org/styles/dark',
  center: [77.5946, 12.9716] as [number, number],
  zoom: 12,
  pitch: 60,
  bearing: -20,
  minZoom: 10,
  maxZoom: 20,
};

interface IncidentDensityMapProps {
  incidents: Incident[];
  height?: string;
}

export function IncidentDensityMap({ incidents = [], height = '480px' }: IncidentDensityMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const hoverCardRef = useRef<HTMLDivElement | null>(null);
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
      map.resize();
      setIsMapLoaded(true);

      if (map.getLayer('building')) {
        map.setLayoutProperty('building', 'visibility', 'none');
      }

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
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapLoaded || !map.isStyleLoaded()) return;

    const sourceId = 'incidents-heat';
    const layerId = 'incidents-heatmap';

    const geojsonData = {
      type: 'FeatureCollection',
      features: incidents
        .filter(i => i.latitude && i.longitude)
        .map(i => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [Number(i.longitude), Number(i.latitude)] },
          properties: { weight: 1, incident_id: i.incident_id }
        }))
    };

    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: 'geojson',
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        data: geojsonData as any,
        cluster: true,
        clusterMaxZoom: 15,
        clusterRadius: 40
      });
    } else {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (map.getSource(sourceId) as maplibregl.GeoJSONSource).setData(geojsonData as any);
    }

    if (!map.getLayer(layerId)) {
      const styleLayers = map.getStyle().layers;
      const firstSymbolId = styleLayers?.find(l => l.type === 'symbol')?.id;

      map.addLayer({
        id: layerId,
        type: 'heatmap',
        source: sourceId,
        maxzoom: 17,
        paint: {
          'heatmap-weight': [
            'interpolate', ['linear'], ['coalesce', ['get', 'point_count'], 1],
            1, 0.2,
            10, 0.6,
            50, 1.0
          ],
          'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 17, 3],
          'heatmap-color': [
            'interpolate', ['linear'], ['heatmap-density'],
            0,     'rgba(0,0,0,0)',
            0.01,  'rgba(0, 102, 255, 0.5)',
            0.05,  'rgba(0, 200, 150, 0.7)',
            0.2,   'rgb(255, 221, 0)',
            0.5,   'rgb(255, 140, 0)',
            1,     'rgb(220, 20, 20)'
          ],
          'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 12, 9, 30, 17, 65],
          'heatmap-opacity': 0.85
        }
      }, firstSymbolId);
    }

    let hoverTimeout: ReturnType<typeof setTimeout>;

    const onMouseMove = (e: maplibregl.MapMouseEvent) => {
      if (!mapContainer.current) return;

      clearTimeout(hoverTimeout);
      hoverTimeout = setTimeout(() => {
        const heatFeatures = map.queryRenderedFeatures(e.point, { layers: [layerId] });
        if (heatFeatures.length === 0) {
          if (hoverCardRef.current && hoverCardRef.current.dataset.source === 'heatmap') {
            hoverCardRef.current.style.opacity = '0';
          }
          return;
        }

        const radiusPx = 40;
        const localIncidents = incidents.filter(inc => {
          if (!inc.latitude || !inc.longitude) return false;
          const px = map.project([inc.longitude, inc.latitude]);
          const dx = px.x - e.point.x;
          const dy = px.y - e.point.y;
          return Math.sqrt(dx * dx + dy * dy) <= radiusPx;
        });

        if (localIncidents.length > 0) {
          const total = localIncidents.length;
          const categories: Record<string, number> = {};
          localIncidents.forEach(inc => {
            const type = inc.incident_type || 'Other';
            categories[type] = (categories[type] || 0) + 1;
          });

          const topCategories = Object.entries(categories)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3)
            .map(([cat, count]) => `<span style="color:#A0A0A0;font-size:11px;background:rgba(255,255,255,0.05);padding:2px 6px;border-radius:4px;">${count} ${cat}</span>`)
            .join('');

          const locationName = localIncidents[0].corridor || localIncidents[0].location || 'Local Area';

          if (hoverCardRef.current) {
            hoverCardRef.current.dataset.source = 'heatmap';
            hoverCardRef.current.innerHTML = `
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
                  <span style="font-size:13px;font-weight:600;color:#FFFFFF;">
                    ${locationName}
                  </span>
                  <span style="background:rgba(255,51,102,0.2);color:#FF3366;font-size:10px;font-weight:700;padding:3px 8px;border-radius:9999px;">
                    ${total} INCIDENT${total > 1 ? 'S' : ''}
                  </span>
                </div>
                ${topCategories ? `<div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 2px;">${topCategories}</div>` : ''}
              </div>
            `;

            const rect = mapContainer.current.getBoundingClientRect();
            let left = rect.left + e.point.x + 15;
            let top = rect.top + e.point.y + 15;
            
            if (left + 220 > window.innerWidth) left = rect.left + e.point.x - 235;
            if (top + 100 > window.innerHeight) top = rect.top + e.point.y - 115;

            hoverCardRef.current.style.left = `${left}px`;
            hoverCardRef.current.style.top = `${top}px`;
            hoverCardRef.current.style.opacity = '1';
          }
        }
      }, 40);
    };

    const onMouseLeave = () => {
      clearTimeout(hoverTimeout);
      if (hoverCardRef.current && hoverCardRef.current.dataset.source === 'heatmap') {
        hoverCardRef.current.style.opacity = '0';
      }
    };

    map.on('mousemove', layerId, onMouseMove);
    map.on('mouseleave', layerId, onMouseLeave);

    return () => {
      clearTimeout(hoverTimeout);
      map.off('mousemove', layerId, onMouseMove);
      map.off('mouseleave', layerId, onMouseLeave);
    };
  }, [incidents, isMapLoaded]);

  return (
    <div className="map-container" style={{ height, flex: 1, position: 'relative', width: '100%', margin: 0, padding: 0, border: 'none' }}>
      <div ref={mapContainer} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', borderRadius: '12px' }} />
      
      <div style={{
        position: 'absolute', bottom: '24px', right: '24px',
        background: 'rgba(17, 17, 17, 0.85)', backdropFilter: 'blur(8px)',
        border: '1px solid #333333', borderRadius: '12px', padding: '12px 16px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)', zIndex: 10,
        display: 'flex', flexDirection: 'column', gap: '8px'
      }}>
        <span style={{ fontSize: '11px', fontWeight: 600, color: '#A0A0A0', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Incident Density
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#6B7280' }}>Fewer</span>
          <div style={{
            width: '120px', height: '8px', borderRadius: '4px',
            background: 'linear-gradient(to right, rgba(0, 102, 255, 0.6), rgba(0, 200, 150, 0.7), rgb(255, 221, 0), rgb(255, 140, 0), rgb(220, 20, 20))'
          }} />
          <span style={{ fontSize: '11px', color: '#6B7280' }}>More</span>
        </div>
      </div>
    </div>
  );
}
