"""
models/audit_logs.py
Immutable audit trail — never deleted.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .base import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    __table_args__ = (
        db.Index("ix_audit_user_id", "user_id"),
        db.Index("ix_audit_resource", "resource_type", "resource_id"),
        db.Index("ix_audit_created_at", "created_at", postgresql_ops={"created_at": "DESC"}),
    )

    log_id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(100), nullable=True)
    resource_id = db.Column(db.String(100), nullable=True)
    old_value = db.Column(JSONB, nullable=True)
    new_value = db.Column(JSONB, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self):
        return {
            "log_id": str(self.log_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self):
        return f"<AuditLog {self.action} on {self.resource_type}/{self.resource_id}>"
