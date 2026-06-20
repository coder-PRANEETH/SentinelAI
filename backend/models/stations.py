"""
models/stations.py
Station model — 53 Bengaluru Traffic Police stations.
Resource counts, readiness score, and active incidents are updated
atomically by ReadinessService on every allocate/release.
"""

from datetime import datetime, timezone
from .base import db


class Station(db.Model):
    __tablename__ = "stations"

    __table_args__ = (
        db.Index("ix_stations_readiness", "readiness_score"),
        db.Index("ix_stations_geo", "latitude", "longitude"),
    )

    station_id = db.Column(db.String(10), primary_key=True)  # BTP-001 … BTP-053
    station_name = db.Column(db.String(200), unique=True, nullable=False)
    latitude = db.Column(db.Numeric(10, 7), nullable=True)
    longitude = db.Column(db.Numeric(10, 7), nullable=True)

    # Resource totals (full capacity)
    total_officers = db.Column(db.Integer, default=15, nullable=False)
    total_vehicles = db.Column(db.Integer, default=4, nullable=False)
    total_tow_trucks = db.Column(db.Integer, default=2, nullable=False)
    total_barricades = db.Column(db.Integer, default=20, nullable=False)

    # Resource availabilities — always >= 0
    available_officers = db.Column(
        db.Integer, default=15, nullable=False,
        info={"check": "available_officers >= 0"}
    )
    available_vehicles = db.Column(
        db.Integer, default=4, nullable=False,
        info={"check": "available_vehicles >= 0"}
    )
    available_tow_trucks = db.Column(
        db.Integer, default=2, nullable=False,
        info={"check": "available_tow_trucks >= 0"}
    )
    available_barricades = db.Column(
        db.Integer, default=20, nullable=False,
        info={"check": "available_barricades >= 0"}
    )

    active_incidents = db.Column(db.Integer, default=0, nullable=False)
    readiness_score = db.Column(db.Numeric(5, 2), default=0, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    dispatches = db.relationship("Dispatch", backref="station", lazy="dynamic",
                                 foreign_keys="Dispatch.station_id")
    users = db.relationship("User", backref="station", lazy="dynamic")

    def to_summary_dict(self):
        """Lightweight dict for list endpoints (cached in Redis)."""
        return {
            "station_id": self.station_id,
            "station_name": self.station_name,
            "latitude": float(self.latitude) if self.latitude else None,
            "longitude": float(self.longitude) if self.longitude else None,
            "readiness_score": float(self.readiness_score),
            "available_officers": self.available_officers,
            "available_vehicles": self.available_vehicles,
            "available_tow_trucks": self.available_tow_trucks,
            "available_barricades": self.available_barricades,
            "active_incidents": self.active_incidents,
        }

    def to_dict(self):
        """Full detail dict for single station endpoints."""
        return {
            **self.to_summary_dict(),
            "total_officers": self.total_officers,
            "total_vehicles": self.total_vehicles,
            "total_tow_trucks": self.total_tow_trucks,
            "total_barricades": self.total_barricades,
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self):
        return f"<Station {self.station_id} {self.station_name}>"
