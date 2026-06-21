"""
models.py
SentinelAI  Unified Flask API
Combines:
  - CatBoost prediction models (risk / road closure / resolution time)
  - Resource Intelligence (SQLite-based station inventory)
  - Historical Incident Search (FAISS + Sentence Transformers)
  - Station Load Balancer & Dispatch Pipeline
  - Corridor Ripple Simulator (NetworkX + BFS Propagation)
"""

import os
import sys
import json
import psycopg2
import pickle
import uuid
import re
import traceback
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, request, jsonify
try:
    from flask_cors import CORS
except ImportError:
    CORS = None  # flask-cors not installed; CORS middleware skipped
from catboost import CatBoostClassifier, CatBoostRegressor
import pandas as pd
import numpy as np
import networkx as nx
import psycopg2

# ─────────────────────────────────────────────────────────────────────────────
# PATH RESOLUTION
# All paths are relative to the project root (parent of final_endpoints/)
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))              # final_endpoints/
PROJECT_ROOT = os.path.dirname(BASE_DIR)                           # gridlock/

TRAINED_MODEL_DIR = os.path.join(PROJECT_ROOT, "trained_model")
RESOURCE_MODULE_DIR = os.path.join(
    PROJECT_ROOT, "Resource Intelligence and Historical Operation Module"
)
DATA_FILE = os.path.join(
    RESOURCE_MODULE_DIR,
    "Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv",
)
DB_FILE = os.path.join(RESOURCE_MODULE_DIR, "resources.db")
FAISS_INDEX_DIR = os.path.join(RESOURCE_MODULE_DIR, "faiss_index")
BACKEND_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sentinel:sentinel@localhost:5432/sentinelai",
)
BACKEND_API_URL = os.getenv(
    "BACKEND_API_URL",
    os.getenv("NEXT_PUBLIC_BACKEND_API_URL", "http://127.0.0.1:5001"),
)

# ─────────────────────────────────────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
if CORS is not None:
    CORS(app, origins=[r"^https://.*\.pages\.dev$", "http://localhost:3000", "http://localhost:3001","https://sentinel-ai-ashen-seven.vercel.app",])


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CATBOOST PREDICTION MODELS
# ═════════════════════════════════════════════════════════════════════════════

# ── Load Models ──────────────────────────────────────────────────────────────

risk_model = CatBoostClassifier()
risk_model.load_model(
    os.path.join(TRAINED_MODEL_DIR, "priority_catboost_model.cbm")
)

closure_model = CatBoostClassifier()
closure_model.load_model(
    os.path.join(TRAINED_MODEL_DIR, "road_closure_catboost_model.cbm")
)

time_model = CatBoostRegressor()
time_model.load_model(
    os.path.join(TRAINED_MODEL_DIR, "resolution_time_model.cbm")
)

# ── Feature Sets (must match training scripts exactly) ───────────────────────

RISK_FEATURES = [
    'event_type_grouped',
    'event_cause',
    'corridor',
    'police_station_grouped',
    'veh_type_grouped',
    'day_of_week',
    'latitude',
    'longitude',
    'location_cluster',
    'hour_of_day',
    'month',
    'is_peak_hour',
    'is_weekend',
    'is_cascaded',
    'cascade_size'
]
CLOSURE_FEATURES = [
    'event_type_grouped',
    'event_cause',
    'corridor',
    'police_station_grouped',
    'veh_type_grouped',
    'day_of_week',
    'priority',
    'latitude',
    'longitude',
    'location_cluster',
    'hour_of_day',
    'month',
    'is_peak_hour',
    'is_weekend',
    'is_cascaded',
    'cascade_size'
]

TIME_FEATURES = [
    'event_type_grouped',
    'event_cause',
    'corridor',
    'police_station_grouped',
    'veh_type_grouped',
    'day_of_week',
    'priority',
    'latitude',
    'longitude',
    'location_cluster',
    'hour_of_day',
    'month',
    'is_peak_hour',
    'is_weekend',
    'is_cascaded',
    'cascade_size'
]

# ── Default Values ───────────────────────────────────────────────────────────

DEFAULTS = {
    "event_type_grouped": "unknown",
    "event_cause": "unknown",
    "corridor": "unknown",
    "junction": "unknown",
    "zone": "unknown",
    "police_station_grouped": "unknown",
    "veh_type_grouped": "unknown",
    "day_of_week": "unknown",

    "latitude": 0.0,
    "longitude": 0.0,

    "location_cluster": -1,

    "hour_of_day": 12,
    "month": 1,

    "is_peak_hour": 0,
    "is_weekend": 0,

    "is_cascaded": 0,
    "cascade_size": 1
}


def build_dataframe(payload, feature_list):
    """Build a single-row DataFrame from the payload using the given feature list."""
    row = {}
    for feature in feature_list:
        row[feature] = payload.get(
            feature,
            DEFAULTS.get(feature)
        )
    df = pd.DataFrame([row])
    return df[feature_list]


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — RESOURCE DATABASE (from resource_database.py)
# ═════════════════════════════════════════════════════════════════════════════

# ── Default resource pool per station ────────────────────────────────────────
DEFAULT_RESOURCES = {
    "officers":   15,
    "vehicles":    4,
    "tow_trucks":  2,
    "barricades": 20,
}

