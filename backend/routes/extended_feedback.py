import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from models.base import db
from models.incidents import Incident
from models.incident_feedback import IncidentFeedback
from models.predictions import Prediction
from utils.validators import FeedbackSchema

logger = logging.getLogger(__name__)
extended_feedback_bp = Blueprint("extended_feedback", __name__)
_feedback_schema = FeedbackSchema()

RESOLUTION_DRIFT_THRESHOLD_MINUTES = 30


def _normalize_extended_payload(data: dict) -> dict:
    """
    Accept the extended form field names and normalize them to the canonical
    feedback schema used by the database.
    """
    return {
        "incident_id": (data.get("incident_id") or "").strip(),
        "actual_priority": data.get("actual_priority"),
        "actual_resolution_time_minutes": (
            data.get("actual_resolution_time_minutes")
            if data.get("actual_resolution_time_minutes") is not None
            else data.get("actual_resolution_time")
        ),
        "road_closure_occurred": (
            data.get("road_closure_occurred")
            if data.get("road_closure_occurred") is not None
            else data.get("actual_closure")
        ),
        "outcome_description": data.get("outcome_description") or data.get("remarks"),
        "operator_id": data.get("operator_id"),
    }


@extended_feedback_bp.route("/feedback", methods=["POST"])
@jwt_required()
def submit_extended_feedback():
    """Submit extended incident feedback using the real feedback schema."""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    try:
        normalized = _normalize_extended_payload(data)
        feedback_data = _feedback_schema.load(normalized)
    except ValidationError as e:
        return (
            jsonify(
                {
                    "error": "VALIDATION_ERROR",
                    "message": "Invalid request body",
                    "details": e.messages,
                }
            ),
            400,
        )

    incident_id = feedback_data["incident_id"]

    # Verify incident exists
    incident = Incident.query.filter_by(incident_id=incident_id).first()
    if not incident:
        return (
            jsonify(
                {
                    "error": "NOT_FOUND",
                    "message": f"Incident '{incident_id}' not found",
                    "details": {},
                }
            ),
            404,
        )

    if incident.status in ("RESOLVED", "CLOSED"):
        return (
            jsonify(
                {
                    "error": "CONFLICT",
                    "message": "Feedback already submitted for this incident",
                    "details": {},
                }
            ),
            409,
        )

    prediction = Prediction.query.filter_by(incident_id=incident_id).first()

    actual_priority = feedback_data["actual_priority"]
    actual_resolution = feedback_data["actual_resolution_time_minutes"]

    priority_accurate = None
    resolution_error = None
    model_drift_alert = False

    if prediction:
        priority_accurate = prediction.predicted_priority == actual_priority
        if prediction.predicted_resolution_minutes is not None:
            resolution_error = abs(actual_resolution - prediction.predicted_resolution_minutes)
            if resolution_error > RESOLUTION_DRIFT_THRESHOLD_MINUTES:
                model_drift_alert = True
        if not priority_accurate:
            model_drift_alert = True

    try:
        feedback = IncidentFeedback(
            incident_id=incident_id,
            actual_priority=actual_priority,
            actual_resolution_time_minutes=actual_resolution,
            road_closure_occurred=feedback_data["road_closure_occurred"],
            outcome_description=feedback_data.get("outcome_description"),
            submitted_by=user_id,
            priority_accurate=priority_accurate,
            resolution_error_minutes=resolution_error,
        )
        db.session.add(feedback)

        incident_status = "RESOLVED"
        incident.status = incident_status
        incident.resolved_at = datetime.now(timezone.utc)
        incident.updated_at = datetime.now(timezone.utc)
        db.session.add(incident)

        db.session.commit()

        response = {
            "success": True,
            "feedback_id": str(feedback.feedback_id),
            "incident_id": incident_id,
            "incident_status": incident_status,
            "priority_accurate": priority_accurate,
            "resolution_error_minutes": resolution_error,
            "model_drift_alert": model_drift_alert,
            "message": "Feedback submitted successfully.",
        }

        if model_drift_alert:
            response["drift_reason"] = (
                "Priority mismatch"
                if not priority_accurate
                else f"Resolution error {resolution_error} min exceeds {RESOLUTION_DRIFT_THRESHOLD_MINUTES} min threshold"
            )

        return jsonify(response), 200

    except Exception as e:
        db.session.rollback()
        logger.exception("Failed to submit extended feedback")
        return jsonify({"error": "INTERNAL_ERROR", "message": str(e), "details": {}}), 500
