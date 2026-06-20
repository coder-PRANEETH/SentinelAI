"""
routes/historical.py
POST /historical-search
GET /station-readiness
"""

import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from services.ml_service import ml_service
from services.readiness_service import readiness_service
from middleware.rbac import require_role
from utils.validators import HistoricalSearchSchema, ReadinessQuerySchema
from config import FAISS_INDEX_PATH, TOP_K_HISTORICAL, MIN_SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)
historical_bp = Blueprint("historical", __name__)
_search_schema = HistoricalSearchSchema()
_readiness_schema = ReadinessQuerySchema()


@historical_bp.route("/historical-search", methods=["POST"])
@jwt_required()
def historical_search():
    """
    Semantic search over historical incidents using FAISS + sentence embeddings.
    Returns similar cases + aggregate stats + low confidence warning if < 3 results.
    """
    try:
        data = _search_schema.load(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": "VALIDATION_ERROR", "message": "Invalid request body", "details": e.messages}), 400

    query_text = data.get("query_text") or data.get("query") or ""
    if not query_text:
        return jsonify({"error": "VALIDATION_ERROR", "message": "'query_text' is required", "details": {}}), 400

    top_k = data.get("top_k", TOP_K_HISTORICAL)
    min_similarity = data.get("min_similarity", MIN_SIMILARITY_THRESHOLD)

    try:
        result = ml_service.historical_search(
            query_text=query_text,
            top_k=top_k,
            min_similarity=min_similarity,
            faiss_index_path=FAISS_INDEX_PATH,
        )
    except RuntimeError as e:
        return jsonify({
            "error": "SERVICE_UNAVAILABLE",
            "message": str(e),
            "details": ml_service.models_status(),
        }), 503
    except Exception as e:
        logger.exception("Historical search failed")
        return jsonify({"error": "INTERNAL_ERROR", "message": str(e), "details": {}}), 500

    return jsonify(result), 200


@historical_bp.route("/station-readiness", methods=["GET"])
@jwt_required()
def station_readiness():
    """
    Return all stations ranked by readiness score.
    Optionally filter by minimum resource requirements.
    """
    try:
        params = _readiness_schema.load(request.args.to_dict())
    except ValidationError as e:
        return jsonify({"error": "VALIDATION_ERROR", "message": "Invalid query parameters", "details": e.messages}), 400

    required = {
        "officers": params.get("officers", 0),
        "vehicles": params.get("patrol_vehicles", 0),
        "tow_trucks": params.get("tow_trucks", 0),
        "barricades": params.get("barricades", 0),
    }
    min_readiness = params.get("min_readiness", 0.0)

    candidates = readiness_service.rank_candidates(required_resources=required)

    # Filter by min_readiness if specified
    if min_readiness > 0:
        candidates = [c for c in candidates if c.get("readiness_score", 0) >= min_readiness]

    return jsonify({
        "stations": candidates,
        "total": len(candidates),
        "filter_applied": required,
    }), 200
