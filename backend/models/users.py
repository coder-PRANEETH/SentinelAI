"""
models/users.py
User model with Argon2id password hashing.
Roles: OPERATOR, STATION_OFFICER, SUPERVISOR, ADMIN
"""

import uuid
from datetime import datetime, timezone
from .base import db
from sqlalchemy.dialects.postgresql import UUID


class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(20),
        db.CheckConstraint(
            "role IN ('OPERATOR','STATION_OFFICER','SUPERVISOR','ADMIN')",
            name="ck_user_role",
        ),
        nullable=False,
    )
    station_id = db.Column(
        db.String(10),
        db.ForeignKey("stations.station_id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)
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
    incidents = db.relationship("Incident", backref="reporter", lazy="dynamic",
                                foreign_keys="Incident.reported_by")
    dispatches = db.relationship("Dispatch", backref="dispatcher", lazy="dynamic",
                                 foreign_keys="Dispatch.dispatched_by")
    audit_logs = db.relationship("AuditLog", backref="actor", lazy="dynamic")

    def to_dict(self):
        return {
            "user_id": str(self.user_id),
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "station_id": self.station_id,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self):
        return f"<User {self.username} [{self.role}]>"
