"""
station_readiness.py
SentinelAI – Station Readiness Calculator
Computes a readiness score for each station based on:
  - Available resources (officers, vehicles, tow_trucks)
  - Current load (active + high-priority incidents from the dataset)
"""

import pandas as pd
from typing import Dict
from resource_tracker import ResourceTracker
from resource_database import DEFAULT_RESOURCES

# Weights for resource importance
RESOURCE_WEIGHTS = {"officers": 0.5, "vehicles": 0.3, "tow_trucks": 0.2}


def _load_dataset(data_file: str) -> pd.DataFrame:
    df = pd.read_csv(data_file, encoding="latin1")
    df["start_dt"] = pd.to_datetime(df["start_datetime"], utc=True, errors="coerce")
    return df


def compute_station_loads(data_file: str) -> Dict[str, dict]:
    """
    Compute per-station load metrics from the historical dataset.
    Uses active + recent incidents as a proxy for current load.

    Returns dict keyed by station with:
        active_incidents, high_priority_incidents, avg_resolution_mins
    """
    df = _load_dataset(data_file)

    # Proxy: 'active' status or open (no resolved_datetime)
    active_mask = (df["status"] == "active") | (df["resolved_datetime"].isna() & (df["status"] != "closed"))
    active_df   = df[active_mask]

    # Resolution times
    df["start_dt"]    = pd.to_datetime(df["start_datetime"],    utc=True, errors="coerce")
    df["resolved_dt"] = pd.to_datetime(df["resolved_datetime"], utc=True, errors="coerce")
    df["resolution_mins"] = (df["resolved_dt"] - df["start_dt"]).dt.total_seconds() / 60

    loads: Dict[str, dict] = {}
    for station in df["police_station"].dropna().unique():
        station_active    = active_df[active_df["police_station"] == station]
        station_all       = df[df["police_station"] == station]
        high_priority     = station_active[station_active["priority"] == "High"]
        avg_res           = station_all["resolution_mins"].dropna().median()

        loads[station] = {
            "active_incidents":       int(len(station_active)),
            "high_priority_incidents": int(len(high_priority)),
            "avg_resolution_mins":    round(float(avg_res), 1) if pd.notna(avg_res) else 60.0,
        }
    return loads


def compute_readiness_score(
    station: str,
    tracker: ResourceTracker,
    loads: Dict[str, dict],
) -> dict:
    """
    Readiness score = weighted_resource_ratio / (1 + load_factor)

    Score range: 0–100 (higher = more ready)
    """
    try:
        res = tracker.get_available_resources(station)
    except ValueError:
        return {"station": station, "readiness_score": 0.0, "error": "Station not in resource DB"}

    load = loads.get(station, {
        "active_incidents": 0,
        "high_priority_incidents": 0,
        "avg_resolution_mins": 60.0,
    })

    # Weighted resource availability ratio (0-1)
    resource_ratio = (
        RESOURCE_WEIGHTS["officers"]   * (res["officers"]   / max(DEFAULT_RESOURCES["officers"],   1)) +
        RESOURCE_WEIGHTS["vehicles"]   * (res["vehicles"]   / max(DEFAULT_RESOURCES["vehicles"],   1)) +
        RESOURCE_WEIGHTS["tow_trucks"] * (res["tow_trucks"] / max(DEFAULT_RESOURCES["tow_trucks"], 1))
    )

    # Load factor: normalise active incidents (0 = idle, 1 = fully loaded)
    load_factor = min(
        (load["active_incidents"] + 0.5 * load["high_priority_incidents"]) / 10.0,
        2.0,  # cap at 2x to avoid division by near-zero
    )

    raw_score = resource_ratio / (1.0 + load_factor)
    score     = round(raw_score * 100, 1)

    return {
        "station":                 station,
        "readiness_score":         score,
        "resource_ratio_pct":      round(resource_ratio * 100, 1),
        "available_officers":      res["officers"],
        "available_vehicles":      res["vehicles"],
        "available_tow_trucks":    res["tow_trucks"],
        "active_incidents":        load["active_incidents"],
        "high_priority_incidents": load["high_priority_incidents"],
        "avg_resolution_mins":     load["avg_resolution_mins"],
    }


if __name__ == "__main__":
    import json
    DATA_FILE = "Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"
    tracker   = ResourceTracker()
    loads     = compute_station_loads(DATA_FILE)

    sample_stations = ["Peenya", "Yeshwanthpura", "Jalahalli"]
    for s in sample_stations:
        r = compute_readiness_score(s, tracker, loads)
        print(json.dumps(r, indent=2))
