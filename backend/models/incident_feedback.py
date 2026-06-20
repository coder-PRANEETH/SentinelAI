"""
models/incident_feedback.py
Ground-truth feedback after incident closure.
Computed fields: priority_accurate, resolution_error_minutes.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from .base import db


class IncidentFeedback(db.Model):
    __tablename__ = "incident_feedback"

    feedback_id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id = db.Column(
        db.String(20),
        db.ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    actual_priority = db.Column(db.String(5), nullable=True)
    actual_resolution_time_minutes = db.Column(db.Integer, nullable=True)
    road_closure_occurred = db.Column(db.Boolean, nullable=True)
    outcome_description = db.Column(db.Text, nullable=True)

    submitted_by = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Computed on write by the feedback service
    priority_accurate = db.Column(db.Boolean, nullable=True)
    resolution_error_minutes = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            "feedback_id": str(self.feedback_id),
            "incident_id": self.incident_id,
            "actual_priority": self.actual_priority,
            "actual_resolution_time_minutes": self.actual_resolution_time_minutes,
            "road_closure_occurred": self.road_closure_occurred,
            "outcome_description": self.outcome_description,
            "submitted_by": str(self.submitted_by) if self.submitted_by else None,
            "submitted_at": self.submitted_at.isoformat(),
            "priority_accurate": self.priority_accurate,
            "resolution_error_minutes": self.resolution_error_minutes,
        }
