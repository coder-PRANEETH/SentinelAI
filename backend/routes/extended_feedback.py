"""
routes/extended_feedback.py
POST /feedback — Extended ground-truth feedback form with additional fields:
  incident_id, actual_priority, actual_closure, actual_resolution_time,
  officers_used, barricades_used, remarks
"""

import uuid
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models.base import db
from models.incidents import Incident

logger = logging.getLogger(__name__)
extended_feedback_bp = Blueprint("extended_feedback", __name__)


class ExtendedFeedback(db.Model):
    """Standalone feedback table with the exact columns requested."""
    __tablename__ = "extended_feedback"

    feedback_id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    incident_id = db.Column(
        db.String(20),
        db.ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actual_priority = db.Column(db.String(5), nullable=True)        # P1-P4
    actual_closure = db.Column(db.Boolean, nullable=True)           # road closed?
    actual_resolution_time = db.Column(db.Integer, nullable=True)   # minutes
    officers_used = db.Column(db.Integer, nullable=True)
    barricades_used = db.Column(db.Integer, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    submitted_by = db.Column(db.String(36), nullable=True)
    submitted_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


@extended_feedback_bp.route("/feedback", methods=["POST"])
@jwt_required()
def submit_extended_feedback():
    """Submit extended incident feedback."""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    incident_id = data.get("incident_id", "").strip()
    if not incident_id:
        return jsonify({"error": "VALIDATION_ERROR", "message": "incident_id is required", "details": {}}), 400

    # Verify incident exists
    incident = Incident.query.filter_by(incident_id=incident_id).first()
    if not incident:
        return jsonify({"error": "NOT_FOUND", "message": f"Incident '{incident_id}' not found", "details": {}}), 404

    try:
        fb = ExtendedFeedback(
            incident_id=incident_id,
            actual_priority=data.get("actual_priority"),
            actual_closure=bool(data.get("actual_closure", False)),
            actual_resolution_time=int(data["actual_resolution_time"]) if data.get("actual_resolution_time") is not None else None,
            officers_used=int(data["officers_used"]) if data.get("officers_used") is not None else None,
            barricades_used=int(data["barricades_used"]) if data.get("barricades_used") is not None else None,
            remarks=data.get("remarks"),
            submitted_by=str(user_id),
        )
        db.session.add(fb)
        db.session.commit()

        return jsonify({
            "success": True,
            "feedback_id": fb.feedback_id,
            "incident_id": incident_id,
            "message": "Feedback submitted successfully.",
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.exception("Failed to submit extended feedback")
        return jsonify({"error": "INTERNAL_ERROR", "message": str(e), "details": {}}), 500
