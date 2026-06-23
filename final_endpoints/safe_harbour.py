import pandas as pd
import numpy as np
import logging
from sklearn.cluster import DBSCAN
from typing import Dict, List, Optional
from threading import Lock

logger = logging.getLogger(__name__)

class KerbSafeHarborIdentifier:
    """
    Kinetic Kerb-Safe Harbor Identifier (Memory-Optimized)
    
    Identifies safe-harbor clustering exclusively for vehicle breakdowns 
    using restricted column parsing to protect memory limits.
    """
    def __init__(self, data_file: str):
        self.data_file = data_file
        self.harbors: List[dict] = []
        self._lock = Lock()
        self._initialized = False

    def initialize(self) -> None:
        """Lazily builds clusters on first query."""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            try:
                import os, pickle
                cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "safe_harbor_cache.pkl")
                if os.path.exists(cache_path):
                    with open(cache_path, "rb") as f:
                        self.harbors = pickle.load(f)
                    self._initialized = True
                    return

                # OPTIMIZATION 1: Only load columns absolutely necessary for clustering
                target_columns = [
                    "latitude", 
                    "longitude", 
                    "resolved_at_latitude", 
                    "resolved_at_longitude", 
                    "resolved_at_address",
                    "event_cause"
                ]

                # Low_memory=True and usecols drastically reduce RAM consumption
                df = pd.read_csv(
                    self.data_file, 
                    usecols=target_columns, 
                    low_memory=True,
                    encoding="latin1"
                )
                
                self._compute_safe_harbors(df)
                self._initialized = True
            except Exception as e:
                logger.error(f"[SafeHarbor] Failed to load optimized data or train model: {e}")
                self.harbors = []

    def _compute_safe_harbors(self, df: pd.DataFrame) -> None:
        # OPTIMIZATION 2: Filter rows immediately. Only process vehicle breakdowns.
        # This discards tree falls, general accidents, and other non-breakdown blockages.
        if "event_cause" in df.columns:
            df["event_cause"] = df["event_cause"].astype(str).str.strip().str.lower()
            df = df[df["event_cause"] == "vehicle_breakdown"].copy()

        if df.empty:
            logger.warning("[SafeHarbor] No vehicle breakdown records found in filtered dataset.")
            return

        # Ensure coordinate columns are purely numeric
        coord_cols = ["latitude", "longitude", "resolved_at_latitude", "resolved_at_longitude"]
        for col in coord_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Select coordinates with actual valid displacement values
        valid_mask = (
            df["latitude"].notna() & (df["latitude"] != 0) &
            df["longitude"].notna() & (df["longitude"] != 0) &
            df["resolved_at_latitude"].notna() & (df["resolved_at_latitude"] != 0) &
            df["resolved_at_longitude"].notna() & (df["resolved_at_longitude"] != 0)
        )
        
        moves_df = df[valid_mask].copy()
        if moves_df.empty:
            return

        # Distance approximation
        lat_delta = moves_df["resolved_at_latitude"] - moves_df["latitude"]
        lon_delta = moves_df["resolved_at_longitude"] - moves_df["longitude"]
        displacement_approx_meters = np.sqrt(lat_delta**2 + lon_delta**2) * 111000

        # Filter out cases resolved in the same lane, keep active pushes/tows
        kinetic_moves = moves_df[
            (displacement_approx_meters >= 10) & 
            (displacement_approx_meters <= 300)
        ].copy()

        if kinetic_moves.empty:
            return

        # Run DBSCAN (50-meter maximum cluster radius)
        earth_radius = 6371000.0
        eps_rad = 50.0 / earth_radius 

        coords_rad = np.radians(kinetic_moves[["resolved_at_latitude", "resolved_at_longitude"]].values)
        
        db = DBSCAN(eps=eps_rad, min_samples=2, metric="haversine")
        kinetic_moves["cluster_label"] = db.fit_predict(coords_rad)

        clusters = kinetic_moves[kinetic_moves["cluster_label"] != -1]

        computed_harbors = []
        for label, group in clusters.groupby("cluster_label"):
            centroid_lat = float(group["resolved_at_latitude"].mean())
            centroid_lon = float(group["resolved_at_longitude"].mean())
            
            address_series = group["resolved_at_address"].dropna()
            best_address = "Road side shoulder"
            if not address_series.empty:
                best_address = max(address_series.unique(), key=len)

            computed_harbors.append({
                "harbor_id": int(label),
                "latitude": centroid_lat,
                "longitude": centroid_lon,
                "address": best_address,
                "historical_frequency": len(group)
            })

        self.harbors = computed_harbors
        logger.info(f"[SafeHarbor] Identified {len(self.harbors)} vehicle breakdown push zones.")

    def find_nearest_harbor(
        self, 
        incident_lat: float, 
        incident_lon: float, 
        max_search_radius_meters: float = 400.0
    ) -> Optional[dict]:
        self.initialize()
        if not self.harbors:
            return None

        best_harbor = None
        min_distance = float("inf")

        for harbor in self.harbors:
            dy = (incident_lat - harbor["latitude"]) * 111000.0
            dx = (incident_lon - harbor["longitude"]) * 111000.0 * np.cos(np.radians(incident_lat))
            dist = np.sqrt(dx*dx + dy*dy)

            if dist < max_search_radius_meters and dist < min_distance:
                min_distance = dist
                best_harbor = {
                    "harbor_address": harbor["address"],
                    "coordinates": {
                        "lat": harbor["latitude"],
                        "lon": harbor["longitude"]
                    },
                    "push_distance_meters": round(dist, 1),
                    "historical_uses": harbor["historical_frequency"]
                }

        return best_harbor