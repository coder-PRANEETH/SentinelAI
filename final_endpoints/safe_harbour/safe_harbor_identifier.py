"""
Kinetic Kerb-Safe Harbor Identifier
=====================================
Spatial clustering engine for identifying historical vehicle resolution locations.

CORE LOGIC:
1. Parse incident data (incident lat/lon vs resolved_at lat/lon)
2. Filter valid resolution deltas (exclude non-breakdown incidents)
3. Perform DBSCAN clustering on resolved_at coordinates
4. Extract cluster centroids, radii, and characteristics
5. Provide operator recommendations with contextual information

COMPONENTS:
- SafeHarborClusterer: Core DBSCAN + geospatial analysis
- SafeHarborStore: In-memory safe harbor database with lookups
- SafeHarborRecommender: Real-time recommendation engine
- SafeHarborVisualizer: GeoJSON + map output
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import math

from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler


@dataclass
class SafeHarbor:
    """Represents a discovered safe harbor location."""
    harbor_id: str
    center_lat: float
    center_lon: float
    radius_meters: float
    num_incidents: int
    cluster_label: int
    vehicle_types: List[str]
    causes: List[str]
    avg_resolution_time_minutes: float
    resolution_locations: List[Dict]  # List of actual resolved_at points
    zone: Optional[str] = None
    junction: Optional[str] = None
    address: Optional[str] = None
    confidence_score: float = 0.0


@dataclass
class HarborRecommendation:
    """Real-time recommendation for an incident."""
    incident_id: str
    incident_lat: float
    incident_lon: float
    nearest_harbor_id: str
    nearest_harbor_lat: float
    nearest_harbor_lon: float
    distance_meters: float
    bearing: float  # Compass direction (0-360°)
    confidence: float  # 0-1 based on cluster density
    recommendation_text: str
    zone: Optional[str] = None
    junction: Optional[str] = None


class GeoUtils:
    """Geospatial utility functions."""
    
    EARTH_RADIUS_KM = 6371.0
    EARTH_RADIUS_M = 6371000.0
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate great-circle distance between two points on Earth.
        Returns: distance in meters
        """
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        
        return GeoUtils.EARTH_RADIUS_M * c
    
    @staticmethod
    def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate compass bearing from point 1 to point 2.
        Returns: bearing in degrees (0-360, where 0 = North)
        """
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlon = lon2_rad - lon1_rad
        
        y = math.sin(dlon) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
        
        bearing_rad = math.atan2(y, x)
        bearing_deg = math.degrees(bearing_rad)
        
        return (bearing_deg + 360) % 360
    
    @staticmethod
    def bearing_to_direction(bearing: float) -> str:
        """Convert bearing (0-360°) to cardinal direction."""
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        idx = int((bearing + 11.25) / 22.5) % 16
        return directions[idx]
    
    @staticmethod
    def lat_lon_to_meters(lat: float, lon: float) -> Tuple[float, float]:
        """Convert lat/lon to pseudo-mercator meters (for clustering)."""
        x = lon * (GeoUtils.EARTH_RADIUS_M * math.pi / 180.0)
        y = GeoUtils.EARTH_RADIUS_M * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
        return x, y
    
    @staticmethod
    def meters_to_lat_lon(x: float, y: float) -> Tuple[float, float]:
        """Convert pseudo-mercator meters back to lat/lon."""
        lon = x * (180.0 / (GeoUtils.EARTH_RADIUS_M * math.pi))
        lat = math.degrees(math.atan(math.sinh(y / GeoUtils.EARTH_RADIUS_M)))
        return lat, lon


class SafeHarborClusterer:
    """
    DBSCAN-based spatial clustering engine.
    
    Parameters:
    - eps_meters: Cluster radius in meters (default 50m for "kerb-safe" zones)
    - min_samples: Minimum points per cluster (default 3 incidents)
    """
    
    def __init__(self, eps_meters: float = 50.0, min_samples: int = 3):
        self.eps_meters = eps_meters
        self.min_samples = min_samples
        self.clusters = {}
        self.incident_data = None
        self.valid_incidents = None
    
    def prepare_incidents(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter incidents with valid resolution data.
        
        Valid = breakdowns (vehicle_breakdown) where resolved_at_latitude/longitude are non-null
        """
        # Filter: only breakdowns with resolution coordinates
        valid = df[
            (df['event_cause'] == 'vehicle_breakdown') &
            (df['resolved_at_latitude'].notna()) &
            (df['resolved_at_longitude'].notna()) &
            (df['resolved_at_latitude'] != 0.0) &
            (df['resolved_at_longitude'] != 0.0)
        ].copy()
        
        # Calculate incident-to-resolution delta
        valid['delta_meters'] = valid.apply(
            lambda row: GeoUtils.haversine_distance(
                row['latitude'], row['longitude'],
                row['resolved_at_latitude'], row['resolved_at_longitude']
            ), axis=1
        )
        
        # Sanity check: delta > 10m and < 5km (actual vehicle movements)
        valid = valid[(valid['delta_meters'] >= 10) & (valid['delta_meters'] <= 5000)]
        
        self.valid_incidents = valid
        return valid
    
    def cluster(self, df: pd.DataFrame) -> Dict[int, SafeHarbor]:
        """
        Execute DBSCAN clustering on resolved_at locations.
        Returns: dict of cluster_label -> SafeHarbor
        """
        # Prepare data
        valid_df = self.prepare_incidents(df)
        
        if len(valid_df) < self.min_samples:
            print(f"⚠️  Only {len(valid_df)} valid incidents. Need ≥{self.min_samples} to cluster.")
            return {}
        
        # Convert lat/lon to meters for distance calculation
        coords = valid_df[['resolved_at_latitude', 'resolved_at_longitude']].values
        coords_meters = np.array([
            GeoUtils.lat_lon_to_meters(lat, lon) for lat, lon in coords
        ])
        
        # Normalize by eps_meters so DBSCAN interprets distances correctly
        scaler = StandardScaler()
        coords_scaled = scaler.fit_transform(coords_meters)
        
        # DBSCAN: eps is in scaled units
        # We need to convert eps_meters to scaled units
        eps_scaled = self.eps_meters / np.mean(np.std(coords_meters, axis=0))
        
        dbscan = DBSCAN(eps=eps_scaled, min_samples=self.min_samples)
        labels = dbscan.fit_predict(coords_scaled)
        
        valid_df['cluster_label'] = labels
        
        # Extract clusters (ignore label -1 = noise)
        self.clusters = {}
        for label in set(labels):
            if label == -1:  # Skip noise
                continue
            
            cluster_data = valid_df[valid_df['cluster_label'] == label]
            harbor = self._create_safe_harbor(label, cluster_data)
            self.clusters[label] = harbor
        
        return self.clusters
    
    def _create_safe_harbor(self, label: int, cluster_data: pd.DataFrame) -> SafeHarbor:
        """Create SafeHarbor object from cluster data."""
        resolved_lats = cluster_data['resolved_at_latitude'].values
        resolved_lons = cluster_data['resolved_at_longitude'].values
        
        # Cluster centroid
        center_lat = np.mean(resolved_lats)
        center_lon = np.mean(resolved_lons)
        
        # Cluster radius: max distance from centroid
        max_dist = max([
            GeoUtils.haversine_distance(center_lat, center_lon, lat, lon)
            for lat, lon in zip(resolved_lats, resolved_lons)
        ])
        
        # Collect resolution locations
        resolution_locations = [
            {
                'latitude': float(row['resolved_at_latitude']),
                'longitude': float(row['resolved_at_longitude']),
                'incident_id': row['id'],
                'date': str(row['resolved_datetime'])
            }
            for _, row in cluster_data.iterrows()
        ]
        
        # Statistics
        vehicle_types = cluster_data['veh_type_grouped'].dropna().unique().tolist()
        causes = cluster_data['event_cause'].dropna().unique().tolist()
        avg_resolution_time = cluster_data['response_time_minutes'].mean() if 'response_time_minutes' in cluster_data.columns else 0.0
        
        # Zone/junction info (most common)
        zone = cluster_data['zone'].mode().values[0] if 'zone' in cluster_data.columns and len(cluster_data['zone'].mode()) > 0 else None
        junction = cluster_data['junction'].mode().values[0] if 'junction' in cluster_data.columns and len(cluster_data['junction'].mode()) > 0 else None
        
        # Confidence score: based on cluster density and consistency
        confidence = min(1.0, len(cluster_data) / 10.0)  # Saturate at 10 incidents
        
        harbor_id = f"SH{label:04d}"
        
        return SafeHarbor(
            harbor_id=harbor_id,
            center_lat=center_lat,
            center_lon=center_lon,
            radius_meters=max_dist,
            num_incidents=len(cluster_data),
            cluster_label=label,
            vehicle_types=vehicle_types,
            causes=causes,
            avg_resolution_time_minutes=float(avg_resolution_time),
            resolution_locations=resolution_locations,
            zone=zone,
            junction=junction,
            confidence_score=confidence
        )


