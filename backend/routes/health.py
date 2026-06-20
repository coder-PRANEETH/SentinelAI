"""
routes/health.py
GET /health — component status check (no auth required).
"""

from datetime import datetime, timezone
from flask import Blueprint, jsonify
from sqlalchemy import text

from models.base import db
from services.ml_service import ml_service
from config import API_VERSION

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    status_components = {}

    # Database check
    try:
        db.session.execute(text("SELECT 1"))
        status_components["database"] = "connected"
    except Exception as e:
        status_components["database"] = f"error: {str(e)}"

    # ML model statuses
    ml_status = ml_service.models_status()
    status_components["catboost_models"] = (
        "loaded" if ml_service.catboost_ready() else "missing"
    )
    status_components["faiss_index"] = ml_status["faiss_index"]
    status_components["sentence_transformer"] = ml_status["sentence_transformer"]

    # Redis check
    try:
        from extensions import redis_client
        if redis_client:
            redis_client.ping()
            status_components["redis"] = "connected"
        else:
            status_components["redis"] = "not_configured"
    except Exception as e:
        status_components["redis"] = f"error: {str(e)}"

    # Overall status
    is_degraded = (
        status_components["database"] != "connected"
        or status_components["catboost_models"] != "loaded"
    )
    overall = "degraded" if is_degraded else "healthy"

    return jsonify({
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": status_components,
        "version": API_VERSION,
    }), 200
