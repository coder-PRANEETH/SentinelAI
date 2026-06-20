"""
models/incidents.py
Incident model — state machine enforced in IncidentService.
Format: INC-YYYY-000001
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from .base import db


class Incident(db.Model):
    __tablename__ = "incidents"

    __table_args__ = (
        db.Index("ix_incidents_status", "status"),
        db.Index("ix_incidents_corridor", "corridor"),
        db.Index("ix_incidents_reported_at", "reported_at", postgresql_ops={"reported_at": "DESC"}),
        db.Index("ix_incidents_reported_by", "reported_by"),
        db.Index("ix_incidents_geo", "latitude", "longitude"),
        db.CheckConstraint(
            "status IN ('REPORTED','UNDER_ASSESSMENT','RESOURCES_ASSIGNED',"
            "'IN_PROGRESS','RESOLVED','CLOSED','CANCELLED')",
            name="ck_incident_status",
        ),
    )

    incident_id = db.Column(db.String(20), primary_key=True)  # INC-YYYY-NNNNNN
    incident_type = db.Column(db.String(100), nullable=True)
    event_cause = db.Column(db.String(200), nullable=True)
    vehicle_type = db.Column(db.String(100), nullable=True)
    location = db.Column(db.Text, nullable=True)
    corridor = db.Column(db.String(200), nullable=True)
    latitude = db.Column(db.Numeric(10, 7), nullable=True)
    longitude = db.Column(db.Numeric(10, 7), nullable=True)
    priority_indicators = db.Column(ARRAY(db.Text), nullable=True)
    status = db.Column(db.String(20), default="REPORTED", nullable=False)
    reported_by = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    reported_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    raw_transcript = db.Column(db.Text, nullable=True)
    is_cancelled = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    prediction = db.relationship("Prediction", backref="incident", uselist=False)
    dispatches = db.relationship("Dispatch", backref="incident", lazy="dynamic")
    feedback = db.relationship("IncidentFeedback", backref="incident", uselist=False)

    def to_dict(self):
        return {
            "incident_id": self.incident_id,
            "incident_type": self.incident_type,
            "event_cause": self.event_cause,
            "vehicle_type": self.vehicle_type,
            "location": self.location,
            "corridor": self.corridor,
            "latitude": float(self.latitude) if self.latitude else None,
            "longitude": float(self.longitude) if self.longitude else None,
            "priority_indicators": self.priority_indicators,
            "status": self.status,
            "reported_by": str(self.reported_by) if self.reported_by else None,
            "reported_at": self.reported_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "raw_transcript": self.raw_transcript,
            "is_cancelled": self.is_cancelled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self):
        return f"<Incident {self.incident_id} [{self.status}]>"
