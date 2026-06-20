/**
 * Bundled fallback coordinates for well-known Bengaluru traffic/police
 * stations and safe stopping points.
 *
 * TODO: The authenticated operator API (`/stations` on the backend, port
 * 5001) holds the live, authoritative station list with coordinates and
 * resource counts — but it requires an operator JWT, which public users
 * don't have. Once a public read-only stations endpoint exists, replace
 * this bundled list with a live fetch in `lib/api.ts`.
 */
export interface StaticStation {
  name: string;
  type: "police_station" | "safe_stop";
  latitude: number;
  longitude: number;
}

export const BENGALURU_STATIONS: StaticStation[] = [
  { name: "Central Traffic Police Station", type: "police_station", latitude: 12.9716, longitude: 77.5946 },
  { name: "Koramangala Police Station", type: "police_station", latitude: 12.9352, longitude: 77.6245 },
  { name: "Indiranagar Traffic Police Station", type: "police_station", latitude: 12.9719, longitude: 77.6412 },
  { name: "Whitefield Police Station", type: "police_station", latitude: 12.9698, longitude: 77.7499 },
  { name: "JP Nagar Traffic Police Station", type: "police_station", latitude: 12.9079, longitude: 77.5856 },
  { name: "Peenya Police Station", type: "police_station", latitude: 13.0264, longitude: 77.4926 },
  { name: "Electronic City Police Station", type: "police_station", latitude: 12.8452, longitude: 77.6602 },
  { name: "Hebbal Traffic Police Station", type: "police_station", latitude: 13.0358, longitude: 77.5970 },
  { name: "Marathahalli Police Station", type: "police_station", latitude: 12.9591, longitude: 77.6974 },
  { name: "Jayanagar Traffic Police Station", type: "police_station", latitude: 12.9250, longitude: 77.5938 },
  { name: "Yeshwanthpur Police Station", type: "police_station", latitude: 13.0218, longitude: 77.5540 },
  { name: "Banashankari Safe Stop", type: "safe_stop", latitude: 12.9255, longitude: 77.5468 },
  { name: "Outer Ring Road Safe Stop", type: "safe_stop", latitude: 12.9352, longitude: 77.6905 },
  { name: "Tumkur Road Safe Stop", type: "safe_stop", latitude: 13.0335, longitude: 77.5210 },
];
