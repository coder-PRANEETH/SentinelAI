"""
models/predictions.py
ML prediction record — one per incident.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .base import db


class Prediction(db.Model):
    __tablename__ = "predictions"

    prediction_id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id = db.Column(
        db.String(20),
        db.ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Priority prediction
    predicted_priority = db.Column(db.String(5), nullable=True)        # P1…P4
    priority_confidence = db.Column(db.Numeric(5, 4), nullable=True)   # 0.0–1.0
    priority_reasons = db.Column(JSONB, nullable=True)

    # Resolution time prediction (minutes)
    predicted_resolution_minutes = db.Column(db.Integer, nullable=True)
    resolution_range_low = db.Column(db.Integer, nullable=True)
    resolution_range_high = db.Column(db.Integer, nullable=True)

    # Road closure prediction
    road_closure_probability = db.Column(db.Numeric(5, 4), nullable=True)  # 0.0–1.0
    road_closure_recommendation = db.Column(db.String(10), nullable=True)  # Yes/No/Monitor
    closure_reasons = db.Column(JSONB, nullable=True)

    # Resource recommendation (snapshot)
    recommended_resources = db.Column(JSONB, nullable=True)

    # Historical context (snapshot)
    historical_context = db.Column(JSONB, nullable=True)

    model_version = db.Column(db.String(20), default="1.0.0", nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self):
        return {
            "prediction_id": str(self.prediction_id),
            "incident_id": self.incident_id,
            "predicted_priority": self.predicted_priority,
            "priority_confidence": float(self.priority_confidence) if self.priority_confidence else None,
            "priority_reasons": self.priority_reasons,
            "predicted_resolution_minutes": self.predicted_resolution_minutes,
            "resolution_range_low": self.resolution_range_low,
            "resolution_range_high": self.resolution_range_high,
            "road_closure_probability": float(self.road_closure_probability) if self.road_closure_probability else None,
            "road_closure_recommendation": self.road_closure_recommendation,
            "closure_reasons": self.closure_reasons,
            "recommended_resources": self.recommended_resources,
            "historical_context": self.historical_context,
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat(),
        }
