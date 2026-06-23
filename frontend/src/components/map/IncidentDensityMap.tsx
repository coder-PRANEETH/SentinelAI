'use client';
import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Incident } from '@/lib/api';

const MAP_CONFIG = {
  // Ultra-stable CartoDB dark matter style (Requires no tokens)
  style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  center: [77.5946, 12.9716] as [number, number],
  zoom: 11,
  pitch: 40,
  minZoom: 9,
  maxZoom: 18,
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

  // Initialize Map
  useEffect(() => {
    if (!mapContainer.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_CONFIG.style,
      center: MAP_CONFIG.center,
      zoom: MAP_CONFIG.zoom,
      pitch: MAP_CONFIG.pitch,
      minZoom: MAP_CONFIG.minZoom,
      maxZoom: MAP_CONFIG.maxZoom,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    mapRef.current = map;

    // Handle ResizeObserver logic cleanly to avoid loop limits in Next.js
    let resizeTimer: ReturnType<typeof setTimeout> | null = null;
    const resizeObserver = new ResizeObserver(() => {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (mapRef.current) mapRef.current.resize();
      }, 100);
    });
    resizeObserver.observe(mapContainer.current);

    // Setup global hover card
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

  // Update Heatmap Sources and Interactive Layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapLoaded) return;

    const sourceId = 'incidents-heat';
    const layerId = 'incidents-heatmap';
    const hoverLayerId = 'incidents-hover'; // Hidden interaction layer

    const geojsonData = {
      type: 'FeatureCollection',
      features: incidents
        .filter((i) => i.latitude && i.longitude)
        .map((i) => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [Number(i.longitude), Number(i.latitude)] },
          properties: { 
            weight: 1, 
            incident_id: i.incident_id,
            incident_type: i.incident_type || 'Unspecified Incident',
            corridor: i.corridor || i.location || 'Local area'
          },
        })),
    };

    // Safely add or update Map Sources
    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: 'geojson',
        data: geojsonData as any,
      });
    } else {
      (map.getSource(sourceId) as maplibregl.GeoJSONSource).setData(geojsonData as any);
    }

    // Add Heatmap Layer
    if (!map.getLayer(layerId)) {
      map.addLayer({
        id: layerId,
        type: 'heatmap',
        source: sourceId,
        maxzoom: 16,
        paint: {
          'heatmap-weight': ['interpolate', ['linear'], ['coalesce', ['get', 'weight'], 1], 1, 0.3, 10, 1.0],
          'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 16, 3],
          'heatmap-color': [
            'interpolate',
            ['linear'],
            ['heatmap-density'],
            0, 'rgba(0,0,0,0)',
            0.1, 'rgba(0, 102, 255, 0.4)',
            0.3, 'rgba(0, 200, 150, 0.6)',
            0.6, 'rgb(255, 221, 0)',
            0.8, 'rgb(255, 140, 0)',
            1.0, 'rgb(220, 20, 20)',
          ],
          'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 10, 9, 24, 16, 50],
          'heatmap-opacity': 0.8,
        },
      });
    }

    // Add Hidden Circle Layer solely to support precise mouse interaction coordinates
    if (!map.getLayer(hoverLayerId)) {
      map.addLayer({
        id: hoverLayerId,
        type: 'circle',
        source: sourceId,
        paint: {
          'circle-radius': 14,
          'circle-color': 'rgba(255, 255, 255, 0.01)', // Almost invisible
          'circle-stroke-width': 0
        },
      });
    }

    let hoverTimeout: ReturnType<typeof setTimeout>;

  const onMouseMove = (e: maplibregl.MapMouseEvent) => {
      // Fix: Capture a local immutable reference to satisfy TypeScript build strictness
      const container = mapContainer.current;
      if (!container) return;

      clearTimeout(hoverTimeout);
      hoverTimeout = setTimeout(() => {
        // Query the robust circle vector layer instead of the custom rasterized heatmap layer
        const features = map.queryRenderedFeatures(e.point, { layers: [hoverLayerId] });
        
        if (features.length === 0) {
          if (hoverCardRef.current) hoverCardRef.current.style.opacity = '0';
          return;
        }

        const props = features[0].properties;
        const totalInCluster = features.length;
        
        const categoryLabel = props.incident_type || 'Unspecified';
        const locationName = props.corridor || 'Bengaluru Corridor';

        if (hoverCardRef.current) {
          hoverCardRef.current.innerHTML = `
            <div style="
              background: rgba(17, 17, 17, 0.9);
              backdrop-filter: blur(8px);
              border: 1px solid rgba(255, 255, 255, 0.15);
              border-radius: 10px;
              padding: 10px 14px;
              width: max-content;
              box-shadow: 0 6px 24px rgba(0,0,0,0.5);
              font-family: system-ui, -apple-system, sans-serif;
              display: flex;
              flex-direction: column;
              gap: 4px;
            ">
              <div style="font-size:12px; font-weight:600; color:#FFFFFF;">
                ${locationName}
              </div>
              <div style="display: flex; gap: 8px; align-items: center; margin-top: 2px;">
                <span style="font-size:10px; font-weight:700; color:#FF3366; background: rgba(255,51,102,0.15); padding: 2px 6px; border-radius: 4px;">
                  ${categoryLabel}
                </span>
                ${totalInCluster > 1 ? `
                  <span style="font-size:10px; color:#A0A0A0;">
                    +${totalInCluster - 1} nearby
                  </span>
                ` : ''}
              </div>
            </div>
          `;

          // Using the immutable local variable here prevents compiler build worker crashes
          const rect = container.getBoundingClientRect();
          let left = rect.left + e.point.x + 15;
          let top = rect.top + e.point.y + 15;

          // Stay within viewport limits
          if (left + 220 > window.innerWidth) left = rect.left + e.point.x - 235;
          if (top + 80 > window.innerHeight) top = rect.top + e.point.y - 95;

          hoverCardRef.current.style.left = `${left}px`;
          hoverCardRef.current.style.top = `${top}px`;
          hoverCardRef.current.style.opacity = '1';
        }
      }, 50);
    };

    const onMouseLeave = () => {
      clearTimeout(hoverTimeout);
      if (hoverCardRef.current) {
        hoverCardRef.current.style.opacity = '0';
      }
    };

    map.on('mousemove', hoverLayerId, onMouseMove);
    map.on('mouseleave', hoverLayerId, onMouseLeave);

    return () => {
      clearTimeout(hoverTimeout);
      try {
        // Ensure the map reference is still active and styled before removing event listeners
        if (mapRef.current && map.getStyle() && map.getLayer(hoverLayerId)) {
          map.off('mousemove', hoverLayerId, onMouseMove);
          map.off('mouseleave', hoverLayerId, onMouseLeave);
        }
      } catch (e) {
        // Map style was already unloaded or map was removed; safely ignore
      }
    };
  }, [incidents, isMapLoaded]);

  return (
    <div className="map-container" style={{ height, flex: 1, position: 'relative', width: '100%' }}>
      <div ref={mapContainer} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', borderRadius: '12px' }} />
      
      {/* Legend Block */}
      <div style={{
        position: 'absolute', bottom: '24px', right: '24px',
        background: 'rgba(17, 17, 17, 0.9)', backdropFilter: 'blur(8px)',
        border: '1px solid #333333', borderRadius: '10px', padding: '10px 14px',
        boxShadow: '0 4px 20px rgba(0,0,0,0.5)', zIndex: 10,
        display: 'flex', flexDirection: 'column', gap: '6px'
      }}>
        <span style={{ fontSize: '10px', fontWeight: 600, color: '#A0A0A0', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Incident Density
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '10px', color: '#6B7280' }}>Low</span>
          <div style={{
            width: '100px', height: '6px', borderRadius: '3px',
            background: 'linear-gradient(to right, rgba(0, 102, 255, 0.4), rgba(0, 200, 150, 0.6), rgb(255, 221, 0), rgb(255, 140, 0), rgb(220, 20, 20))'
          }} />
          <span style={{ fontSize: '10px', color: '#6B7280' }}>High</span>
        </div>
      </div>
    </div>
  );
}