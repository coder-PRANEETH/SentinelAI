"""
models.py (Optimized for Render Free Tier)
SentinelAI Unified Flask API

Optimizations:
  - Lazy loading: models, TF-IDF index only load on first request
  - Streaming startup: Flask binds immediately, health check available
  - Reduced memory: TF-IDF replaces SentenceTransformer + FAISS + torch
  - Connection pool: tuned for single gunicorn worker
  - Graceful degradation: missing artifacts don't crash startup

Historical search backend: sklearn TF-IDF cosine similarity.
  Removed: sentence_transformers, transformers, torch, faiss.
  Added:   TfidfVectorizer + cosine_similarity (sklearn, already a dep).
"""

import os
import sys
import json
import psycopg2
import pickle
import logging
import uuid
import re
import traceback
import time
import tracemalloc
import gc
from functools import lru_cache
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from threading import Lock

from flask import Flask, request, jsonify
try:
    from flask_cors import CORS
except ImportError:
    CORS = None

from catboost import CatBoostClassifier, CatBoostRegressor
import pandas as pd
import numpy as np
import networkx as nx
import psycopg2
from safe_harbour import KerbSafeHarborIdentifier
# ─────────────────────────────────────────────────────────────────────────────
# PATH RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)


def _load_local_env(env_path: str) -> None:
    """Load simple KEY=VALUE pairs from a local .env file if present."""
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as exc:
        print(f"[final_endpoints] failed to load env file {env_path}: {exc}")


_load_local_env(os.path.join(BASE_DIR, ".env"))

TRAINED_MODEL_DIR = os.path.join(PROJECT_ROOT, "trained_model")
RESOURCE_MODULE_DIR = os.path.join(
    PROJECT_ROOT, "Resource Intelligence and Historical Operation Module"
)
DATA_FILE = os.path.join(
    RESOURCE_MODULE_DIR,
    "Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv",
)
DB_FILE = os.path.join(RESOURCE_MODULE_DIR, "resources.db")
# FAISS_INDEX_DIR removed — historical search now uses TF-IDF (no FAISS artifacts needed)
BACKEND_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sentinel:sentinel@localhost:5432/sentinelai",
)
BACKEND_API_URL = os.getenv(
    "BACKEND_API_URL",
    os.getenv("NEXT_PUBLIC_BACKEND_API_URL", "http://127.0.0.1:5001"),
)

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING & MEMORY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _process_rss_mb() -> Optional[float]:
    """Best-effort resident set size for request-time memory profiling."""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        try:
            import resource
            rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return rss_kb / 1024.0
        except Exception:
            return None


def _log_rss(label: str) -> None:
    rss_mb = _process_rss_mb()
    if rss_mb is not None:
        logger.info("[final_endpoints] %s RSS=%.2f MB", label, rss_mb)


def _log_memory_delta(
    label: str,
    started_at: float,
    rss_before: Optional[float],
    snapshot_before,
) -> None:
    rss_after = _process_rss_mb()
    parts = [
        f"[final_endpoints] {label} duration={time.perf_counter() - started_at:.3f}s",
    ]
    if rss_before is not None and rss_after is not None:
        parts.append(
            f"rss_before={rss_before:.1f}MB rss_after={rss_after:.1f}MB delta={rss_after - rss_before:.1f}MB"
        )

    if snapshot_before is not None and tracemalloc.is_tracing():
        snapshot_after = tracemalloc.take_snapshot()
        top_stats = snapshot_after.compare_to(snapshot_before, "lineno")[:5]
        if top_stats:
            parts.append(
                "largest_allocations="
                + " | ".join(
                    f"{stat.traceback[0].filename}:{stat.traceback[0].lineno} "
                    f"{stat.size_diff / 1024:.1f}KiB"
                    for stat in top_stats
                )
            )

    logger.info(" ".join(parts))


# ─────────────────────────────────────────────────────────────────────────────
# FLASK APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
if CORS is not None:
    CORS(
        app,
        origins=[
            r"^https://.*\.pages\.dev$",
            r"^https://.*\.vercel\.app$",
            "http://localhost:3000",
            "http://localhost:3001",
        ],
        supports_credentials=True,
    )

logger = logging.getLogger(__name__)

_MEMORY_DIAGNOSTICS = os.environ.get("FINAL_ENDPOINTS_PROFILE_MEMORY", "").lower() in {
    "1",
    "true",
    "yes",
}

if _MEMORY_DIAGNOSTICS and not tracemalloc.is_tracing():
    tracemalloc.start(25)

_ALLOWED_ORIGIN_PATTERNS = (
    re.compile(r"^https://.*\.pages\.dev$"),
    re.compile(r"^https://.*\.vercel\.app$"),
)


def _is_allowed_origin(origin: str | None) -> bool:
    if not origin:
        return False
    return any(pattern.fullmatch(origin) for pattern in _ALLOWED_ORIGIN_PATTERNS)


@app.after_request
def _attach_cors_headers(response):
    origin = request.headers.get("Origin")
    if _is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = request.headers.get(
            "Access-Control-Request-Headers",
            "Content-Type, Authorization",
        )
        response.headers.setdefault("Vary", "Origin")
    return response


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CATBOOST MODELS (LAZY-LOADED)
# ═════════════════════════════════════════════════════════════════════════════

_risk_model = None
_closure_model = None
_time_model = None
_models_lock = Lock()


def _load_catboost_models():
    """Lazy-load CatBoost models on first predict() call."""
    global _risk_model, _closure_model, _time_model
    if _risk_model is not None:
        return

    with _models_lock:
        if _risk_model is not None:
            return

        started_at = time.perf_counter()
        logger.info("[final_endpoints] Loading CatBoost models...")

        _risk_model = CatBoostClassifier()
        _risk_model.load_model(
            os.path.join(TRAINED_MODEL_DIR, "priority_catboost_model.cbm")
        )

        _closure_model = CatBoostClassifier()
        _closure_model.load_model(
            os.path.join(TRAINED_MODEL_DIR, "road_closure_catboost_model.cbm")
        )

        _time_model = CatBoostRegressor()
        _time_model.load_model(
            os.path.join(TRAINED_MODEL_DIR, "resolution_time_model.cbm")
        )

        logger.info(
            "[final_endpoints] CatBoost models loaded in %.3fs",
            time.perf_counter() - started_at,
        )


RISK_FEATURES = [
    'event_type_grouped', 'event_cause', 'corridor', 'police_station_grouped',
    'veh_type_grouped', 'day_of_week', 'latitude', 'longitude', 'location_cluster',
    'hour_of_day', 'month', 'is_peak_hour', 'is_weekend', 'is_cascaded', 'cascade_size'
]