class SafeHarborStore:
    """In-memory database of safe harbors with spatial indexing."""
    
    def __init__(self):
        self.harbors: Dict[str, SafeHarbor] = {}
    
    def add_harbor(self, harbor: SafeHarbor) -> None:
        self.harbors[harbor.harbor_id] = harbor
    
    def add_harbors(self, harbors: Dict[int, SafeHarbor]) -> None:
        for label, harbor in harbors.items():
            self.add_harbor(harbor)
    
    def nearest_harbor(self, lat: float, lon: float, max_distance: float = 2000.0) -> Optional[SafeHarbor]:
        """Find nearest safe harbor within max_distance meters."""
        nearest = None
        nearest_dist = float('inf')
        
        for harbor in self.harbors.values():
            dist = GeoUtils.haversine_distance(lat, lon, harbor.center_lat, harbor.center_lon)
            if dist < nearest_dist and dist <= max_distance:
                nearest = harbor
                nearest_dist = dist
        
        return nearest
    
    def harbors_near(self, lat: float, lon: float, radius: float = 2000.0) -> List[SafeHarbor]:
        """Find all harbors within radius meters."""
        nearby = []
        for harbor in self.harbors.values():
            dist = GeoUtils.haversine_distance(lat, lon, harbor.center_lat, harbor.center_lon)
            if dist <= radius:
                nearby.append(harbor)
        return sorted(nearby, key=lambda h: GeoUtils.haversine_distance(lat, lon, h.center_lat, h.center_lon))
    
    def get_stats(self) -> Dict:
        """Return summary statistics."""
        if not self.harbors:
            return {"total_harbors": 0, "total_incidents": 0}
        
        return {
            "total_harbors": len(self.harbors),
            "total_incidents": sum(h.num_incidents for h in self.harbors.values()),
            "avg_cluster_size": np.mean([h.num_incidents for h in self.harbors.values()]),
            "avg_radius_meters": np.mean([h.radius_meters for h in self.harbors.values()]),
        }


