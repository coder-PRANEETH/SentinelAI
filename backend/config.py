"""
config.py
SentinelAI Flask Backend Configuration
All settings come from environment variables with documented defaults.
Readiness weights are stored here so an admin can update without redeployment.
"""

import os
from datetime import timedelta

# ─────────────────────────────────────────────────────────────────────────────
# BASE PATHS
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sentinel:sentinel@localhost:5432/sentinelai"
)

# ─────────────────────────────────────────────────────────────────────────────
# REDIS
# ─────────────────────────────────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ─────────────────────────────────────────────────────────────────────────────
# JWT
# ─────────────────────────────────────────────────────────────────────────────

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
JWT_ACCESS_TOKEN_EXPIRES = timedelta(
    hours=int(os.getenv("JWT_ACCESS_TOKEN_HOURS", "8"))
)
# Redis blocklist TTL matches token expiry
JWT_BLOCKLIST_TTL = int(os.getenv("JWT_ACCESS_TOKEN_HOURS", "8")) * 3600

# ─────────────────────────────────────────────────────────────────────────────
# ML MODELS
# ─────────────────────────────────────────────────────────────────────────────

CATBOOST_MODEL_DIR = os.getenv(
    "CATBOOST_MODEL_DIR",
    os.path.join(PROJECT_ROOT, "trained_model")
)

RESOURCE_MODULE_DIR = os.path.join(
    PROJECT_ROOT,
    "Resource Intelligence and Historical Operation Module"
)

FAISS_INDEX_PATH = os.getenv(
    "FAISS_INDEX_PATH",
    os.path.join(RESOURCE_MODULE_DIR, "faiss_index")
)

DATA_FILE = os.path.join(
    RESOURCE_MODULE_DIR,
    "Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv",
)

DB_FILE = os.path.join(RESOURCE_MODULE_DIR, "resources.db")

SENTENCE_TRANSFORMER_MODEL = os.getenv(
    "SENTENCE_TRANSFORMER_MODEL",
    "all-MiniLM-L6-v2"
)

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────

TOP_K_HISTORICAL = int(os.getenv("TOP_K_HISTORICAL", "10"))
MIN_SIMILARITY_THRESHOLD = float(os.getenv("MIN_SIMILARITY_THRESHOLD", "0.7"))

# ─────────────────────────────────────────────────────────────────────────────
# READINESS SCORE WEIGHTS
# Stored in config (not hardcoded) so admin can update without redeployment.
# These are surfaced as /admin/config in a future endpoint.
# ─────────────────────────────────────────────────────────────────────────────

READINESS_WEIGHTS = {
    "officer":   float(os.getenv("WEIGHT_OFFICER",   "0.35")),
    "vehicle":   float(os.getenv("WEIGHT_VEHICLE",   "0.30")),
    "tow":       float(os.getenv("WEIGHT_TOW",       "0.15")),
    "barricade": float(os.getenv("WEIGHT_BARRICADE", "0.10")),
    "penalty":   float(os.getenv("WEIGHT_PENALTY",   "0.10")),
}

# ─────────────────────────────────────────────────────────────────────────────
# SECURITY
# ─────────────────────────────────────────────────────────────────────────────

# Max consecutive failed login attempts before account lock
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
# Minutes to lock account after too many failures
ACCOUNT_LOCK_MINUTES = int(os.getenv("ACCOUNT_LOCK_MINUTES", "30"))

# ─────────────────────────────────────────────────────────────────────────────
# CACHE TTL (seconds)
# ─────────────────────────────────────────────────────────────────────────────

STATION_LIST_CACHE_TTL = int(os.getenv("STATION_LIST_CACHE_TTL", "30"))
READINESS_CACHE_TTL = int(os.getenv("READINESS_CACHE_TTL", "60"))

# ─────────────────────────────────────────────────────────────────────────────
# RATE LIMITING
# ─────────────────────────────────────────────────────────────────────────────

RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "100 per minute")
RATELIMIT_STORAGE_URL = REDIS_URL

# ─────────────────────────────────────────────────────────────────────────────
# MISC
# ─────────────────────────────────────────────────────────────────────────────

API_VERSION = "1.0.0"


def _parse_cors_origins(raw_value: str):
    """
    Normalize CORS origins from env.

    Accepts:
    - "*" for wildcard matching
    - a single origin string
    - a comma-separated list of origins
    """
    value = (raw_value or "").strip()
    if not value or value == "*":
        return "*"
    return [origin.strip() for origin in value.split(",") if origin.strip()]


CORS_ORIGINS = _parse_cors_origins(os.getenv("CORS_ORIGINS", "*"))
