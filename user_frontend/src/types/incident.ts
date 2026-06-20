export type IncidentTypeId =
  | "car_breakdown"
  | "accident"
  | "road_block"
  | "medical_emergency";

export interface IncidentTypeInfo {
  id: IncidentTypeId;
  label: string;
  description: string;
  icon: string;
  href: string;
}

export const INCIDENT_TYPES: IncidentTypeInfo[] = [
  {
    id: "car_breakdown",
    label: "Car Breakdown",
    description: "Vehicle stalled or broken down on the road",
    icon: "car",
    href: "/report/car-breakdown",
  },
  {
    id: "accident",
    label: "Accident",
    description: "Collision or crash involving vehicles",
    icon: "alert-triangle",
    href: "/report/car-breakdown?type=accident",
  },
  {
    id: "road_block",
    label: "Road Block",
    description: "Obstruction, debris or closure on the road",
    icon: "octagon",
    href: "/report/car-breakdown?type=road_block",
  },
  {
    id: "medical_emergency",
    label: "Medical Emergency",
    description: "Someone needs urgent medical attention",
    icon: "heart-pulse",
    href: "/report/car-breakdown?type=medical_emergency",
  },
];

export interface GeoPoint {
  latitude: number;
  longitude: number;
  accuracy?: number;
}

export interface CarBreakdownReport {
  incidentTypeId: IncidentTypeId;
  vehicleType: string;
  issueType: string;
  description: string;
  phoneNumber?: string;
  location: GeoPoint | null;
}

export interface SafeLocation {
  name: string;
  type: "police_station" | "safe_stop" | "service_point";
  latitude: number;
  longitude: number;
  distanceKm: number;
  etaMinutes: number;
}

export interface IncidentSubmissionResult {
  success: boolean;
  incidentId: string;
  isMock: boolean;
  message: string;
}
