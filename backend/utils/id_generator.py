"""
utils/id_generator.py
Generates sequential INC-YYYY-NNNNNN and DIS-YYYY-NNNNNN IDs using a
PostgreSQL sequence (advisory lock + counter in DB) or an in-memory
atomic counter for SQLite/test environments.
"""

import threading
from datetime import datetime, timezone

from models.base import db

_lock = threading.Lock()
_counters: dict = {}  # fallback for non-Postgres envs


def _next_sequence_val(seq_name: str) -> int:
    """Use PostgreSQL nextval() if available, else in-memory counter."""
    try:
        result = db.session.execute(
            db.text(f"SELECT nextval('{seq_name}')")
        ).scalar()
        return int(result)
    except Exception:
        # Fallback: in-memory counter (not suitable for multi-process deployments)
        with _lock:
            _counters[seq_name] = _counters.get(seq_name, 0) + 1
            return _counters[seq_name]


def generate_incident_id() -> str:
    """Generate INC-YYYY-NNNNNN."""
    year = datetime.now(timezone.utc).strftime("%Y")
    seq = _next_sequence_val("incident_id_seq")
    return f"INC-{year}-{seq:06d}"


def generate_dispatch_id() -> str:
    """Generate DIS-YYYY-NNNNNN."""
    year = datetime.now(timezone.utc).strftime("%Y")
    seq = _next_sequence_val("dispatch_id_seq")
    return f"DIS-{year}-{seq:06d}"


def ensure_sequences():
    """Create PostgreSQL sequences if they don't exist (called at app startup)."""
    for seq in ("incident_id_seq", "dispatch_id_seq"):
        try:
            db.session.execute(
                db.text(f"CREATE SEQUENCE IF NOT EXISTS {seq} START 1 INCREMENT 1")
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