class SafeHarborRecommender:
    """Real-time recommendation engine for incidents."""
    
    def __init__(self, store: SafeHarborStore):
        self.store = store
    
    def recommend(self, incident_id: str, incident_lat: float, incident_lon: float,
                  zone: Optional[str] = None, junction: Optional[str] = None) -> Optional[HarborRecommendation]:
        """Generate recommendation for an incident."""
        nearest = self.store.nearest_harbor(incident_lat, incident_lon, max_distance=2000.0)
        
        if nearest is None:
            return None
        
        distance = GeoUtils.haversine_distance(incident_lat, incident_lon, nearest.center_lat, nearest.center_lon)
        bearing = GeoUtils.bearing(incident_lat, incident_lon, nearest.center_lat, nearest.center_lon)
        direction = GeoUtils.bearing_to_direction(bearing)
        
        # Recommendation text
        rec_text = f"Historical safe harbor: Push vehicle {distance:.0f}m {direction} ({bearing:.0f}°)."
        if nearest.zone:
            rec_text += f" Zone: {nearest.zone}."
        if nearest.junction:
            rec_text += f" Near: {nearest.junction}."
        rec_text += f" {nearest.num_incidents} similar incidents resolved here."
        
        return HarborRecommendation(
            incident_id=incident_id,
            incident_lat=incident_lat,
            incident_lon=incident_lon,
            nearest_harbor_id=nearest.harbor_id,
            nearest_harbor_lat=nearest.center_lat,
            nearest_harbor_lon=nearest.center_lon,
            distance_meters=distance,
            bearing=bearing,
            confidence=nearest.confidence_score,
            recommendation_text=rec_text,
            zone=zone,
            junction=junction
        )