CLOSURE_FEATURES = [
    'event_type_grouped', 'event_cause', 'corridor', 'police_station_grouped',
    'veh_type_grouped', 'day_of_week', 'priority', 'latitude', 'longitude',
    'location_cluster', 'hour_of_day', 'month', 'is_peak_hour', 'is_weekend',
    'is_cascaded', 'cascade_size'
]

TIME_FEATURES = [
    'event_type_grouped', 'event_cause', 'corridor', 'police_station_grouped',
    'veh_type_grouped', 'day_of_week', 'priority', 'latitude', 'longitude',
    'location_cluster', 'hour_of_day', 'month', 'is_peak_hour', 'is_weekend',
    'is_cascaded', 'cascade_size'
]

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
    """Build a single-row DataFrame from the payload."""
    row = {}
    for feature in feature_list:
        row[feature] = payload.get(feature, DEFAULTS.get(feature))
    df = pd.DataFrame([row])
    return df[feature_list]


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — RESOURCE DATABASE (POOLED CONNECTION)
# ═════════════════════════════════════════════════════════════════════════════

DEFAULT_RESOURCES = {
    "officers": 15,
    "vehicles": 4,
    "tow_trucks": 2,
    "barricades": 20,
}

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

_db_pool = None


def _get_pool():
    """Lazily initialise the connection pool on first call."""
    global _db_pool
    if _db_pool is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise Exception("DATABASE_URL environment variable is missing")
        from psycopg2 import pool as pg_pool
        # Render free: 1 worker, so keep pool minimal
        _db_pool = pg_pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=3,  # Reduced from 5
            dsn=db_url,
        )
        print("[ResourceDB] Connection pool initialised (min=1, max=3)")
    return _db_pool


class DBWrapper:
    """Thin wrapper around a pooled psycopg2 connection."""
    def __init__(self):
        self._pool = _get_pool()
        self.conn = self._checkout_connection()

    def _checkout_connection(self):
        conn = self._pool.getconn()
        if getattr(conn, "closed", 1):
            try:
                self._pool.putconn(conn, close=True)
            except Exception:
                pass
            conn = self._pool.getconn()
        return conn

    def _reconnect(self):
        try:
            self._pool.putconn(self.conn, close=True)
        except Exception:
            pass
        self.conn = self._checkout_connection()

    def execute(self, query, params=()):
        try:
            cur = self.conn.cursor()
            if query:
                cur.execute(query.replace('?', '%s'), params)
            return cur
        except psycopg2.Error:
            self._reconnect()
            cur = self.conn.cursor()
            if query:
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
        """Return this connection to the pool."""
        try:
            if getattr(self.conn, "closed", 1):
                self._pool.putconn(self.conn, close=True)
            else:
                self._pool.putconn(self.conn)
        except Exception:
            pass

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


