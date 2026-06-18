"""
load_balancer.py
SentinelAI – Station Load Balancer
Given an incident location (corridor/junction), computes readiness scores
for candidate stations and returns a ranked recommendation.
"""

import pandas as pd
from typing import List, Optional, Dict
from resource_tracker import ResourceTracker
from station_readiness import compute_station_loads, compute_readiness_score
from resource_database import STATIONS, DEFAULT_RESOURCES

DATA_FILE = "Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"


class LoadBalancer:
    def __init__(self, data_file: str = DATA_FILE):
        self.tracker = ResourceTracker()
        print("[LoadBalancer] Computing station loads from historical data …")
        self.loads   = compute_station_loads(data_file)

    def _candidate_stations(self, corridor: Optional[str] = None) -> List[str]:
        """
        Filter stations that historically handle the given corridor.
        Falls back to all stations if none found.
        """
        if not corridor:
            return [s for s in STATIONS if s != "No Police Station"]

        df = pd.read_csv(DATA_FILE, encoding="latin1")
        corridor_stations = (
            df[df["corridor"].str.lower() == corridor.lower()]["police_station"]
            .dropna()
            .unique()
            .tolist()
        )
        if len(corridor_stations) >= 2:
            return corridor_stations
        return [s for s in STATIONS if s != "No Police Station"]

    def rank_stations(
        self,
        corridor: Optional[str] = None,
        candidate_stations: Optional[List[str]] = None,
    ) -> List[dict]:
        """Compute and rank readiness scores for candidate stations."""
        if candidate_stations is None:
            candidate_stations = self._candidate_stations(corridor)

        scores = []
        for station in candidate_stations:
            r = compute_readiness_score(station, self.tracker, self.loads)
            scores.append(r)

        scores.sort(key=lambda x: x["readiness_score"], reverse=True)
        return scores

    def select_station(
        self,
        incident_location: str,
        corridor: Optional[str] = None,
        min_officers: int = 1,
        min_vehicles: int = 1,
    ) -> dict:
        """
        Main entry point.  Returns the best station with explanation.

        Parameters
        ----------
        incident_location : Free-text location description
        corridor          : Matched corridor name (e.g. 'Tumkur Road')
        min_officers      : Minimum officers required for the incident
        min_vehicles      : Minimum vehicles required for the incident
        """
        ranked = self.rank_stations(corridor)

        # Filter: must have enough baseline resources
        eligible = [
            r for r in ranked
            if r["available_officers"] >= min_officers
            and r["available_vehicles"] >= min_vehicles
        ]

        if not eligible:
            eligible = ranked  # relax constraint if all stations stretched

        best = eligible[0]

        # Build human-readable recommendation
        reasons = []
        if best["readiness_score"] == max(r["readiness_score"] for r in ranked):
            reasons.append("Highest readiness score")
        if best["active_incidents"] == min(r["active_incidents"] for r in eligible):
            reasons.append("Lowest active load")
        if best["available_officers"] >= min_officers and best["available_vehicles"] >= min_vehicles:
            reasons.append("Sufficient resources available")

        return {
            "incident_location":  incident_location,
            "recommended_station": best["station"],
            "readiness_score":    best["readiness_score"],
            "reason":             reasons,
            "station_details":    best,
            "all_candidates":     [
                {
                    "station":        r["station"],
                    "readiness_pct":  r["readiness_score"],
                    "active":         r["active_incidents"],
                    "officers":       r["available_officers"],
                    "vehicles":       r["available_vehicles"],
                }
                for r in ranked[:8]   # top 8 for display
            ],
        }


# ── Standalone demo ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    lb     = LoadBalancer()
    result = lb.select_station(
        incident_location="Tumkur Road",
        corridor="Tumkur Road",
        min_officers=2,
        min_vehicles=1,
    )
    print(f"\n{'='*60}")
    print(f"  Incident : {result['incident_location']}")
    print(f"{'='*60}")
    print(f"\n  RECOMMENDED -> {result['recommended_station']}")
    print(f"  Readiness   : {result['readiness_score']}%")
    print(f"  Reasons     : {', '.join(result['reason'])}")
    print(f"\n  Top Candidates:")
    for c in result["all_candidates"]:
        bar = "#" * int(c["readiness_pct"] / 5)
        print(f"    {c['station']:<30} {bar:<20} {c['readiness_pct']:>5.1f}%")
    print()
    print("[JSON Output]")
    print(json.dumps(result, indent=2))
