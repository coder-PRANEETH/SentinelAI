"""
models/resource_inventory_log.py
Log every resource change at a station (allocate / release / manual update).
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from .base import db


class ResourceInventoryLog(db.Model):
    __tablename__ = "resource_inventory_log"

    log_id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    station_id = db.Column(
        db.String(10),
        db.ForeignKey("stations.station_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type = db.Column(db.String(50), nullable=False)   # officers/vehicles/…
    change_type = db.Column(db.String(20), nullable=False)     # allocate/release/manual
    quantity_change = db.Column(db.Integer, nullable=False)    # positive=added, negative=deducted
    reason = db.Column(db.Text, nullable=True)
    changed_by = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self):
        return {
            "log_id": str(self.log_id),
            "station_id": self.station_id,
            "resource_type": self.resource_type,
            "change_type": self.change_type,
            "quantity_change": self.quantity_change,
            "reason": self.reason,
            "changed_by": str(self.changed_by) if self.changed_by else None,
            "created_at": self.created_at.isoformat(),
        }