# Stations list pulled directly from the Astram dataset
STATIONS: List[str] = [
    "Peenya", "HSR Layout", "Wilson Garden", "Sadashivanagar", "Hebbala",
    "Kengeri", "Cubbon Park", "Hennuru", "K.R. Pura", "Byatarayanapura",
    "Mahadevapura", "Halasur", "Kodigehalli", "Jayanagara", "Madiwala",
    "Jeevanbheemanagar", "Whitefield", "Shivajinagar", "Mico Layout",
    "HAL Old Airport", "J.P. Nagar", "Magadi Road", "Electronic City",
    "High ground", "Chikkabanavara", "K.G. Halli", "Yeshwanthpura",
    "Bellandur", "Malleshwaram", "Devanahalli Airport", "Jnanabharathi",
    "Vijayanagara", "Chamarajpet", "Kamakshipalya", "V.V.Puram (C.Pet)",
    "Rajajinagar", "Pulikeshinagar(F.Town)", "Adugodi", "Ashok Nagar",
    "Banaswadi", "Halasuru Gate", "R.T. Nagar", "Banashankari",
    "City Market", "Basavanagudi", "Yelahanka", "K.S. Layout",
    "Chikkajala", "Sheshadripuram", "Hulimavu", "Jalahalli",
    "Thalagattapura", "Upparpet",
]


# ── Connection pool (initialized once at startup) ────────────────────────────
# Supabase free tier: 25 max connections.
# Render free tier: 1 gunicorn worker by default (see start command).
# Pool sized at min=1, max=5 — well within budget even if concurrency is
# briefly higher than 1 worker.
_db_pool = None

def _get_pool():
    """Lazily initialise the connection pool on first call."""
    global _db_pool
    if _db_pool is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise Exception("DATABASE_URL environment variable is missing")
        from psycopg2 import pool as pg_pool
        _db_pool = pg_pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=db_url,
        )
        print("[ResourceDB] Connection pool initialised (min=1, max=5)")
    return _db_pool


class DBWrapper:
    """Thin wrapper around a pooled psycopg2 connection.

    Always call .close() (or use as a context manager) to return the
    connection to the pool rather than closing it.
    """
    def __init__(self):
        self._pool = _get_pool()
        self.conn = self._pool.getconn()

    def execute(self, query, params=()):
        cur = self.conn.cursor()
        if query:
            # Translate SQLite-style ? placeholders to psycopg2 %s
            cur.execute(query.replace('?', '%s'), params)
        return cur

    def fetchall_query(self, query, params=()):
        """Execute query and return all rows, closing cursor automatically."""
        cur = self.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        """Return this connection to the pool (NOT psycopg2 close)."""
        try:
            self._pool.putconn(self.conn)
        except Exception:
            pass

    # Context-manager support so callers can use `with _get_db_connection() as conn:`
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        self.close()
        return False


def _get_db_connection(db_file=DB_FILE):
    """Return a DBWrapper backed by the shared connection pool."""
    return DBWrapper()


def _backend_generate_incident_id(cur) -> str:
    year = datetime.now(timezone.utc).year
    try:
        cur.execute("SELECT nextval('incident_id_seq')")
        seq = int(cur.fetchone()[0])
        return f"INC-{year}-{seq:06d}"
    except Exception:
        rand = uuid.uuid4().int % 1_000_000
        return f"INC-{year}-{rand:06d}"


