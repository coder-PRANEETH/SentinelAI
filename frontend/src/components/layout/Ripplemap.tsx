"use client";

import React, { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

interface Coordinate {
  lat: number;
  lon: number;
}

interface RippleImpact {
  location: string;
  coordinates: Coordinate;
  time_taken_minutes: number;
  severity: "high" | "medium" | "low";
}

interface StartNode {
  name: string;
  lat: number;
  lon: number;
}

interface RippleMapProps {
  startNode: StartNode;
  rippleData: RippleImpact[];
}

const SEVERITY_COLORS = {
  high: "#ef4444",   // Red for heavy congestion
  medium: "#f97316", // Orange for moderate congestion
  low: "#eab308",    // Yellow for residual delay
  source: "#a855f7"  // Purple for incident epicenter
};

export default function RippleMap({ startNode, rippleData }: RippleMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  
  const [mapReady, setMapReady] = useState(false);
  const [loadingRoutes, setLoadingRoutes] = useState(false);
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center: [startNode.lon, startNode.lat],
      zoom: 12,
      pitch: 35,
    });

    mapRef.current = map;

    map.on("load", () => {
      map.addSource("ripple-roads", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });

      // Primary road visualization layer (varies width and opacity by severity)
      map.addLayer({
        id: "ripple-roads-layer",
        type: "line",
        source: "ripple-roads",
        layout: {
          "line-join": "round",
          "line-cap": "round"
        },
        paint: {
          "line-color": [
            "match",
            ["get", "severity"],
            "high", SEVERITY_COLORS.high,
            "medium", SEVERITY_COLORS.medium,
            "low", SEVERITY_COLORS.low,
            "#ffffff"
          ],
          "line-width": [
            "match",
            ["get", "severity"],
            "high", 6,     // Thicker lines for major blockages
            "medium", 4,   // Medium lines for secondary delays
            "low", 2.5,    // Thinner lines for minor warnings
            3
          ],
          "line-opacity": [
            "match",
            ["get", "severity"],
            "high", 0.95,
            "medium", 0.75,
            "low", 0.45,
            0.6
          ]
        }
      });

      // Underlay glow layer to enrich visual presence
      map.addLayer({
        id: "ripple-roads-glow",
        type: "line",
        source: "ripple-roads",
        layout: {
          "line-join": "round",
          "line-cap": "round"
        },
        paint: {
          "line-color": [
            "match",
            ["get", "severity"],
            "high", SEVERITY_COLORS.high,
            "medium", SEVERITY_COLORS.medium,
            "low", SEVERITY_COLORS.low,
            "#ffffff"
          ],
          "line-width": [
            "match",
            ["get", "severity"],
            "high", 14,
            "medium", 9,
            "low", 5,
            6
          ],
          "line-opacity": 0.2,
          "line-blur": 4
        }
      }, "ripple-roads-layer");

      setMapReady(true);
    });

    return () => {
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const fetchRoadRoutes = async () => {
      setLoadingRoutes(true);
      const features: any[] = [];

      try {
        const routePromises = rippleData.map(async (item) => {
          const url = `https://router.project-osrm.org/route/v1/driving/${startNode.lon},${startNode.lat};${item.coordinates.lon},${item.coordinates.lat}?overview=full&geometries=geojson`;
          
          try {
            const res = await fetch(url);
            const data = await res.json();
            
            if (data.routes && data.routes.length > 0) {
              features.push({
                type: "Feature",
                properties: {
                  severity: item.severity,
                  location: item.location
                },
                geometry: data.routes[0].geometry
              });
            } else {
              throw new Error("Route not found");
            }
          } catch (err) {
            // Straight line fallback
            features.push({
              type: "Feature",
              properties: {
                severity: item.severity,
                location: item.location
              },
              geometry: {
                type: "LineString",
                coordinates: [
                  [startNode.lon, startNode.lat],
                  [item.coordinates.lon, item.coordinates.lat]
                ]
              }
            });
          }
        });

        await Promise.all(routePromises);

        const source = map.getSource("ripple-roads") as maplibregl.GeoJSONSource;
        if (source) {
          source.setData({
            type: "FeatureCollection",
            features
          });
        }

        updateMapMarkers();

      } catch (error) {
        console.error("Error setting routes on map:", error);
      } finally {
        setLoadingRoutes(false);
      }
    };

    fetchRoadRoutes();

  }, [rippleData, startNode, mapReady]);

  const updateMapMarkers = () => {
    const map = mapRef.current;
    if (!map) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    // Epicenter Marker
    const epicenterEl = document.createElement("div");
    epicenterEl.className = "relative flex items-center justify-center w-8 h-8";
    epicenterEl.innerHTML = `
      <div class="absolute w-8 h-8 bg-purple-500 rounded-full opacity-30 animate-ping"></div>
      <div class="absolute w-5 h-5 bg-purple-600 rounded-full border-2 border-white shadow-xl"></div>
    `;
    const epicenterMarker = new maplibregl.Marker({ element: epicenterEl })
      .setLngLat([startNode.lon, startNode.lat])
      .addTo(map);
    markersRef.current.push(epicenterMarker);

    // Ripple Markers with delays proportional to their delays
    rippleData.forEach((item) => {
      const color = SEVERITY_COLORS[item.severity];
      // Time-delay scaled animation delay
      const animationDelay = item.time_taken_minutes * 0.08;

      const markerEl = document.createElement("div");
      markerEl.className = "relative flex items-center justify-center cursor-pointer group";
      markerEl.style.width = "40px";
      markerEl.style.height = "40px";
      markerEl.innerHTML = `
        <div class="ripple-wave absolute rounded-full" style="--ripple-color: ${color}; --ripple-delay: ${animationDelay}s"></div>
        <div class="ripple-wave absolute rounded-full" style="--ripple-color: ${color}; --ripple-delay: ${animationDelay + 1.0}s"></div>
        <div class="w-3.5 h-3.5 rounded-full border-2 border-white shadow-lg z-10 transition-transform group-hover:scale-125" style="background-color: ${color}"></div>
      `;

      markerEl.addEventListener("click", () => {
        setSelectedLocation(item.location);
        map.easeTo({
          center: [item.coordinates.lon, item.coordinates.lat],
          zoom: 13,
          duration: 900
        });
      });

      const marker = new maplibregl.Marker({ element: markerEl })
        .setLngLat([item.coordinates.lon, item.coordinates.lat])
        .addTo(map);
      markersRef.current.push(marker);
    });

    if (rippleData.length > 0) {
      const lons = [startNode.lon, ...rippleData.map((d) => d.coordinates.lon)];
      const lats = [startNode.lat, ...rippleData.map((d) => d.coordinates.lat)];
      
      map.fitBounds([Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)], {
        padding: { top: 60, bottom: 60, left: 340, right: 60 },
        maxZoom: 13,
        duration: 1200
      });
    }
  };

  return (
    <div className="relative w-full h-[650px] rounded-xl overflow-hidden border border-neutral-800 bg-neutral-950">
      <div ref={mapContainerRef} className="w-full h-full" />

      {loadingRoutes && (
        <div className="absolute inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-20">
          <div className="flex items-center space-x-3 bg-neutral-900 border border-neutral-800 px-5 py-3 rounded-lg text-sm shadow-2xl">
            <svg className="animate-spin h-5 w-5 text-orange-500" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span className="text-neutral-300 font-medium">Re-calculating Bengaluru arterial ripple...</span>
          </div>
        </div>
      )}

      {/* Control Panel Layer Info */}
      <div className="absolute top-4 left-4 z-10 w-[300px] bg-neutral-900/95 backdrop-blur-md p-4 rounded-xl border border-neutral-800/80 text-neutral-200 shadow-2xl flex flex-col max-h-[580px]">
        <div className="mb-3">
          <h4 className="font-semibold text-sm text-white tracking-wide uppercase">Bengaluru Traffic Ripple</h4>
          <p className="text-[11px] text-neutral-400 mt-0.5">
            Epicenter: <span className="text-purple-400 font-semibold">{startNode.name}</span>
          </p>
        </div>

        {/* Dynamic Legend */}
        <div className="grid grid-cols-3 gap-1 mb-3 text-[10px] bg-neutral-950/60 p-2 rounded border border-neutral-800/50">
          <div className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded bg-red-500 inline-block"></span>
            <span className="text-neutral-300">High (0-15m)</span>
          </div>
          <div className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded bg-orange-500 inline-block"></span>
            <span className="text-neutral-300">Med (15-30m)</span>
          </div>
          <div className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded bg-yellow-500 inline-block"></span>
            <span className="text-neutral-300">Low (30m+)</span>
          </div>
        </div>

        {/* Junction List */}
        <div className="space-y-1.5 overflow-y-auto flex-1 pr-1 custom-scrollbar">
          {rippleData.map((item) => (
            <div 
              key={item.location}
              className={`p-2 rounded border cursor-pointer transition-all text-xs flex justify-between items-center ${
                selectedLocation === item.location 
                  ? "bg-neutral-800 border-neutral-600 shadow-md" 
                  : "bg-neutral-950/40 border-neutral-800/60 hover:bg-neutral-800/30"
              }`}
              onClick={() => {
                setSelectedLocation(item.location);
                mapRef.current?.easeTo({
                  center: [item.coordinates.lon, item.coordinates.lat],
                  zoom: 13.5,
                  duration: 800
                });
              }}
            >
              <div className="space-y-0.5">
                <div className="font-semibold text-neutral-200">{item.location}</div>
                <div className="text-[10px] text-neutral-400 flex items-center space-x-1">
                  <span>Wave Arrival:</span>
                  <span className="font-semibold text-neutral-300">+{item.time_taken_minutes} mins</span>
                </div>
              </div>
              <span 
                className="px-1.5 py-0.5 rounded text-[8px] font-bold tracking-wider uppercase inline-block border"
                style={{ 
                  backgroundColor: `${SEVERITY_COLORS[item.severity]}15`, 
                  color: SEVERITY_COLORS[item.severity],
                  borderColor: `${SEVERITY_COLORS[item.severity]}30`
                }}
              >
                {item.severity}
              </span>
            </div>
          ))}
        </div>
      </div>

      <style jsx global>{`
        .ripple-wave {
          width: 40px;
          height: 40px;
          border: 1.5px solid var(--ripple-color);
          background-color: var(--ripple-color);
          opacity: 0;
          animation: rippleEffect 2.4s infinite cubic-bezier(0.16, 1, 0.3, 1);
          animation-delay: var(--ripple-delay, 0s);
        }

        @keyframes rippleEffect {
          0% {
            transform: scale(0.1);
            opacity: 0.75;
            background-color: var(--ripple-color);
          }
          50% {
            background-color: transparent;
          }
          100% {
            transform: scale(2.2);
            opacity: 0;
            border-color: transparent;
          }
        }
        
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: rgba(0,0,0,0.1);
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255,255,255,0.1);
          border-radius: 2px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255,255,255,0.2);
        }
      `}</style>
    </div>
  );
}