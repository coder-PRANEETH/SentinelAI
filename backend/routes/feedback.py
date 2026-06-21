"""
routes/feedback.py
POST /incident-feedback — Submit ground truth feedback after incident closure.
Computes model drift alert if prediction error > thresholds.
"""

import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError

from models.base import db
from models.incidents import Incident
from models.predictions import Prediction
from models.incident_feedback import IncidentFeedback
from services.sentinel_incident_service import (
    sentinel_incident_service, IncidentStateMachineError
)
from middleware.rbac import require_role
from utils.validators import FeedbackSchema, is_valid_uuid

logger = logging.getLogger(__name__)
feedback_bp = Blueprint("feedback", __name__)
_feedback_schema = FeedbackSchema()

# Drift thresholds
RESOLUTION_DRIFT_THRESHOLD_MINUTES = 30


@feedback_bp.route("/incident-feedback", methods=["POST"])
@jwt_required()
@require_role("OPERATOR", "SUPERVISOR", "ADMIN")
def submit_feedback():
    try:
        data = _feedback_schema.load(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": "VALIDATION_ERROR", "message": "Invalid request body", "details": e.messages}), 400

    user_id = get_jwt_identity()
    if user_id and not is_valid_uuid(user_id):
        return jsonify({"error": "UNAUTHORIZED", "message": "Invalid token identity format", "details": {}}), 401
    claims = get_jwt()
    user_role = claims.get("role", "")

    incident_id = data["incident_id"]

    # Fetch incident
    incident = Incident.query.filter_by(incident_id=incident_id).first()
    if not incident:
        return jsonify({"error": "NOT_FOUND", "message": f"Incident '{incident_id}' not found", "details": {}}), 404

    if incident.status in ("RESOLVED", "CLOSED"):
        return jsonify({"error": "CONFLICT", "message": "Feedback already submitted for this incident", "details": {}}), 409

    # Fetch prediction for drift calculation
    prediction = Prediction.query.filter_by(incident_id=incident_id).first()

    actual_priority = data["actual_priority"]
    actual_resolution = data["actual_resolution_time_minutes"]

    priority_accurate = None
    resolution_error = None
    model_drift_alert = False

    if prediction:
        priority_accurate = (prediction.predicted_priority == actual_priority)
        if prediction.predicted_resolution_minutes is not None:
            resolution_error = abs(actual_resolution - prediction.predicted_resolution_minutes)
            if resolution_error > RESOLUTION_DRIFT_THRESHOLD_MINUTES:
                model_drift_alert = True
        if not priority_accurate:
            model_drift_alert = True

    # Save feedback
    feedback = IncidentFeedback(
        incident_id=incident_id,
        actual_priority=actual_priority,
        actual_resolution_time_minutes=actual_resolution,
        road_closure_occurred=data["road_closure_occurred"],
        outcome_description=data.get("outcome_description"),
        submitted_by=user_id,
        priority_accurate=priority_accurate,
        resolution_error_minutes=resolution_error,
    )
    db.session.add(feedback)

    # Mark incident as resolved when feedback is submitted.
    incident.status = "RESOLVED"
    incident.resolved_at = datetime.now(timezone.utc)
    incident.updated_at = datetime.now(timezone.utc)
    db.session.add(incident)

    db.session.commit()

    response = {
        "success": True,
        "feedback_id": str(feedback.feedback_id),
        "incident_id": incident_id,
        "incident_status": "RESOLVED",
        "priority_accurate": priority_accurate,
        "resolution_error_minutes": resolution_error,
        "model_drift_alert": model_drift_alert,
    }

    if model_drift_alert:
        response["drift_reason"] = (
            "Priority mismatch" if not priority_accurate else
            f"Resolution error {resolution_error} min exceeds {RESOLUTION_DRIFT_THRESHOLD_MINUTES} min threshold"
        )

    return jsonify(response), 200
