"""
inventory_api.py
SentinelAI – Inventory REST API (Flask)
Exposes resource tracker operations over HTTP.

Run:  python inventory_api.py
"""

from flask import Flask, request, jsonify, abort
from resource_tracker import ResourceTracker

app     = Flask(__name__)
tracker = ResourceTracker()


# ── Helpers ──────────────────────────────────────────────────────────────────
def _int(val, default=0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _bad(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/stations")
def list_stations():
    """GET /stations – list all stations with current resources."""
    return jsonify(tracker.list_all_stations())


@app.get("/stations/<station>")
def get_station(station: str):
    """GET /stations/<station> – resource snapshot."""
    try:
        return jsonify(tracker.get_available_resources(station))
    except ValueError as e:
        return _bad(str(e), 404)


@app.post("/stations/<station>/allocate")
def allocate(station: str):
    """
    POST /stations/<station>/allocate
    Body (JSON): { "officers": 2, "vehicles": 1, "tow_trucks": 1, "barricades": 0 }
    """
    data = request.get_json(silent=True) or {}
    try:
        result = tracker.allocate_resources(
            station,
            officers   = _int(data.get("officers")),
            vehicles   = _int(data.get("vehicles")),
            tow_trucks = _int(data.get("tow_trucks")),
            barricades = _int(data.get("barricades")),
        )
        return jsonify(result), 200
    except ValueError as e:
        return _bad(str(e))


@app.post("/stations/<station>/release")
def release(station: str):
    """
    POST /stations/<station>/release
    Body (JSON): { "officers": 2, "vehicles": 1, "tow_trucks": 1, "barricades": 0 }
    """
    data = request.get_json(silent=True) or {}
    try:
        result = tracker.release_resources(
            station,
            officers   = _int(data.get("officers")),
            vehicles   = _int(data.get("vehicles")),
            tow_trucks = _int(data.get("tow_trucks")),
            barricades = _int(data.get("barricades")),
        )
        return jsonify(result), 200
    except ValueError as e:
        return _bad(str(e))


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "SentinelAI Inventory API"})


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5001)
