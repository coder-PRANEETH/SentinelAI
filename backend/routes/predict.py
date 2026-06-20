"""
routes/predict.py
POST /predict — ML prediction endpoint.
Runs CatBoost + historical search, saves prediction record.
"""

import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from marshmallow import ValidationError

from models.base import db
from models.incidents import Incident
from models.predictions import Prediction
from services.ml_service import ml_service
from services.sentinel_incident_service import sentinel_incident_service
from middleware.rbac import require_role
from utils.validators import PredictSchema
from config import FAISS_INDEX_PATH, TOP_K_HISTORICAL, MIN_SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)
predict_bp = Blueprint("predict", __name__)
_predict_schema = PredictSchema()


@predict_bp.route("/predict", methods=["POST"])
@jwt_required()
@require_role("OPERATOR", "SUPERVISOR", "ADMIN")
def predict():
    # Validate request
    try:
        data = _predict_schema.load(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": "VALIDATION_ERROR", "message": "Invalid request body", "details": e.messages}), 400

    # Check models loaded
    if not ml_service.catboost_ready():
        return jsonify({
            "error": "SERVICE_UNAVAILABLE",
            "message": "CatBoost models not loaded. Check trained_model/ directory.",
            "details": ml_service.models_status(),
        }), 503

    claims = get_jwt()
    user_id = get_jwt_identity()

    try:
        # Run prediction
        pred_result = ml_service.predict(data)
    except Exception as e:
        logger.exception("CatBoost prediction failed")
        return jsonify({"error": "MODEL_ERROR", "message": str(e), "details": {}}), 422

    # Historical search (non-blocking — degrade gracefully)
    historical = None
    try:
        query_text = (
            f"{data.get('incident_type', '')} {data.get('event_type_grouped', '')} "
            f"{data.get('corridor', '')} {data.get('veh_type_grouped', '')} "
            f"{data.get('event_cause', '')}"
        ).strip()
        historical = ml_service.historical_search(
            query_text=query_text,
            top_k=data.get("top_k", TOP_K_HISTORICAL),
            min_similarity=MIN_SIMILARITY_THRESHOLD,
            faiss_index_path=FAISS_INDEX_PATH,
            data_file=None,
        )
    except Exception as e:
        logger.warning(f"Historical search failed (non-fatal): {e}")

    # Resource recommendation
    resources = ml_service.recommend_resources(
        incident_type=data.get("incident_type", data.get("event_type_grouped", "")),
        priority=pred_result["predicted_priority"],
        vehicle_type=data.get("vehicle_type", data.get("veh_type_grouped", "")),
        road_closure_probability=pred_result["road_closure_probability"],
        hour=data.get("hour_of_day", 12),
    )

    # Save prediction record (if incident_id provided, link it)
    incident_id = data.get("incident_id")
    prediction_record = None
    try:
        prediction_record = Prediction(
            incident_id=incident_id,
            predicted_priority=pred_result["predicted_priority"],
            priority_confidence=pred_result["priority_confidence"],
            priority_reasons=pred_result["priority_reasons"],
            predicted_resolution_minutes=pred_result["predicted_resolution_minutes"],
            resolution_range_low=pred_result["resolution_range_low"],
            resolution_range_high=pred_result["resolution_range_high"],
            road_closure_probability=pred_result["road_closure_probability"],
            road_closure_recommendation=pred_result["road_closure_recommendation"],
            closure_reasons=pred_result["closure_reasons"],
            recommended_resources=resources,
            historical_context=historical,
            model_version=pred_result["model_version"],
        )
        db.session.add(prediction_record)

        # Auto-advance incident to UNDER_ASSESSMENT if linked
        if incident_id:
            incident = Incident.query.filter_by(incident_id=incident_id).first()
            if incident and incident.status == "REPORTED":
                sentinel_incident_service.advance_to_under_assessment(incident_id)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.warning(f"Failed to save prediction record: {e}")

    return jsonify({
        "success": True,
        "incident": {
            "incident_id": incident_id,
            "corridor": data.get("corridor"),
            "event_cause": data.get("event_cause"),
            "event_type": data.get("incident_type", data.get("event_type_grouped")),
        },
        "predictions": {
            "predicted_priority": pred_result["predicted_priority"],
            "priority_confidence": round(pred_result["priority_confidence"] * 100, 2),
            "priority_reasons": pred_result["priority_reasons"],
            "predicted_resolution_minutes": pred_result["predicted_resolution_minutes"],
            "resolution_range": {
                "low": pred_result["resolution_range_low"],
                "high": pred_result["resolution_range_high"],
            },
            "road_closure_probability": round(pred_result["road_closure_probability"] * 100, 2),
            "road_closure_recommendation": pred_result["road_closure_recommendation"],
            "closure_reasons": pred_result["closure_reasons"],
        },
        "recommended_resources": resources,
        "historical_context": historical,
        "prediction_id": str(prediction_record.prediction_id) if prediction_record else None,
    }), 200