def _store_via_backend_api(payload: dict, response: dict) -> tuple[str, str]:
    api_payload = dict(payload)
    api_payload["prediction"] = response.get("predictions", {})
    api_payload["recommended_resources"] = response.get("recommended_resources")
    api_payload["historical_context"] = response.get("historical_context")

    req = Request(
        f"{BACKEND_API_URL.rstrip('/')}/incidents",
        data=json.dumps(api_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=5) as res:
        body = json.loads(res.read().decode("utf-8"))
        incident_id = body.get("incident_id") or api_payload.get("incident_id")
        prediction_id = body.get("prediction_id")
        if not incident_id or not prediction_id:
            raise RuntimeError("Backend incident save response missing ids")
        return incident_id, prediction_id


def _store_received_incident(payload: dict, response: dict) -> tuple[str, str]:
    try:
        return _store_via_backend_api(payload, response)
    except Exception:
        traceback.print_exc()

    incident_id = None
    prediction_id = str(uuid.uuid4())
    predictions = response.get("predictions", {})
    created_at = datetime.now(timezone.utc)
    request_json = json.dumps(payload, sort_keys=True)

    conn = None
    try:
        conn = psycopg2.connect(BACKEND_DATABASE_URL, connect_timeout=3)
        conn.autocommit = False
        cur = conn.cursor()
        incident_id = _backend_generate_incident_id(cur)

        incident_type = payload.get("event_type_grouped", "unknown")
        event_cause = payload.get("event_cause", "unknown")
        vehicle_type = payload.get("veh_type_grouped", "unknown")
        corridor = payload.get("corridor", "unknown")
        location = payload.get("location") or corridor
        latitude = payload.get("latitude")
        longitude = payload.get("longitude")

        cur.execute(
            """
            INSERT INTO incidents (
                incident_id,
                incident_type,
                event_cause,
                vehicle_type,
                location,
                corridor,
                latitude,
                longitude,
                status,
                reported_at,
                raw_transcript,
                is_cancelled,
                created_at,
                updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                incident_id,
                incident_type,
                event_cause,
                vehicle_type,
                location,
                corridor,
                latitude,
                longitude,
                "REPORTED",
                created_at,
                request_json,
                False,
                created_at,
                created_at,
            ),
        )

        predicted_priority = predictions.get("priority")
        road_closure_required = predictions.get("road_closure_required", False)
        road_closure_probability = predictions.get("road_closure_probability")
        expected_resolution_minutes = predictions.get("expected_resolution_minutes")

        cur.execute(
            """
            INSERT INTO predictions (
                prediction_id,
                incident_id,
                predicted_priority,
                priority_confidence,
                predicted_resolution_minutes,
                road_closure_probability,
                road_closure_recommendation,
                model_version,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                prediction_id,
                incident_id,
                predicted_priority,
                round(float(predictions.get("priority_confidence", 0.0)) / 100.0, 4)
                if predictions.get("priority_confidence") is not None
                else None,
                expected_resolution_minutes,
                round(float(road_closure_probability) / 100.0, 4)
                if road_closure_probability is not None
                else None,
                "Yes" if road_closure_required else "No",
                "final_endpoints-1.0",
                created_at,
            ),
        )

        conn.commit()
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()

    return incident_id, prediction_id


def _extract_incident_id(payload: dict) -> Optional[str]:
    """Best-effort incident_id extraction for dispatch/status updates."""
    incident_id = payload.get("incident_id")
    if incident_id:
        return str(incident_id).strip()

    incident_text = str(payload.get("incident_text", "") or "")
    match = re.search(r"INC-\d{4}-\d{6}", incident_text)
    if match:
        return match.group(0)
    return None


def _mark_backend_incident_in_progress(incident_id: str) -> bool:
    """Update the backend incident row to IN_PROGRESS if it exists."""
    conn = None
    try:
        conn = psycopg2.connect(BACKEND_DATABASE_URL, connect_timeout=3)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE incidents
               SET status = 'IN_PROGRESS',
                   updated_at = NOW()
             WHERE incident_id = %s
               AND status IN ('REPORTED', 'UNDER_ASSESSMENT', 'RESOURCES_ASSIGNED', 'IN_PROGRESS')
            """,
            (incident_id,),
        )
        updated = cur.rowcount > 0
        conn.commit()
        return updated
    except Exception:
        if conn is not None:
            conn.rollback()
        traceback.print_exc()
        return False
    finally:
        if conn is not None:
            conn.close()


def _init_db(db_file=DB_FILE, force=False):
    """Create tables and seed default resources. Safe to call multiple times."""
    with _get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS station_resources (
                station     TEXT PRIMARY KEY,
                officers    INTEGER NOT NULL,
                vehicles    INTEGER NOT NULL,
                tow_trucks  INTEGER NOT NULL,
                barricades  INTEGER NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS resource_log (
                id          SERIAL PRIMARY KEY,
                station     TEXT,
                action      TEXT,
                officers    INTEGER,
                vehicles    INTEGER,
                tow_trucks  INTEGER,
                barricades  INTEGER,
                timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        if force:
            conn.execute("DELETE FROM station_resources")

        # Seed only missing stations
        import random
        for i, station in enumerate(STATIONS):
            if i % 5 == 0:
                off = max(0, DEFAULT_RESOURCES["officers"] - random.randint(2, 8))
                veh = max(0, DEFAULT_RESOURCES["vehicles"] - random.randint(1, 3))
                tow = max(0, DEFAULT_RESOURCES["tow_trucks"] - random.randint(0, 1))
                bar = max(0, DEFAULT_RESOURCES["barricades"] - random.randint(5, 15))
            elif i % 3 == 0:
                off = max(0, DEFAULT_RESOURCES["officers"] - random.randint(1, 4))
                veh = max(0, DEFAULT_RESOURCES["vehicles"] - random.randint(0, 1))
                tow = DEFAULT_RESOURCES["tow_trucks"]
                bar = max(0, DEFAULT_RESOURCES["barricades"] - random.randint(2, 5))
            else:
                off = DEFAULT_RESOURCES["officers"]
                veh = DEFAULT_RESOURCES["vehicles"]
                tow = DEFAULT_RESOURCES["tow_trucks"]
                bar = DEFAULT_RESOURCES["barricades"]

            conn.execute(
                "INSERT INTO station_resources VALUES (%s,%s,%s,%s,%s) ON CONFLICT (station) DO NOTHING",
                (station, off, veh, tow, bar),
            )

            # Fix any station with all zeros from a previous bug
            conn.execute("""
                UPDATE station_resources
                SET officers=%s, vehicles=%s, tow_trucks=%s, barricades=%s
                WHERE station=%s AND officers=0 AND vehicles=0 AND tow_trucks=0 AND barricades=0
            """, (off, veh, tow, bar, station))

        conn.commit()
    print(f"[ResourceDB] Initialised with {len(STATIONS)} stations")


def _log_action(conn, station, action, officers, vehicles, tow_trucks, barricades):
    # Uses %s placeholders (psycopg2); DBWrapper.execute() also handles ? → %s,
    # but we write %s directly here to be explicit.
    conn.execute(
        "INSERT INTO resource_log (station,action,officers,vehicles,tow_trucks,barricades) VALUES (%s,%s,%s,%s,%s,%s)",
        (station, action, officers, vehicles, tow_trucks, barricades),
    )


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 — RESOURCE TRACKER (from resource_tracker.py)
# ═════════════════════════════════════════════════════════════════════════════

class ResourceTracker:
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        _init_db(db_file)  # idempotent – safe to call each time

    # ── Internal helpers ─────────────────────────────────────────────────────
    def _get(self, station: str) -> Optional[dict]:
        conn = _get_db_connection(self.db_file)
        row = conn.execute(
            "SELECT officers, vehicles, tow_trucks, barricades FROM station_resources WHERE station=?",
            (station,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "station":    station,
            "officers":   row[0],
            "vehicles":   row[1],
            "tow_trucks": row[2],
            "barricades": row[3],
        }

    def _update(self, conn, station, officers, vehicles, tow_trucks, barricades):
        conn.execute(
            """UPDATE station_resources
               SET officers=?, vehicles=?, tow_trucks=?, barricades=?
               WHERE station=?""",
            (officers, vehicles, tow_trucks, barricades, station),
        )

    # ── Public API ───────────────────────────────────────────────────────────
    def get_available_resources(self, station: str) -> dict:
        """Return current resource snapshot for a station."""
        res = self._get(station)
        if not res:
            raise ValueError(f"Station '{station}' not found in database.")
        return res

    def allocate_resources(
        self,
        station: str,
        officers: int = 0,
        vehicles: int = 0,
        tow_trucks: int = 0,
        barricades: int = 0,
    ) -> dict:
        """
        Deduct resources for an active dispatch within a single pooled connection.
        Raises ValueError if station lacks sufficient resources.
        """
        with _get_db_connection() as conn:
            cur = conn.execute(
                "SELECT officers, vehicles, tow_trucks, barricades FROM station_resources WHERE station=%s",
                (station,),
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                raise ValueError(f"Station '{station}' not found.")

            cur_o, cur_v, cur_t, cur_b = row

            shortages = []
            if officers   > cur_o: shortages.append(f"officers (need {officers}, have {cur_o})")
            if vehicles   > cur_v: shortages.append(f"vehicles (need {vehicles}, have {cur_v})")
            if tow_trucks > cur_t: shortages.append(f"tow_trucks (need {tow_trucks}, have {cur_t})")
            if barricades > cur_b: shortages.append(f"barricades (need {barricades}, have {cur_b})")
            if shortages:
                raise ValueError(f"Insufficient resources at {station}: {', '.join(shortages)}")

            new_o = cur_o - officers
            new_v = cur_v - vehicles
            new_t = cur_t - tow_trucks
            new_b = cur_b - barricades

            self._update(conn, station, new_o, new_v, new_t, new_b)
            _log_action(conn, station, "allocate", officers, vehicles, tow_trucks, barricades)
            conn.commit()

            # Read back remaining within the SAME connection — no second round-trip
            remaining = {
                "station": station,
                "officers": new_o,
                "vehicles": new_v,
                "tow_trucks": new_t,
                "barricades": new_b,
            }

        return {
            "station":    station,
            "action":     "allocated",
            "dispatched": {"officers": officers, "vehicles": vehicles,
                           "tow_trucks": tow_trucks, "barricades": barricades},
            "remaining":  remaining,
        }

    def release_resources(
        self,
        station: str,
        officers: int = 0,
        vehicles: int = 0,
        tow_trucks: int = 0,
        barricades: int = 0,
    ) -> dict:
        """Return resources to station after incident resolution, single connection."""
        with _get_db_connection() as conn:
            cur = conn.execute(
                "SELECT officers, vehicles, tow_trucks, barricades FROM station_resources WHERE station=%s",
                (station,),
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                raise ValueError(f"Station '{station}' not found.")

            new_o = min(row[0] + officers,   DEFAULT_RESOURCES["officers"])
            new_v = min(row[1] + vehicles,   DEFAULT_RESOURCES["vehicles"])
            new_t = min(row[2] + tow_trucks, DEFAULT_RESOURCES["tow_trucks"])
            new_b = min(row[3] + barricades, DEFAULT_RESOURCES["barricades"])

            self._update(conn, station, new_o, new_v, new_t, new_b)
            _log_action(conn, station, "release", officers, vehicles, tow_trucks, barricades)
            conn.commit()

            current = {
                "station": station,
                "officers": new_o,
                "vehicles": new_v,
                "tow_trucks": new_t,
                "barricades": new_b,
            }

        return {
            "station":  station,
            "action":   "released",
            "returned": {"officers": officers, "vehicles": vehicles,
                         "tow_trucks": tow_trucks, "barricades": barricades},
            "current":  current,
        }

    def list_all_stations(self) -> list:
        """Fetch all station resources in one query."""
        with _get_db_connection() as conn:
            rows = conn.fetchall_query(
                "SELECT station, officers, vehicles, tow_trucks, barricades FROM station_resources ORDER BY station"
            )
        return [
            {"station": r[0], "officers": r[1], "vehicles": r[2],
             "tow_trucks": r[3], "barricades": r[4]}
            for r in rows
        ]

    def get_all_resources_batch(self) -> dict:
        """Fetch ALL stations in one query. Returns {station_name: resource_dict}.
        Used by station_readiness to avoid 53 separate DB round-trips."""
        with _get_db_connection() as conn:
            rows = conn.fetchall_query(
                "SELECT station, officers, vehicles, tow_trucks, barricades FROM station_resources"
            )
        return {
            r[0]: {
                "station":    r[0],
                "officers":   r[1],
                "vehicles":   r[2],
                "tow_trucks": r[3],
                "barricades": r[4],
            }
            for r in rows
        }


# Initialise the tracker at module level
tracker = ResourceTracker()


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 — STATION READINESS (from station_readiness.py)
# ═════════════════════════════════════════════════════════════════════════════

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
    active_df = df[active_mask]

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
            "active_incidents":        int(len(station_active)),
            "high_priority_incidents": int(len(high_priority)),
            "avg_resolution_mins":     round(float(avg_res), 1) if pd.notna(avg_res) else 60.0,
        }
    return loads


def compute_readiness_score(
    station: str,
    resource_tracker: ResourceTracker,
    loads: Dict[str, dict],
) -> dict:
    """
    Readiness score = weighted_resource_ratio / (1 + load_factor)
    Score range: 0–100 (higher = more ready)
    """
    try:
        res = resource_tracker.get_available_resources(station)
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

    import math
    effective_load = load["active_incidents"] + 0.5 * load["high_priority_incidents"]
    # Use a logarithmic scale to differentiate high-load stations without hitting a hard cap
    load_factor = math.log1p(effective_load) / 1.5

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


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5 — LOAD BALANCER (from load_balancer.py)
# ═════════════════════════════════════════════════════════════════════════════

class LoadBalancer:
    def __init__(self, data_file: str = DATA_FILE):
        self._tracker = tracker  # use module-level tracker
        print("[LoadBalancer] Computing station loads from historical data …")
        self.loads = compute_station_loads(data_file)

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
            r = compute_readiness_score(station, self._tracker, self.loads)
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
            "incident_location":   incident_location,
            "recommended_station": best["station"],
            "readiness_score":     best["readiness_score"],
            "reason":              reasons,
            "station_details":     best,
            "all_candidates":      [
                {
                    "station":       r["station"],
                    "readiness_pct": r["readiness_score"],
                    "active":        r["active_incidents"],
                    "officers":      r["available_officers"],
                    "vehicles":      r["available_vehicles"],
                }
                for r in ranked[:8]   # top 8 for display
            ],
        }


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6 — EMBEDDING PIPELINE (from embedding_pipeline.py)
# ═════════════════════════════════════════════════════════════════════════════

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"   # fast, 384-dim, good quality

FEATURE_COLS = [
    "event_cause", "corridor", "junction",
    "priority", "veh_type", "police_station",
]


def _load_and_clean(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="latin1")

    # Parse datetimes
    df["start_dt"]    = pd.to_datetime(df["start_datetime"],   utc=True, errors="coerce")
    df["resolved_dt"] = pd.to_datetime(df["resolved_datetime"], utc=True, errors="coerce")

    # Resolution time in minutes
    df["resolution_mins"] = (
        (df["resolved_dt"] - df["start_dt"]).dt.total_seconds() / 60
    )

    # Day / hour features
    df["day"]  = df["start_dt"].dt.day_name()
    df["hour"] = df["start_dt"].dt.hour

    # Fill NaN in text cols
    for col in FEATURE_COLS:
        if col in df.columns:
            df[col] = df[col].fillna("unknown")

    return df


def _build_text_repr(row: pd.Series) -> str:
    """Concatenate features into a single sentence for embedding."""
    parts = []
    for col in FEATURE_COLS:
        val = str(row.get(col, "unknown")).strip().lower().replace("_", " ")
        parts.append(val)
    if "day" in row:
        parts.append(str(row["day"]).lower())
    if "hour" in row:
        parts.append(f"hour {row['hour']}")
    return " | ".join(parts)


def _build_embeddings(df: pd.DataFrame, model) -> np.ndarray:
    texts = df.apply(_build_text_repr, axis=1).tolist()
    print(f"[EmbeddingPipeline] Encoding {len(texts)} incidents …")
    embeddings = model.encode(texts, batch_size=256, show_progress_bar=True,
                              normalize_embeddings=True)
    return embeddings.astype("float32")


def _build_faiss_index(embeddings: np.ndarray):
    import faiss
    dim   = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)   # Inner-product == cosine on L2-normalised vecs
    index.add(embeddings)
    print(f"[EmbeddingPipeline] FAISS index built – {index.ntotal} vectors, dim={dim}")
    return index


def _save_artifacts(df, embeddings, index, out_dir=FAISS_INDEX_DIR):
    import faiss
    os.makedirs(out_dir, exist_ok=True)
    faiss.write_index(index, os.path.join(out_dir, "incidents.index"))
    np.save(os.path.join(out_dir, "embeddings.npy"), embeddings)
    df.reset_index(drop=True).to_pickle(os.path.join(out_dir, "incidents.pkl"))
    print(f"[EmbeddingPipeline] Artifacts saved -> {out_dir}/")


def _load_artifacts(out_dir=FAISS_INDEX_DIR):
    import faiss
    index      = faiss.read_index(os.path.join(out_dir, "incidents.index"))
    embeddings = np.load(os.path.join(out_dir, "embeddings.npy"))
    df         = pd.read_pickle(os.path.join(out_dir, "incidents.pkl"))
    return df, embeddings, index


def run_embedding_pipeline(data_file=DATA_FILE, out_dir=FAISS_INDEX_DIR, force=False):
    """Build or load the FAISS index and incident dataframe."""
    if not force and os.path.exists(os.path.join(out_dir, "incidents.index")):
        print("[EmbeddingPipeline] Index already exists – skipping build.")
        return _load_artifacts(out_dir)

    from sentence_transformers import SentenceTransformer
    df    = _load_and_clean(data_file)
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    embs  = _build_embeddings(df, model)
    index = _build_faiss_index(embs)
    _save_artifacts(df, embs, index, out_dir)
    return df, embs, index


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 7 — HISTORICAL SEARCH (from historical_search.py)
# Lazy-loaded to avoid slowing Flask startup
# ═════════════════════════════════════════════════════════════════════════════

_hist_df: Optional[pd.DataFrame]    = None
_hist_index                          = None
_hist_model                          = None


def _load_historical():
    """Lazy-load FAISS index and sentence-transformer model on first use."""
    global _hist_df, _hist_index, _hist_model
    if _hist_df is None:
        from sentence_transformers import SentenceTransformer
        _hist_df, _, _hist_index = run_embedding_pipeline(out_dir=FAISS_INDEX_DIR)
        _hist_model = SentenceTransformer(EMBEDDING_MODEL_NAME)


def search_similar_incidents(
    query: str,
    top_k: int = 20,
) -> dict:
    """
    Parameters
    ----------
    query   : Free-text description, e.g. 'Vehicle Breakdown Tumkur Road Heavy Vehicle'
    top_k   : Number of neighbours to retrieve

    Returns
    -------
    dict with keys: similar_cases, average_resolution_time, historical_priority,
                    most_common_outcome, total_similar
    """
    _load_historical()

    # Embed query (L2-normalised to match inner-product index)
    q_vec = _hist_model.encode([query], normalize_embeddings=True).astype("float32")

    scores, indices = _hist_index.search(q_vec, top_k)
    matched = _hist_df.iloc[indices[0]].copy()
    matched["similarity_score"] = scores[0]

    # ── Aggregate stats ──────────────────────────────────────────────────────
    avg_res_time = (
        matched["resolution_mins"].dropna().median()
        if "resolution_mins" in matched.columns else None
    )

    priority_counts = matched["priority"].value_counts()
    most_common_priority = (
        priority_counts.index[0] if not priority_counts.empty else "Unknown"
    )

    # "outcome" proxied by event_cause (dominant event type in results)
    outcome_counts = matched["event_cause"].value_counts()
    most_common_outcome = (
        outcome_counts.index[0].replace("_", " ").title()
        if not outcome_counts.empty else "Unknown"
    )

    # Build per-case summaries (serialisable)
    cases = []
    for _, row in matched.iterrows():
        cases.append({
            "event_cause":       str(row.get("event_cause", "")),
            "corridor":          str(row.get("corridor", "")),
            "junction":          str(row.get("junction", "")),
            "priority":          str(row.get("priority", "")),
            "veh_type":          str(row.get("veh_type", "")),
            "police_station":    str(row.get("police_station", "")),
            "status":            str(row.get("status", "")),
            "resolution_mins":   (
                round(float(row["resolution_mins"]), 1)
                if pd.notna(row.get("resolution_mins")) else None
            ),
            "similarity_score":  round(float(row["similarity_score"]), 4),
        })

    # Count total similar in full dataset (cosine threshold 0.75)
    all_scores, _ = _hist_index.search(q_vec, min(len(_hist_df), 5000))
    total_similar = int((all_scores[0] >= 0.75).sum())

    result = {
        "similar_cases":           cases,
        "total_similar":           total_similar,
        "average_resolution_time": round(avg_res_time, 1) if avg_res_time else None,
        "historical_priority":     most_common_priority,
        "most_common_outcome":     most_common_outcome,
    }
    return result


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 8 — STATION SELECTOR / DISPATCH (from station_selector.py)
# Lazy-loaded LoadBalancer
# ═════════════════════════════════════════════════════════════════════════════

_lb: Optional[LoadBalancer] = None


def _get_balancer() -> LoadBalancer:
    global _lb
    if _lb is None:
        _lb = LoadBalancer()
    return _lb


def dispatch(
    incident_text: str,
    corridor: str = None,
    min_officers: int = 1,
    min_vehicles: int = 1,
    search_top_k: int = 20,
) -> dict:
    """
    Full dispatch pipeline:
      1. Historical search -> context
      2. Load balancer -> best station

    Returns a unified response dict.
    """
    lb = _get_balancer()

    # Step 1 – Historical context
    history = search_similar_incidents(incident_text, top_k=search_top_k)
    
    # Step 2 - Dynamic Resource Recommendation Heuristic
    # The Astram dataset does not track exact historical officer/vehicle counts per incident.
    # We derive a justified rule-based recommendation from the most common priority and event signals
    # of the similar historical cases.
    hist_priority = history.get("historical_priority", "low").lower()
    
    # Analyze the top similar cases for heavy vehicles or planned events
    has_heavy_vehicle = any(c.get("veh_type") in ["heavy_vehicle", "bus"] for c in history["similar_cases"])
    has_planned_event = any(c.get("event_cause") in ["public_event", "procession", "vip_movement", "protest"] for c in history["similar_cases"])
    
    # Default baseline
    rec_officers = 2
    rec_vehicles = 1
    rec_tow = 0
    rec_barricades = 0
    
    reasoning = []
    
    if hist_priority in ["p1", "high", "critical"]:
        rec_officers += 2
        rec_vehicles += 1
        reasoning.append("High priority historical profile (+2 officers, +1 vehicle)")
    
    if has_heavy_vehicle:
        rec_tow = 1
        reasoning.append("Involves heavy vehicles/buses (+1 tow truck)")
        
    if has_planned_event:
        rec_officers += 4
        rec_barricades = 10
        reasoning.append("Planned event detected in context (+4 officers, +10 barricades)")
        
    if not reasoning:
        reasoning.append("Standard baseline response package")

    # Step 3 – Station selection using the dynamically computed minimums
    selection = lb.select_station(
        incident_location=incident_text,
        corridor=corridor,
        min_officers=rec_officers,
        min_vehicles=rec_vehicles,
    )

    return {
        "dispatch": {
            "incident":             incident_text,
            "recommended_station":  selection["recommended_station"],
            "readiness_score":      selection["readiness_score"],
            "reasons":              selection["reason"],
            "top_candidates":       selection["all_candidates"],
        },
        "recommended_resources": {
            "officers": rec_officers,
            "vehicles": rec_vehicles,
            "tow_trucks": rec_tow,
            "barricades": rec_barricades,
            "justification": "Based on historical similarities: " + "; ".join(reasoning)
        },
        "historical_context": {
            "similar_cases":            history["total_similar"],
            "average_resolution_time":  history["average_resolution_time"],
            "historical_priority":      history["historical_priority"],
            "most_common_outcome":      history["most_common_outcome"],
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 10 — BENGALURU TRAFFIC NETWORK GRAPH (CORRIDOR RIPPLE SIMULATOR)
# ═════════════════════════════════════════════════════════════════════════════

BENGALURU_NODES = {
    "Tumkur Road": {"lat": 13.0380, "lon": 77.5120},
    "Peenya Junction": {"lat": 13.0285, "lon": 77.5186},
    "Yeshwanthpur": {"lat": 13.0206, "lon": 77.5560},
    "Hebbal": {"lat": 13.0354, "lon": 77.5978},
    "Outer Ring Road": {"lat": 12.9716, "lon": 77.6410},
    "Marathahalli": {"lat": 12.9562, "lon": 77.7011},
    "Silk Board": {"lat": 12.9176, "lon": 77.6244},
    "Electronic City": {"lat": 12.8452, "lon": 77.6602},
    "KR Puram": {"lat": 13.0110, "lon": 77.7040},
    "Mysore Road": {"lat": 12.9461, "lon": 77.5255},
    "Majestic": {"lat": 12.9766, "lon": 77.5712}
}

BENGALURU_EDGES = [
    ("Tumkur Road", "Peenya Junction"),
    ("Peenya Junction", "Yeshwanthpur"),
    ("Yeshwanthpur", "Hebbal"),
    ("Yeshwanthpur", "Majestic"),
    ("Hebbal", "KR Puram"),
    ("KR Puram", "Marathahalli"),
    ("Marathahalli", "Outer Ring Road"),
    ("Outer Ring Road", "Silk Board"),
    ("Silk Board", "Electronic City"),
    ("Majestic", "Mysore Road"),
    ("Mysore Road", "Silk Board"),
    ("Majestic", "Hebbal")
]

# Build the NetworkX graph during application startup
traffic_graph = nx.Graph()
for node, coords in BENGALURU_NODES.items():
    traffic_graph.add_node(node, lat=coords["lat"], lon=coords["lon"])
traffic_graph.add_edges_from(BENGALURU_EDGES)


def run_ripple_bfs(start_node: str, max_depth: int) -> list:
    """
    Executes BFS traversal to simulate traffic ripple propagation up to max_depth.
    Decays severity and escalates time taken by depth level.
    """
    matched_start = None
    for node in traffic_graph.nodes:
        if node.lower() == start_node.lower():
            matched_start = node
            break

    if not matched_start:
        # Fallback to the first node if not matched precisely to avoid failing silently
        matched_start = list(traffic_graph.nodes)[0]

    visited = {matched_start}
    queue = [(matched_start, 0)]
    results = []

    while queue:
        curr, dist = queue.pop(0)
        if dist >= max_depth:
            continue

        for neighbor in traffic_graph.neighbors(curr):
            if neighbor not in visited:
                visited.add(neighbor)
                next_dist = dist + 1

                # Calculate depth-based attributes
                if next_dist == 1:
                    severity = "high"
                    time_taken = 15
                elif next_dist == 2:
                    severity = "medium"
                    time_taken = 30
                elif next_dist == 3:
                    severity = "low"
                    time_taken = 45
                else:  # next_dist == 4 or greater
                    severity = "low"
                    time_taken = 60

                node_data = traffic_graph.nodes[neighbor]
                results.append({
                    "location": neighbor,
                    "coordinates": {
                        "lat": node_data["lat"],
                        "lon": node_data["lon"]
                    },
                    "time_taken_minutes": time_taken,
                    "severity": severity
                })

                queue.append((neighbor, next_dist))
    return results


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 9 — REST ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

def _int_param(val, default=0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _bad_request(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


# ── Health Check ─────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "SentinelAI Unified API"
    })


# ── CatBoost Prediction ─────────────────────────────────────────────────────

@app.route("/predict", methods=["POST"])
def predict():
    try:
        payload = request.get_json()

        # ── Risk Model ───────────────────────────────────────────────────
        X_risk = build_dataframe(payload, RISK_FEATURES)
        risk_prediction = risk_model.predict(X_risk)
        risk_class = int(risk_prediction[0])
        risk_prob = float(risk_model.predict_proba(X_risk)[0][1])
        predicted_priority = "high" if risk_class == 1 else "low"

        payload["priority"] = predicted_priority

        # ── Road Closure Model ───────────────────────────────────────────
        X_closure = build_dataframe(payload, CLOSURE_FEATURES)
        closure_prob = float(closure_model.predict_proba(X_closure)[0][1])
        closure_prediction = int(closure_model.predict(X_closure)[0])

        # ── Resolution Time Model ────────────────────────────────────────
        X_time = build_dataframe(payload, TIME_FEATURES)
        log_time = float(time_model.predict(X_time)[0])
        expected_minutes = float(np.expm1(log_time))

        # ── Response ─────────────────────────────────────────────────────
        response = {
            "incident": {
                "incident_id": None,
                "event_type":  payload.get("event_type_grouped", "unknown"),
                "event_cause": payload.get("event_cause", "unknown"),
                "corridor":    payload.get("corridor", "unknown"),
            },
            "predictions": {
                "priority":                    predicted_priority,
                "priority_confidence":         round(risk_prob * 100, 2),
                "road_closure_required":       bool(closure_prediction),
                "road_closure_probability":    round(closure_prob * 100, 2),
                "expected_resolution_minutes": round(expected_minutes, 2),
            }
        }
        try:
            incident_id, prediction_id = _store_received_incident(payload, response)
            response["incident"]["incident_id"] = incident_id
            response["incident_id"] = incident_id
            response["prediction_id"] = prediction_id
        except Exception:
            traceback.print_exc()
        print(response)
        return jsonify(response)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ── Resource Inventory Endpoints ─────────────────────────────────────────────

@app.route("/stations", methods=["GET"])
def list_stations():
    """GET /stations – list all stations with current resources."""
    return jsonify(tracker.list_all_stations())


@app.route("/stations/<station>", methods=["GET"])
def get_station(station: str):
    """GET /stations/<station> – resource snapshot."""
    try:
        return jsonify(tracker.get_available_resources(station))
    except ValueError as e:
        return _bad_request(str(e), 404)


@app.route("/stations/<station>/allocate", methods=["POST"])
def allocate(station: str):
    """
    POST /stations/<station>/allocate
    Body (JSON): { "officers": 2, "vehicles": 1, "tow_trucks": 1, "barricades": 0 }
    """
    data = request.get_json(silent=True) or {}
    try:
        result = tracker.allocate_resources(
            station,
            officers   = _int_param(data.get("officers")),
            vehicles   = _int_param(data.get("vehicles")),
            tow_trucks = _int_param(data.get("tow_trucks")),
            barricades = _int_param(data.get("barricades")),
        )
        return jsonify(result), 200
    except ValueError as e:
        return _bad_request(str(e))


@app.route("/stations/<station>/release", methods=["POST"])
def release(station: str):
    """
    POST /stations/<station>/release
    Body (JSON): { "officers": 2, "vehicles": 1, "tow_trucks": 1, "barricades": 0 }
    """
    data = request.get_json(silent=True) or {}
    try:
        result = tracker.release_resources(
            station,
            officers   = _int_param(data.get("officers")),
            vehicles   = _int_param(data.get("vehicles")),
            tow_trucks = _int_param(data.get("tow_trucks")),
            barricades = _int_param(data.get("barricades")),
        )
        return jsonify(result), 200
    except ValueError as e:
        return _bad_request(str(e))


# ── Historical Search Endpoint ───────────────────────────────────────────────

@app.route("/historical-search", methods=["POST"])
def historical_search():
    """
    POST /historical-search
    Body (JSON): { "query": "Vehicle Breakdown Tumkur Road", "top_k": 20 }
    """
    try:
        data = request.get_json()
        query = data.get("query", "")
        top_k = _int_param(data.get("top_k"), default=20)

        if not query:
            return _bad_request("'query' field is required.")

        result = search_similar_incidents(query, top_k=top_k)
        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ── Dispatch Endpoint ────────────────────────────────────────────────────────

@app.route("/dispatch", methods=["POST"])
def dispatch_endpoint():
    """
    POST /dispatch
    Body (JSON): {
        "incident_text": "Vehicle Breakdown Tumkur Road Heavy Vehicle",
        "corridor": "Tumkur Road",         (optional)
        "min_officers": 2,                 (optional, default 1)
        "min_vehicles": 1,                 (optional, default 1)
        "search_top_k": 20                 (optional, default 20)
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        incident_text = data.get("incident_text", "")

        if not incident_text:
            return _bad_request("'incident_text' field is required.")

        result = dispatch(
            incident_text=incident_text,
            corridor=data.get("corridor"),
            min_officers=_int_param(data.get("min_officers"), default=1),
            min_vehicles=_int_param(data.get("min_vehicles"), default=1),
            search_top_k=_int_param(data.get("search_top_k"), default=20),
        )

        incident_id = _extract_incident_id(data)
        if incident_id:
            updated = _mark_backend_incident_in_progress(incident_id)
            result["dispatch"]["incident_id"] = incident_id
            result["dispatch"]["incident_status_updated"] = updated
        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ── Station Readiness Endpoint ───────────────────────────────────────────────

@app.route("/station-readiness", methods=["GET"])
def station_readiness():
    """
    GET /station-readiness?station=Peenya
    Without ?station param, returns readiness for all stations.

    FIX: Previously opened 53 sequential psycopg2 connections (one per station
    inside compute_readiness_score → get_available_resources → _get → DBWrapper).
    Now uses a single batch SELECT to fetch all resource rows, then scores are
    computed in Python — one connection total per request.
    """
    try:
        loads = compute_station_loads(DATA_FILE)
        station_param = request.args.get("station")

        if station_param:
            # Single-station path: still just one connection via _get()
            result = compute_readiness_score(station_param, tracker, loads)
            return jsonify(result)

        # ── All-stations path: batch fetch, then score in Python ──────────────
        # ONE query replaces 53 sequential psycopg2.connect() calls.
        all_resources = tracker.get_all_resources_batch()  # {name: resource_dict}

        import math
        results = []
        for station in STATIONS:
            res = all_resources.get(station)
            if res is None:
                results.append({"station": station, "readiness_score": 0.0,
                                 "error": "Station not in resource DB"})
                continue

            load = loads.get(station, {
                "active_incidents": 0,
                "high_priority_incidents": 0,
                "avg_resolution_mins": 60.0,
            })

            resource_ratio = (
                RESOURCE_WEIGHTS["officers"]   * (res["officers"]   / max(DEFAULT_RESOURCES["officers"],   1)) +
                RESOURCE_WEIGHTS["vehicles"]   * (res["vehicles"]   / max(DEFAULT_RESOURCES["vehicles"],   1)) +
                RESOURCE_WEIGHTS["tow_trucks"] * (res["tow_trucks"] / max(DEFAULT_RESOURCES["tow_trucks"], 1))
            )
            effective_load = load["active_incidents"] + 0.5 * load["high_priority_incidents"]
            load_factor = math.log1p(effective_load) / 1.5
            score = round((resource_ratio / (1.0 + load_factor)) * 100, 1)

            results.append({
                "station":                 station,
                "readiness_score":         score,
                "resource_ratio_pct":      round(resource_ratio * 100, 1),
                "available_officers":      res["officers"],
                "available_vehicles":      res["vehicles"],
                "available_tow_trucks":    res["tow_trucks"],
                "active_incidents":        load["active_incidents"],
                "high_priority_incidents": load["high_priority_incidents"],
                "avg_resolution_mins":     load["avg_resolution_mins"],
            })

        results.sort(key=lambda x: x["readiness_score"], reverse=True)
        return jsonify(results)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ── Corridor Ripple Simulator Endpoint ───────────────────────────────────────

@app.route("/simulate-ripple", methods=["POST"])
def simulate_ripple():
    """
    POST /simulate-ripple
    Body (JSON): {
        "location": "Tumkur Road",
        "priority": "high",
        "closure_probability": 0.82
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        location = data.get("location", "")
        closure_prob = float(data.get("closure_probability", 0.0))

        if not location:
            return _bad_request("'location' field is required.")

        # Determine depth from closure probability thresholds
        if closure_prob > 0.8:
            depth = 4
        elif closure_prob > 0.6:
            depth = 3
        elif closure_prob > 0.4:
            depth = 2
        else:
            depth = 1

        ripple_results = run_ripple_bfs(location, depth)
        return jsonify(ripple_results)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# RUN SERVER
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