def _connect_backend_db():
    """Create a fresh backend DB connection with a single retry."""
    last_exc = None
    for attempt in range(2):
        try:
            return psycopg2.connect(BACKEND_DATABASE_URL, connect_timeout=3)
        except psycopg2.Error as exc:
            last_exc = exc
            if attempt == 0:
                time.sleep(0.1)
    raise last_exc


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
        conn = _connect_backend_db()
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
                incident_id, incident_type, event_cause, vehicle_type,
                location, corridor, latitude, longitude, status,
                reported_at, raw_transcript, is_cancelled, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                incident_id, incident_type, event_cause, vehicle_type,
                location, corridor, latitude, longitude, "REPORTED",
                created_at, request_json, False, created_at, created_at,
            ),
        )

        predicted_priority = predictions.get("priority")
        road_closure_required = predictions.get("road_closure_required", False)
        road_closure_probability = predictions.get("road_closure_probability")
        expected_resolution_minutes = predictions.get("expected_resolution_minutes")

        cur.execute(
            """
            INSERT INTO predictions (
                prediction_id, incident_id, predicted_priority, priority_confidence,
                predicted_resolution_minutes, road_closure_probability,
                road_closure_recommendation, model_version, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                prediction_id, incident_id, predicted_priority,
                round(float(predictions.get("priority_confidence", 0.0)) / 100.0, 4)
                if predictions.get("priority_confidence") is not None else None,
                expected_resolution_minutes,
                round(float(road_closure_probability) / 100.0, 4)
                if road_closure_probability is not None else None,
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
    """Best-effort incident_id extraction."""
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
        conn = _connect_backend_db()
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE incidents
               SET status = 'IN_PROGRESS', updated_at = NOW()
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

            conn.execute("""
                UPDATE station_resources
                SET officers=%s, vehicles=%s, tow_trucks=%s, barricades=%s
                WHERE station=%s AND officers=0 AND vehicles=0 AND tow_trucks=0 AND barricades=0
            """, (off, veh, tow, bar, station))

        conn.commit()
    print(f"[ResourceDB] Initialised with {len(STATIONS)} stations")


def _log_action(conn, station, action, officers, vehicles, tow_trucks, barricades):
    conn.execute(
        "INSERT INTO resource_log (station,action,officers,vehicles,tow_trucks,barricades) VALUES (%s,%s,%s,%s,%s,%s)",
        (station, action, officers, vehicles, tow_trucks, barricades),
    )


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 — RESOURCE TRACKER
# ═════════════════════════════════════════════════════════════════════════════

class ResourceTracker:
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        _init_db(db_file)

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
            "station": station,
            "officers": row[0],
            "vehicles": row[1],
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
        """Deduct resources for an active dispatch."""
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

            remaining = {
                "station": station,
                "officers": new_o,
                "vehicles": new_v,
                "tow_trucks": new_t,
                "barricades": new_b,
            }

        return {
            "station": station,
            "action": "allocated",
            "dispatched": {"officers": officers, "vehicles": vehicles,
                           "tow_trucks": tow_trucks, "barricades": barricades},
            "remaining": remaining,
        }

    def release_resources(
        self,
        station: str,
        officers: int = 0,
        vehicles: int = 0,
        tow_trucks: int = 0,
        barricades: int = 0,
    ) -> dict:
        """Return resources to station after incident resolution."""
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
            "station": station,
            "action": "released",
            "returned": {"officers": officers, "vehicles": vehicles,
                         "tow_trucks": tow_trucks, "barricades": barricades},
            "current": current,
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
        """Fetch ALL stations in one query. Batch mode to avoid 53 round-trips."""
        with _get_db_connection() as conn:
            rows = conn.fetchall_query(
                "SELECT station, officers, vehicles, tow_trucks, barricades FROM station_resources"
            )
        return {
            r[0]: {
                "station": r[0],
                "officers": r[1],
                "vehicles": r[2],
                "tow_trucks": r[3],
                "barricades": r[4],
            }
            for r in rows
        }


_tracker: Optional[ResourceTracker] = None
_tracker_lock = Lock()


def _get_tracker() -> ResourceTracker:
    """Lazy-load the resource tracker so import time stays lightweight."""
    global _tracker
    if _tracker is not None:
        return _tracker

    with _tracker_lock:
        if _tracker is not None:
            return _tracker

        started_at = time.perf_counter()
        rss_before = _process_rss_mb()
        logger.info("[final_endpoints] STEP 1 resource tracker init")
        _tracker = ResourceTracker()
        logger.info("[final_endpoints] STEP 2 resource tracker ready")
        logger.info(
            "[final_endpoints] resource tracker init duration=%.3fs RSS_before=%.2f MB RSS_after=%.2f MB",
            time.perf_counter() - started_at,
            rss_before if rss_before is not None else -1.0,
            _process_rss_mb() if _process_rss_mb() is not None else -1.0,
        )
        return _tracker


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 — STATION READINESS (CACHED DATASET LOAD)
# ═════════════════════════════════════════════════════════════════════════════

RESOURCE_WEIGHTS = {"officers": 0.5, "vehicles": 0.3, "tow_trucks": 0.2}


@lru_cache(maxsize=1)
def compute_station_loads(data_file: str) -> Dict[str, dict]:
    """Compute per-station load metrics from the historical dataset."""
    import pickle
    cache_path = os.path.join(BASE_DIR, "station_loads_cache.pkl")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    started_at = time.perf_counter()
    rss_before = _process_rss_mb()
    logger.info("[final_endpoints] STEP 4 dataset load")
    
    # Load using memory-efficient shared dataset helper
    df = _load_shared_dataset(data_file)

    active_mask = (df["status"] == "active") | (df["resolved_datetime"].isna() & (df["status"] != "closed"))
    active_subset = df.loc[active_mask, ["police_station", "priority"]]

    unique_stations = df["police_station"].dropna().unique()
    median_resolutions = df.groupby("police_station")["resolution_mins"].median()
    active_counts = active_subset.groupby("police_station").size()
    high_priority_counts = active_subset[active_subset["priority"] == "High"].groupby("police_station").size()

    loads: Dict[str, dict] = {}
    for station in unique_stations:
        act_count = int(active_counts.get(station, 0))
        hp_count = int(high_priority_counts.get(station, 0))
        avg_res = median_resolutions.get(station, np.nan)

        loads[station] = {
            "active_incidents": act_count,
            "high_priority_incidents": hp_count,
            "avg_resolution_mins": round(float(avg_res), 1) if pd.notna(avg_res) else 60.0,
        }

    gc.collect()
    logger.info(
        "[final_endpoints] station loads computed stations=%s duration=%.3fs",
        len(loads),
        time.perf_counter() - started_at,
    )
    logger.info(
        "[final_endpoints] station loads RSS before=%.2f MB after=%.2f MB",
        rss_before if rss_before is not None else -1.0,
        _process_rss_mb() if _process_rss_mb() is not None else -1.0,
    )
    return loads


def compute_readiness_score(
    station: str,
    resource_tracker: ResourceTracker,
    loads: Dict[str, dict],
) -> dict:
    """Readiness score = weighted_resource_ratio / (1 + load_factor)"""
    try:
        res = resource_tracker.get_available_resources(station)
    except ValueError:
        return {"station": station, "readiness_score": 0.0, "error": "Station not in resource DB"}

    load = loads.get(station, {
        "active_incidents": 0,
        "high_priority_incidents": 0,
        "avg_resolution_mins": 60.0,
    })

    resource_ratio = (
        RESOURCE_WEIGHTS["officers"] * (res["officers"] / max(DEFAULT_RESOURCES["officers"], 1)) +
        RESOURCE_WEIGHTS["vehicles"] * (res["vehicles"] / max(DEFAULT_RESOURCES["vehicles"], 1)) +
        RESOURCE_WEIGHTS["tow_trucks"] * (res["tow_trucks"] / max(DEFAULT_RESOURCES["tow_trucks"], 1))
    )

    import math
    effective_load = load["active_incidents"] + 0.5 * load["high_priority_incidents"]
    load_factor = math.log1p(effective_load) / 1.5

    raw_score = resource_ratio / (1.0 + load_factor)
    score     = round(raw_score * 100, 1)

    return {
        "station": station,
        "readiness_score": score,
        "resource_ratio_pct": round(resource_ratio * 100, 1),
        "available_officers": res["officers"],
        "available_vehicles": res["vehicles"],
        "available_tow_trucks": res["tow_trucks"],
        "active_incidents": load["active_incidents"],
        "high_priority_incidents": load["high_priority_incidents"],
        "avg_resolution_mins": load["avg_resolution_mins"],
    }


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5 — LOAD BALANCER (LAZY-INITIALIZED)
# ═════════════════════════════════════════════════════════════════════════════

class LoadBalancer:
    def __init__(self, data_file: str = DATA_FILE):
        self._tracker = _get_tracker()
        self.loads = None
        self._loads_lock = Lock()

    def _ensure_loads(self):
        """Lazy-load station loads on first use."""
        if self.loads is not None:
            return
        with self._loads_lock:
            if self.loads is not None:
                return
            started_at = time.perf_counter()
            rss_before = _process_rss_mb()
            logger.info("[final_endpoints] STEP 3 station load creation")
            logger.info("[LoadBalancer] Computing station loads from historical data …")
            self.loads = compute_station_loads(DATA_FILE)
            logger.info(
                "[final_endpoints] load balancer initialized duration=%.3fs",
                time.perf_counter() - started_at,
            )
            logger.info(
                "[final_endpoints] station loads RSS before=%.2f MB after=%.2f MB",
                rss_before if rss_before is not None else -1.0,
                _process_rss_mb() if _process_rss_mb() is not None else -1.0,
            )

    def _candidate_stations(self, corridor: Optional[str] = None) -> List[str]:
        """Filter stations that historically handle the given corridor."""
        if not corridor:
            return [s for s in STATIONS if s != "No Police Station"]

        try:
            df = _load_dataset(DATA_FILE)
            corridor_stations = (
                df[df["corridor"].str.lower() == corridor.lower()]["police_station"]
                .dropna()
                .unique()
                .tolist()
            )
            if len(corridor_stations) >= 2:
                return corridor_stations
        except Exception:
            pass

        return [s for s in STATIONS if s != "No Police Station"]

    def rank_stations(
        self,
        corridor: Optional[str] = None,
        candidate_stations: Optional[List[str]] = None,
    ) -> List[dict]:
        """Compute and rank readiness scores for candidate stations in a batch."""
        self._ensure_loads()

        if candidate_stations is None:
            candidate_stations = self._candidate_stations(corridor)

        # Batch-fetch all resource rows in one call to prevent 53 sequential DB round-trips
        all_resources = self._tracker.get_all_resources_batch()

        import math
        scores = []
        for station in candidate_stations:
            res = all_resources.get(station)
            if not res:
                # Fallback to single lookup if station wasn't loaded in batch
                try:
                    res = self._tracker.get_available_resources(station)
                except ValueError:
                    scores.append({"station": station, "readiness_score": 0.0, "error": "Station not in resource DB"})
                    continue

            load = self.loads.get(station, {
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

            raw_score = resource_ratio / (1.0 + load_factor)
            score     = round(raw_score * 100, 1)

            scores.append({
                "station": station,
                "readiness_score": score,
                "resource_ratio_pct": round(resource_ratio * 100, 1),
                "available_officers": res["officers"],
                "available_vehicles": res["vehicles"],
                "available_tow_trucks": res["tow_trucks"],
                "active_incidents": load["active_incidents"],
                "high_priority_incidents": load["high_priority_incidents"],
                "avg_resolution_mins": load["avg_resolution_mins"],
            })

        scores.sort(key=lambda x: x["readiness_score"], reverse=True)
        return scores

    def select_station(
        self,
        incident_location: str,
        corridor: Optional[str] = None,
        min_officers: int = 1,
        min_vehicles: int = 1,
    ) -> dict:
        """Main entry point. Returns the best station with explanation."""
        ranked = self.rank_stations(corridor)

        eligible = [
            r for r in ranked
            if r["available_officers"] >= min_officers
            and r["available_vehicles"] >= min_vehicles
        ]

        if not eligible:
            eligible = ranked

        best = eligible[0]

        reasons = []
        if best["readiness_score"] == max(r["readiness_score"] for r in ranked):
            reasons.append("Highest readiness score")
        if best["active_incidents"] == min(r["active_incidents"] for r in eligible):
            reasons.append("Lowest active load")
        if best["available_officers"] >= min_officers and best["available_vehicles"] >= min_vehicles:
            reasons.append("Sufficient resources available")

        return {
            "incident_location": incident_location,
            "recommended_station": best["station"],
            "readiness_score": best["readiness_score"],
            "reason": reasons,
            "station_details": best,
            "all_candidates": [
                {
                    "station": r["station"],
                    "readiness_pct": r["readiness_score"],
                    "active": r["active_incidents"],
                    "officers": r["available_officers"],
                    "vehicles": r["available_vehicles"],
                }
                for r in ranked[:8]
            ],
        }


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6 — HISTORICAL INCIDENT TEXT PREPARATION (shared by TF-IDF pipeline)
# ═════════════════════════════════════════════════════════════════════════════

FEATURE_COLS = [
    "event_cause", "corridor", "junction",
    "priority", "veh_type", "police_station",
]

REQUIRED_COLS = [
    "event_cause", "corridor", "junction", "priority", "veh_type",
    "police_station", "start_datetime", "resolved_datetime", "status"
]


@lru_cache(maxsize=1)
def _load_shared_dataset(path: str) -> pd.DataFrame:
    """
    Load and clean the Astram CSV using an optimized memory-efficient strategy.
    Only the required columns are loaded to keep the footprint within Render Free limits.
    """
    rss_before = _process_rss_mb()
    logger.info("[shared-dataset] loading optimized CSV: %s", path)

    # Resolve actual columns available in the file
    header = pd.read_csv(path, nrows=0, encoding="latin1")
    cols_to_use = [col for col in REQUIRED_COLS if col in header.columns]

    df = pd.read_csv(path, encoding="latin1", usecols=cols_to_use)

    if "start_datetime" in df.columns:
        df["start_dt"] = pd.to_datetime(df["start_datetime"], utc=True, errors="coerce")
        df["day"]  = df["start_dt"].dt.day_name()
        df["hour"] = df["start_dt"].dt.hour
    else:
        df["start_dt"] = pd.NaT
        df["day"] = "unknown"
        df["hour"] = 12

    if "resolved_datetime" in df.columns:
        df["resolved_dt"] = pd.to_datetime(df["resolved_datetime"], utc=True, errors="coerce")
    else:
        df["resolved_dt"] = pd.NaT

    if "start_dt" in df.columns and "resolved_dt" in df.columns:
        df["resolution_mins"] = (df["resolved_dt"] - df["start_dt"]).dt.total_seconds() / 60
    else:
        df["resolution_mins"] = np.nan

    for col in FEATURE_COLS:
        if col in df.columns:
            df[col] = df[col].fillna("unknown")

    gc.collect()
    logger.info(
        "[shared-dataset] CSV loaded rows=%d RSS_before=%.1f MB RSS_after=%.1f MB",
        len(df),
        rss_before if rss_before is not None else -1.0,
        _process_rss_mb() if _process_rss_mb() is not None else -1.0,
    )
    return df


def _build_text_repr(row: pd.Series) -> str:
    """
    Concatenate structured incident fields into a single searchable string.
    Underscores replaced with spaces so TF-IDF tokenises sub-words correctly.
    """
    parts = []
    for col in FEATURE_COLS:
        val = str(row.get(col, "unknown")).strip().lower().replace("_", " ")
        parts.append(val)
    if "day" in row:
        parts.append(str(row["day"]).lower())
    if "hour" in row:
        parts.append(f"hour {row['hour']}")
    return " ".join(parts)


@lru_cache(maxsize=1)
def _load_and_clean(path: str) -> pd.DataFrame:
    """Fallback compatible wrapper routing to the shared loader."""
    return _load_shared_dataset(path)


@lru_cache(maxsize=1)
def _load_dataset(data_file: str) -> pd.DataFrame:
    """Fallback compatible wrapper routing to the shared loader."""
    return _load_shared_dataset(data_file)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 7 — TF-IDF HISTORICAL SEARCH  (replaces FAISS / SentenceTransformer)
# ═════════════════════════════════════════════════════════════════════════════

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine_similarity

# ── Module-level singletons (None until first search request) ────────────────
_hist_df: Optional[pd.DataFrame] = None
_tfidf_vectorizer: Optional[TfidfVectorizer] = None
_tfidf_matrix = None          # scipy sparse matrix, shape (n_docs, n_features)
_historical_init_lock = Lock()


def _initialize_historical_cache() -> None:
    """
    Lazily build the TF-IDF index on the first search call.
    """
    global _hist_df, _tfidf_vectorizer, _tfidf_matrix
    # Fast-path: already initialised
    if _hist_df is not None:
        return

    with _historical_init_lock:
        if _hist_df is not None:       # another thread may have finished while we waited
            return

        import pickle
        cache_path = os.path.join(BASE_DIR, "historical_search_cache.pkl")
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                data = pickle.load(f)
            _hist_df = data["df"]
            _tfidf_vectorizer = data["vectorizer"]
            _tfidf_matrix = data["matrix"]
            return

        started_at = time.perf_counter()
        rss_before = _process_rss_mb()

        # Step 1 — load data (shared optimized loader)
        df = _load_and_clean(DATA_FILE)

        # Step 2 — build per-row text corpus
        corpus = df.apply(_build_text_repr, axis=1).tolist()

        # Step 3 — fit TF-IDF
        vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        matrix = vectorizer.fit_transform(corpus)   # returns scipy sparse CSR

        # Step 4 — assign to module globals atomically
        _hist_df          = df
        _tfidf_vectorizer = vectorizer
        _tfidf_matrix     = matrix

        gc.collect()
        elapsed = time.perf_counter() - started_at
        logger.info(
            "[historical-search] cache initialized in %.2fs "
            "rows=%d vocab=%d RSS_before=%.1f MB RSS_after=%.1f MB",
            elapsed,
            len(df),
            len(vectorizer.vocabulary_),
            rss_before if rss_before is not None else -1.0,
            _process_rss_mb() if _process_rss_mb() is not None else -1.0,
        )


def _load_historical() -> None:
    """Ensure the TF-IDF cache is warm. Raises on failure."""
    _initialize_historical_cache()
    if _hist_df is None or _tfidf_vectorizer is None or _tfidf_matrix is None:
        raise RuntimeError("Historical search cache is unavailable")


# NOTE: No eager warmup at import time — deferred to first request.


def search_similar_incidents(
    query: str,
    top_k: int = 20,
) -> dict:
    """
    Find historical incidents most similar to *query* using TF-IDF cosine similarity.
    """
    started_at = time.perf_counter()
    rss_before = _process_rss_mb()

    # ── 1. Ensure cache is warm ──────────────────────────────────────────────
    _load_historical()
    load_elapsed = time.perf_counter() - started_at

    # ── 2. Vectorise query (same vocabulary as corpus) ───────────────────────
    vec_started = time.perf_counter()
    query_vec = _tfidf_vectorizer.transform([query])   # (1, n_features) sparse
    vec_elapsed = time.perf_counter() - vec_started

    # ── 3. Cosine similarity against full matrix ─────────────────────────────
    search_started = time.perf_counter()
    scores_array = sk_cosine_similarity(query_vec, _tfidf_matrix).flatten()

    # ── Synonym Mapping for Event Causes ─────────────────────────────────────
    synonyms = {
        "rally": "public_event",
        "march": "public_event",
        "gathering": "public_event",
        "demonstration": "protest",
        "vip movement": "vip_movement",
        "vip visit": "vip_movement",
        "convoy": "vip_movement",
        "construction work": "construction",
        "roadwork": "construction",
        "digging": "construction",
        "festival": "public_event",
    }
    all_causes = ["vehicle_breakdown", "pot_holes", "construction", "water_logging", 
                  "accident", "tree_fall", "road_conditions", "congestion", 
                  "public_event", "procession", "vip_movement", "protest", "debris"]

    query_lower = query.lower()
    resolved_cause = None

    # Check exact categories first
    for cause in all_causes:
        if cause.replace("_", " ") in query_lower or cause in query_lower:
            resolved_cause = cause
            break

    # Check synonyms if no exact match
    if not resolved_cause:
        for syn, mapped_cause in synonyms.items():
            if syn in query_lower:
                resolved_cause = mapped_cause
                break

    exact_cause_match = False
    if resolved_cause:
        exact_cause_match = True
        mask = _hist_df["event_cause"].str.lower() == resolved_cause
        # Apply 0.6 * cause_match (1.0) + 0.4 * text_similarity
        scores_array[mask] = (0.6 * 1.0) + (0.4 * scores_array[mask])

    # argsort ascending → take last top_k and reverse for descending order
    top_indices = scores_array.argsort()[-top_k:][::-1]
    search_elapsed = time.perf_counter() - search_started

    # ── 4. Build result rows ─────────────────────────────────────────────────
    matched = _hist_df.iloc[top_indices].copy()
    matched["similarity_score"] = scores_array[top_indices]

    avg_res_time = (
        matched["resolution_mins"].dropna().median()
        if "resolution_mins" in matched.columns else None
    )

    priority_counts = matched["priority"].value_counts()
    most_common_priority = (
        priority_counts.index[0] if not priority_counts.empty else "Unknown"
    )

    outcome_counts = matched["event_cause"].value_counts()
    most_common_outcome = (
        outcome_counts.index[0].replace("_", " ").title()
        if not outcome_counts.empty else "Unknown"
    )

    cases = []
    for _, row in matched.iterrows():
        cases.append({
            "event_cause":    str(row.get("event_cause", "")),
            "corridor":       str(row.get("corridor", "")),
            "junction":       str(row.get("junction", "")),
            "priority":       str(row.get("priority", "")),
            "veh_type":       str(row.get("veh_type", "")),
            "police_station": str(row.get("police_station", "")),
            "status":         str(row.get("status", "")),
            "resolution_mins": (
                round(float(row["resolution_mins"]), 1)
                if pd.notna(row.get("resolution_mins")) else None
            ),
            "similarity_score": round(float(row["similarity_score"]), 4),
        })

    # total_similar: incidents with cosine score >= 0.10
    total_similar = int((scores_array >= 0.10).sum())

    result = {
        "similar_cases":           cases,
        "total_similar":           total_similar,
        "average_resolution_time": round(avg_res_time, 1) if avg_res_time else None,
        "historical_priority":     most_common_priority,
        "most_common_outcome":     most_common_outcome,
        "exact_cause_match":       exact_cause_match,
    }

    elapsed = time.perf_counter() - started_at
    logger.info(
        "[historical-search] search completed in %.2fs "
        "(load=%.3fs vec=%.3fs search=%.3fs) top_k=%d total_similar=%d "
        "RSS_before=%.1f MB RSS_after=%.1f MB",
        elapsed,
        load_elapsed,
        vec_elapsed,
        search_elapsed,
        top_k,
        total_similar,
        rss_before if rss_before is not None else -1.0,
        _process_rss_mb() if _process_rss_mb() is not None else -1.0,
    )
    return result


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 8 — DISPATCH PIPELINE (LAZY-LOADED LOAD BALANCER)
# ═════════════════════════════════════════════════════════════════════════════

_lb: Optional[LoadBalancer] = None
_lb_lock = Lock()


def _get_balancer() -> LoadBalancer:
    global _lb
    if _lb is None:
        with _lb_lock:
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
    started_at = time.perf_counter()
    rss_before = _process_rss_mb()
    snapshot_before = tracemalloc.take_snapshot() if tracemalloc.is_tracing() else None
    lb = _get_balancer()

    # Step 1 – Historical context
    history_started_at = time.perf_counter()
    history = search_similar_incidents(incident_text, top_k=search_top_k)
    logger.info(
        "[final_endpoints] dispatch history_search duration=%.3fs",
        time.perf_counter() - history_started_at,
    )

    # Step 2 - Dynamic Resource Recommendation Heuristic
    hist_priority = history.get("historical_priority", "low").lower()

    has_heavy_vehicle = any(c.get("veh_type") in ["heavy_vehicle", "bus"] for c in history["similar_cases"])
    has_planned_event = any(c.get("event_cause") in ["public_event", "procession", "vip_movement", "protest"] for c in history["similar_cases"])

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

    # Step 3 – Station selection
    select_started_at = time.perf_counter()
    selection = lb.select_station(
        incident_location=incident_text,
        corridor=corridor,
        min_officers=rec_officers,
        min_vehicles=rec_vehicles,
    )
    logger.info(
        "[final_endpoints] dispatch select_station duration=%.3fs",
        time.perf_counter() - select_started_at,
    )

    logger.info(
        "[final_endpoints] dispatch total duration=%.3fs",
        time.perf_counter() - started_at,
    )
    _log_memory_delta(
        "dispatch",
        started_at,
        rss_before,
        snapshot_before,
    )
    # Step 4 - Simple Diversion Route Logic
    diversion_route = "Standard local diversion (deploy traffic wardens at preceding junction)"
    if corridor:
        corridor_lower = corridor.lower()
        if "outer ring road" in corridor_lower or "orr" in corridor_lower:
            diversion_route = "Recommended Diversion: Use Inner Ring Road / Old Airport Road via nearest major interchange."
        elif "mysore road" in corridor_lower:
            diversion_route = "Recommended Diversion: Divert traffic via West of Chord Road / Magadi Road."
        elif "bellary road" in corridor_lower:
            diversion_route = "Recommended Diversion: Divert via New BEL Road / Tumkur Road."
        elif "tumkur road" in corridor_lower:
            diversion_route = "Recommended Diversion: Divert via Magadi Road / Outer Ring Road (North)."
        elif "hosur road" in corridor_lower:
            diversion_route = "Recommended Diversion: Divert via Bannerghatta Road / Electronic City elevated tollway."
        elif "old madras road" in corridor_lower:
            diversion_route = "Recommended Diversion: Divert via Old Airport Road / Swami Vivekananda Road."
    elif incident_text:
        incident_lower = incident_text.lower()
        if "silk board" in incident_lower:
            diversion_route = "Recommended Diversion: Pre-divert at HSR Layout and BTM Layout junctions."
        elif "mekhri circle" in incident_lower:
            diversion_route = "Recommended Diversion: Divert traffic via Jayamahal Road and Sankey Road."

    return {
        "dispatch": {
            "incident": incident_text,
            "recommended_station": selection["recommended_station"],
            "readiness_score": selection["readiness_score"],
            "reasons": selection["reason"],
            "top_candidates": selection["all_candidates"],
        },
        "recommended_resources": {
            "officers": rec_officers,
            "vehicles": rec_vehicles,
            "tow_trucks": rec_tow,
            "barricades": rec_barricades,
            "suggested_diversion_route": diversion_route,
            "justification": "Based on historical similarities: " + "; ".join(reasoning)
        },
        "historical_context": {
            "similar_cases": history["total_similar"],
            "average_resolution_time": history["average_resolution_time"],
            "historical_priority": history["historical_priority"],
            "most_common_outcome": history["most_common_outcome"],
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 9 — BENGALURU TRAFFIC NETWORK GRAPH (CORRIDOR RIPPLE SIMULATOR)
# ═════════════════════════════════════════════════════════════════════════════

BENGALURU_NODES = {
    # --- CENTRAL HUB & CONNECTIONS ---
    "Majestic": {"lat": 12.9779, "lon": 77.5724},
    "Corporation Circle": {"lat": 12.9680, "lon": 77.5890},
    "Hudson Circle": {"lat": 12.9664, "lon": 77.5880},
    "Town Hall": {"lat": 12.9649, "lon": 77.5852},
    "Richmond Circle": {"lat": 12.9634, "lon": 77.5976},
    "Minerva Circle": {"lat": 12.9575, "lon": 77.5732},
    "Dairy Circle": {"lat": 12.9428, "lon": 77.6012},

    # --- NORTH CORRIDOR (Bellary Road & ORR North) ---
    "Mekhri Circle": {"lat": 13.0076, "lon": 77.5896},
    "Hebbal": {"lat": 13.0358, "lon": 77.5970},
    "Sanjay Nagar": {"lat": 13.0305, "lon": 77.5821},
    "RT Nagar": {"lat": 13.0185, "lon": 77.5932},
    "Ganganagar Circle": {"lat": 13.0122, "lon": 77.5910},
    "Nagavara Junction": {"lat": 13.0416, "lon": 77.6244},
    "Manyata Tech Park": {"lat": 13.0441, "lon": 77.6225},

    # --- EAST CORRIDOR (Old Madras Road, ITPL & ORR East) ---
    "KR Puram": {"lat": 13.0110, "lon": 77.7040},
    "Tin Factory": {"lat": 13.0163, "lon": 77.6758},
    "Indiranagar 100ft Rd": {"lat": 12.9647, "lon": 77.6382},
    "HAL Old Airport Road": {"lat": 12.9592, "lon": 77.6641},
    "Marathahalli": {"lat": 12.9562, "lon": 77.7011},
    "Whitefield": {"lat": 12.9866, "lon": 77.7341},

    # --- SOUTH-EAST CORRIDOR (Outer Ring Road South) ---
    "Silk Board": {"lat": 12.9176, "lon": 77.6244},
    "HSR Layout": {"lat": 12.9128, "lon": 77.6385},
    "Agara Junction": {"lat": 12.9261, "lon": 77.6482},
    "Iblur Junction": {"lat": 12.9213, "lon": 77.6715},
    "Bellandur": {"lat": 12.9304, "lon": 77.6784},
    "Electronic City": {"lat": 12.8452, "lon": 77.6602},

    # --- WEST & NORTH-WEST CORRIDOR (Tumkur Road & Mysore Road) ---
    "Yeshwanthpur": {"lat": 13.0206, "lon": 77.5560},
    "Goraguntepalya": {"lat": 13.0286, "lon": 77.5385},
    "Peenya Junction": {"lat": 13.0285, "lon": 77.5186},
    "Tumkur Road": {"lat": 13.0380, "lon": 77.5120},
    "Jalahalli Cross": {"lat": 13.0378, "lon": 77.5022},
    "Mysore Road": {"lat": 12.9461, "lon": 77.5255},
    "Mathikere": {"lat": 13.0322, "lon": 77.5585}
}

BENGALURU_EDGES = [
    # Central Core Loops
    ("Majestic", "Corporation Circle"),
    ("Majestic", "Mekhri Circle"),
    ("Majestic", "Yeshwanthpur"),
    ("Majestic", "Mysore Road"),
    ("Corporation Circle", "Hudson Circle"),
    ("Hudson Circle", "Town Hall"),
    ("Hudson Circle", "Richmond Circle"),
    ("Town Hall", "Minerva Circle"),
    ("Minerva Circle", "Dairy Circle"),
    
    # West Corridor & Tumkur Road Spine
    ("Goraguntepalya", "Yeshwanthpur"),
    ("Goraguntepalya", "Peenya Junction"),
    ("Peenya Junction", "Tumkur Road"),
    ("Tumkur Road", "Jalahalli Cross"),
    ("Yeshwanthpur", "Mathikere"),
    ("Mathikere", "Mekhri Circle"),

    # North Corridor Spine (Bellary Road & NH44)
    ("Mekhri Circle", "Ganganagar Circle"),
    ("Ganganagar Circle", "RT Nagar"),
    ("RT Nagar", "Sanjay Nagar"),
    ("Mekhri Circle", "Hebbal"),
    ("Hebbal", "Nagavara Junction"),
    ("Nagavara Junction", "Manyata Tech Park"),
    ("Nagavara Junction", "KR Puram"),

    # East Corridor Spine (Old Madras Rd & ITPL)
    ("KR Puram", "Tin Factory"),
    ("Tin Factory", "Indiranagar 100ft Rd"),
    ("Indiranagar 100ft Rd", "HAL Old Airport Road"),
    ("HAL Old Airport Road", "Marathahalli"),
    ("Tin Factory", "Marathahalli"),
    ("Marathahalli", "Whitefield"),

    # South-East Ring Road Loop (ORR South)
    ("Marathahalli", "Bellandur"),
    ("Bellandur", "Iblur Junction"),
    ("Iblur Junction", "Agara Junction"),
    ("Agara Junction", "HSR Layout"),
    ("HSR Layout", "Silk Board"),
    ("Silk Board", "Electronic City"),
    ("Silk Board", "Dairy Circle"),
    ("Mysore Road", "Silk Board")
]

traffic_graph = nx.Graph()
for node, coords in BENGALURU_NODES.items():
    traffic_graph.add_node(node, lat=coords["lat"], lon=coords["lon"])
traffic_graph.add_edges_from(BENGALURU_EDGES)



def run_ripple_bfs(start_node: str, max_depth: int) -> list:
    """Executes BFS traversal to simulate traffic ripple propagation."""
    matched_start = None
    for node in traffic_graph.nodes:
        if node.lower() == start_node.lower():
            matched_start = node
            break

    if not matched_start:
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

                if next_dist == 1:
                    severity = "high"
                    time_taken = 15
                elif next_dist == 2:
                    severity = "medium"
                    time_taken = 30
                elif next_dist == 3:
                    severity = "low"
                    time_taken = 45
                else:
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
# SECTION 10 — REST ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

def _int_param(val, default=0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _bad_request(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


def _log_endpoint_response(endpoint_name: str, started_at: float, response):
    flask_response = app.make_response(response)
    logger.info(
        "[final_endpoints:%s] <- %s %s status=%s duration=%.3fs",
        endpoint_name,
        request.method,
        request.path,
        flask_response.status_code,
        time.perf_counter() - started_at,
    )
    return flask_response


# ── Health Check ─────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "SentinelAI Unified API"
    })

@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "message": "SentinelAI Unified API is running",
        "endpoints": ["/health", "/predict", "/stations", "/historical-search", "/dispatch", "/station-readiness"]
    })


# ── CatBoost Prediction ─────────────────────────────────────────────────────

@app.route("/predict", methods=["POST"])
def predict():
    try:
        _load_catboost_models()  # Lazy-load on first call
        payload = request.get_json()

        # ── Risk Model ───────────────────────────────────────────────────
        X_risk = build_dataframe(payload, RISK_FEATURES)
        risk_prediction = _risk_model.predict(X_risk)
        risk_class = int(risk_prediction[0])
        risk_prob = float(_risk_model.predict_proba(X_risk)[0][1])
        predicted_priority = "high" if risk_class == 1 else "low"

        payload["priority"] = predicted_priority

        # ── Road Closure Model ───────────────────────────────────────────
        X_closure = build_dataframe(payload, CLOSURE_FEATURES)
        closure_prob = float(_closure_model.predict_proba(X_closure)[0][1])
        closure_prediction = int(_closure_model.predict(X_closure)[0])

        # ── Resolution Time Model ────────────────────────────────────────
        X_time = build_dataframe(payload, TIME_FEATURES)
        log_time = float(_time_model.predict(X_time)[0])
        expected_minutes = float(np.expm1(log_time))

        # ── Response ─────────────────────────────────────────────────────
        response = {
            "incident": {
                "incident_id": None,
                "event_type": payload.get("event_type_grouped", "unknown"),
                "event_cause": payload.get("event_cause", "unknown"),
                "corridor": payload.get("corridor", "unknown"),
            },
            "predictions": {
                "priority": predicted_priority,
                "priority_confidence": round(risk_prob * 100, 2),
                "road_closure_required": bool(closure_prediction),
                "road_closure_probability": round(closure_prob * 100, 2),
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
    return jsonify(_get_tracker().list_all_stations())


@app.route("/stations/<station>", methods=["GET"])
def get_station(station: str):
    """GET /stations/<station> – resource snapshot."""
    try:
        return jsonify(_get_tracker().get_available_resources(station))
    except ValueError as e:
        return _bad_request(str(e), 404)


@app.route("/stations/<station>/allocate", methods=["POST"])
def allocate(station: str):
    """POST /stations/<station>/allocate"""
    data = request.get_json(silent=True) or {}
    try:
        result = _get_tracker().allocate_resources(
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
    """POST /stations/<station>/release"""
    data = request.get_json(silent=True) or {}
    try:
        result = _get_tracker().release_resources(
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
    """POST /historical-search"""
    started_at = time.perf_counter()
    rss_before = _process_rss_mb()
    snapshot_before = tracemalloc.take_snapshot() if tracemalloc.is_tracing() else None
    body_size = len(request.get_data(cache=True) or b"")
    logger.info(
        "[final_endpoints:historical-search] -> %s %s body_bytes=%s",
        request.method,
        request.path,
        body_size,
    )
    response = None
    try:
        data = request.get_json()
        query = data.get("query", "")
        top_k = _int_param(data.get("top_k"), default=20)

        if not query:
            response = _log_endpoint_response(
                "historical-search",
                started_at,
                _bad_request("'query' field is required."),
            )
            return response

        result = search_similar_incidents(query, top_k=top_k)
        response = _log_endpoint_response("historical-search", started_at, jsonify(result))
        return response

    except Exception as e:
        traceback.print_exc()
        response = _log_endpoint_response(
            "historical-search",
            started_at,
            (jsonify({"success": False, "error": str(e)}), 500),
        )
        return response
    finally:
        if response is not None:
            _log_memory_delta(
                "historical-search endpoint",
                started_at,
                rss_before,
                snapshot_before,
            )


# ── Dispatch Endpoint ────────────────────────────────────────────────────────

@app.route("/dispatch", methods=["POST"])
def dispatch_endpoint():
    """POST /dispatch"""
    started_at = time.perf_counter()
    rss_before = _process_rss_mb()
    snapshot_before = tracemalloc.take_snapshot() if tracemalloc.is_tracing() else None
    body_size = len(request.get_data(cache=True) or b"")
    logger.info(
        "[final_endpoints:dispatch] -> %s %s body_bytes=%s",
        request.method,
        request.path,
        body_size,
    )
    response = None
    try:
        data = request.get_json(silent=True) or {}
        incident_text = data.get("incident_text", "")

        if not incident_text:
            response = _log_endpoint_response(
                "dispatch",
                started_at,
                _bad_request("'incident_text' field is required."),
            )
            return response

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
        response = _log_endpoint_response("dispatch", started_at, jsonify(result))
        return response

    except Exception as e:
        traceback.print_exc()
        response = _log_endpoint_response(
            "dispatch",
            started_at,
            (jsonify({"success": False, "error": str(e)}), 500),
        )
        return response
    finally:
        if response is not None:
            _log_memory_delta(
                "dispatch endpoint",
                started_at,
                rss_before,
                snapshot_before,
            )


# ── Station Readiness Endpoint ───────────────────────────────────────────────

@app.route("/station-readiness", methods=["GET"])
def station_readiness():
    """GET /station-readiness?station=Peenya"""
    started_at = time.perf_counter()
    body_size = len(request.get_data(cache=True) or b"")
    logger.info(
        "[final_endpoints:station-readiness] -> %s %s body_bytes=%s",
        request.method,
        request.path,
        body_size,
    )
    try:
        loads_started_at = time.perf_counter()
        loads = compute_station_loads(DATA_FILE)
        logger.info(
            "[final_endpoints:station-readiness] loads duration=%.3fs",
            time.perf_counter() - loads_started_at,
        )
        station_param = request.args.get("station")

        if station_param:
            single_started_at = time.perf_counter()
            result = compute_readiness_score(station_param, _get_tracker(), loads)
            logger.info(
                "[final_endpoints:station-readiness] single-station duration=%.3fs",
                time.perf_counter() - single_started_at,
            )
            return _log_endpoint_response("station-readiness", started_at, jsonify(result))

        # ── All-stations path: batch fetch ──────────────────────────────────
        batch_started_at = time.perf_counter()
        all_resources = _get_tracker().get_all_resources_batch()

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
                "station": station,
                "readiness_score": score,
                "resource_ratio_pct": round(resource_ratio * 100, 1),
                "available_officers": res["officers"],
                "available_vehicles": res["vehicles"],
                "available_tow_trucks": res["tow_trucks"],
                "active_incidents": load["active_incidents"],
                "high_priority_incidents": load["high_priority_incidents"],
                "avg_resolution_mins": load["avg_resolution_mins"],
            })

        results.sort(key=lambda x: x["readiness_score"], reverse=True)
        logger.info(
            "[final_endpoints:station-readiness] batch duration=%.3fs",
            time.perf_counter() - batch_started_at,
        )
        return _log_endpoint_response("station-readiness", started_at, jsonify(results))

    except Exception as e:
        traceback.print_exc()
        return _log_endpoint_response(
            "station-readiness",
            started_at,
            (jsonify({"success": False, "error": str(e)}), 500),
        )


# ── Corridor Ripple Simulator Endpoint ───────────────────────────────────────

@app.route("/simulate-ripple", methods=["POST"])
def simulate_ripple():
    """POST /simulate-ripple"""
    try:
        data = request.get_json(silent=True) or {}
        location = data.get("location", "")
        closure_prob = float(data.get("closure_probability", 0.0))

        if not location:
            return _bad_request("'location' field is required.")

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





# ─────────────────────────────────────────────────────────────────────────────
# SAFE HARBOR SINGLETON (LAZY INITIALIZATION)
# ─────────────────────────────────────────────────────────────────────────────

_harbor_identifier = None
_harbor_lock = Lock()

def _get_harbor_identifier() -> KerbSafeHarborIdentifier:
    """Lazily load and build the DBSCAN Safe Harbor clusters on first access."""
    global _harbor_identifier
    if _harbor_identifier is None:
        with _harbor_lock:
            if _harbor_identifier is None:
                # DATA_FILE is the path to your Astram CSV already defined in models.py
                _harbor_identifier = KerbSafeHarborIdentifier(DATA_FILE)
    return _harbor_identifier

@app.route("/recommend-safe-harbor", methods=["POST"])
def recommend_safe_harbor():
    """POST /recommend-safe-harbor - Finds nearest physical push harbor."""
    try:
        data = request.get_json(silent=True) or {}
        lat_val = data.get("latitude")
        lon_val = data.get("longitude")

        if lat_val is None or lon_val is None:
            return jsonify({"error": "Fields 'latitude' and 'longitude' are required."}), 400

        lat = float(lat_val)
        lon = float(lon_val)

        # Retrieve the lazy-loaded instance
        identifier = _get_harbor_identifier()
        recommendation = identifier.find_nearest_harbor(lat, lon)

        if not recommendation:
            return jsonify({
                "found": False,
                "message": "No historical safe harbor within 400 meters of this coordinate."
            }), 200

        return jsonify({
            "found": True,
            "recommendation": recommendation
        }), 200

    except ValueError:
        return jsonify({"error": "Coordinates must be numeric floating points."}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

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