class SafeHarborVisualizer:
    """Generate GeoJSON and visualization data."""
    
    @staticmethod
    def to_geojson(harbors: Dict[str, SafeHarbor]) -> Dict:
        """Convert harbors to GeoJSON FeatureCollection."""
        features = []
        
        for harbor in harbors.values():
            # Center point
            feature = {
                "type": "Feature",
                "id": harbor.harbor_id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [harbor.center_lon, harbor.center_lat]
                },
                "properties": {
                    "harbor_id": harbor.harbor_id,
                    "num_incidents": harbor.num_incidents,
                    "radius_meters": harbor.radius_meters,
                    "vehicle_types": harbor.vehicle_types,
                    "zone": harbor.zone,
                    "junction": harbor.junction,
                    "confidence": harbor.confidence_score,
                    "avg_resolution_time": harbor.avg_resolution_time_minutes
                }
            }
            features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features
        }
    
    @staticmethod
    def resolution_locations_geojson(harbor: SafeHarbor) -> Dict:
        """GeoJSON of all resolution points in a harbor."""
        features = []
        
        for loc in harbor.resolution_locations:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [loc['longitude'], loc['latitude']]
                },
                "properties": {
                    "incident_id": loc['incident_id'],
                    "date": loc['date']
                }
            }
            features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Load dataset
    print("📍 Loading incident data...")
    df = pd.read_csv('/home/claude/astram_sample.csv')
    
    print(f"Total records: {len(df)}")
    print(f"Columns: {df.columns.tolist()}\n")
    
    # Initialize clusterer
    print("🔧 Initializing Safe Harbor Clusterer (eps=50m, min_samples=3)...")
    clusterer = SafeHarborClusterer(eps_meters=50.0, min_samples=3)
    
    # Cluster
    print("⚙️  Clustering resolution locations...")
    harbors = clusterer.cluster(df)
    
    if harbors:
        print(f"✅ Found {len(harbors)} safe harbors!\n")
        
        # Initialize store
        store = SafeHarborStore()
        store.add_harbors(harbors)
        
        # Print summary
        stats = store.get_stats()
        print(f"📊 Summary Statistics:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
        print()
        
        # Print harbors
        print("🛣️  Safe Harbors:")
        for harbor in sorted(harbors.values(), key=lambda h: -h.num_incidents):
            print(f"\n   {harbor.harbor_id}: {harbor.center_lat:.4f}, {harbor.center_lon:.4f}")
            print(f"      Incidents: {harbor.num_incidents}")
            print(f"      Radius: {harbor.radius_meters:.0f}m")
            print(f"      Vehicles: {', '.join(harbor.vehicle_types)}")
            print(f"      Zone: {harbor.zone} | Junction: {harbor.junction}")
            print(f"      Confidence: {harbor.confidence_score:.2f}")
        
        # Test recommendation
        print("\n\n🎯 Sample Recommendations:")
        recommender = SafeHarborRecommender(store)
        
        # Pick a few test incidents
        test_incidents = df.head(5)
        for _, incident in test_incidents.iterrows():
            rec = recommender.recommend(
                incident_id=incident['id'],
                incident_lat=incident['latitude'],
                incident_lon=incident['longitude'],
                zone=incident.get('zone'),
                junction=incident.get('junction')
            )
            if rec:
                print(f"\n   📍 {rec.incident_id}")
                print(f"      {rec.recommendation_text}")
                print(f"      Confidence: {rec.confidence:.2f}")
        
        # Export GeoJSON
        print("\n\n💾 Exporting GeoJSON...")
        geojson = SafeHarborVisualizer.to_geojson(store.harbors)
        with open('/home/claude/safe_harbors.geojson', 'w') as f:
            json.dump(geojson, f, indent=2)
        print(f"   ✅ Saved: /home/claude/safe_harbors.geojson")
    else:
        print("❌ No clusters found. Check data quality and parameters.")
