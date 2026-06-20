"""
models/dispatches.py
Dispatch record — created ONLY by POST /dispatch (human-in-the-loop).
Format: DIS-YYYY-000001
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from .base import db


class Dispatch(db.Model):
    __tablename__ = "dispatches"

    __table_args__ = (
        db.Index("ix_dispatches_incident_id", "incident_id"),
        db.Index("ix_dispatches_station_id", "station_id"),
        db.Index("ix_dispatches_dispatched_at", "dispatched_at", postgresql_ops={"dispatched_at": "DESC"}),
    )

    dispatch_id = db.Column(db.String(20), primary_key=True)  # DIS-YYYY-NNNNNN
    incident_id = db.Column(
        db.String(20),
        db.ForeignKey("incidents.incident_id", ondelete="RESTRICT"),
        nullable=False,
    )
    station_id = db.Column(
        db.String(10),
        db.ForeignKey("stations.station_id", ondelete="RESTRICT"),
        nullable=False,
    )
    recommended_station_id = db.Column(
        db.String(10),
        db.ForeignKey("stations.station_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Resources dispatched
    officers_dispatched = db.Column(db.Integer, default=0, nullable=False)
    vehicles_dispatched = db.Column(db.Integer, default=0, nullable=False)
    tow_trucks_dispatched = db.Column(db.Integer, default=0, nullable=False)
    barricades_dispatched = db.Column(db.Integer, default=0, nullable=False)

    dispatched_by = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    dispatch_override = db.Column(db.Boolean, default=False, nullable=False)
    override_reason = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    dispatched_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    released_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "dispatch_id": self.dispatch_id,
            "incident_id": self.incident_id,
            "station_id": self.station_id,
            "recommended_station_id": self.recommended_station_id,
            "officers_dispatched": self.officers_dispatched,
            "vehicles_dispatched": self.vehicles_dispatched,
            "tow_trucks_dispatched": self.tow_trucks_dispatched,
            "barricades_dispatched": self.barricades_dispatched,
            "dispatched_by": str(self.dispatched_by) if self.dispatched_by else None,
            "dispatch_override": self.dispatch_override,
            "override_reason": self.override_reason,
            "notes": self.notes,
            "dispatched_at": self.dispatched_at.isoformat(),
            "released_at": self.released_at.isoformat() if self.released_at else None,
        }

    def __repr__(self):
        return f"<Dispatch {self.dispatch_id} station={self.station_id}>"
