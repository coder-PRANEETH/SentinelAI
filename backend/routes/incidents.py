import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from models.base import db
from models.incidents import Incident
from models.predictions import Prediction
from utils.id_generator import generate_incident_id

logger = logging.getLogger(__name__)
incidents_bp = Blueprint("incidents", __name__)


def _coerce_probability(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value / 100.0 if value > 1 else value


def _normalize_priority(value):
    if value is None:
        return None
    value = str(value).strip().upper()
    mapping = {
        "HIGH": "P1",
        "MEDIUM": "P2",
        "LOW": "P4",
        "P1": "P1",
        "P2": "P2",
        "P3": "P3",
        "P4": "P4",
    }
    return mapping.get(value, value[:5] if value else None)

@incidents_bp.route("/incidents/active", methods=["GET"])
def get_active_incidents():
    try:
        active_incidents = Incident.query.filter(
            Incident.status.in_(["REPORTED", "IN_PROGRESS"])
        ).order_by(Incident.created_at.desc()).all()
        
        results = []
        for inc in active_incidents:
            data = inc.to_dict()
            if inc.prediction:
                data["predicted_priority"] = inc.prediction.predicted_priority
            else:
                data["predicted_priority"] = "P4"
            results.append(data)
            
        return jsonify(results), 200
    except Exception as e:
        logger.exception("Failed to fetch active incidents")
        return jsonify({"error": "INTERNAL_ERROR", "message": str(e)}), 500


@incidents_bp.route("/incidents", methods=["GET"])
def list_incidents():
    """List incidents with optional filtering."""
    try:
        status_filter = request.args.get("status")
        limit = int(request.args.get("limit", 50))

        query = Incident.query.order_by(Incident.created_at.desc())
        if status_filter:
            query = query.filter(Incident.status == status_filter.upper())
        incidents = query.limit(limit).all()

        results = []
        for inc in incidents:
            data = inc.to_dict()
            data["predicted_priority"] = (
                inc.prediction.predicted_priority if inc.prediction else "P4"
            )
            results.append(data)

        return jsonify(results), 200
    except Exception as e:
        logger.exception("Failed to list incidents")
        return jsonify({"error": "INTERNAL_ERROR", "message": str(e)}), 500


@incidents_bp.route("/incidents/<string:incident_id>", methods=["GET"])
def get_incident_by_id(incident_id: str):
    """Fetch full incident details by ID including prediction."""
    try:
        inc = Incident.query.filter_by(incident_id=incident_id).first()
        if not inc:
            return jsonify({"error": "NOT_FOUND", "message": f"Incident '{incident_id}' not found", "details": {}}), 404

        data = inc.to_dict()
        if inc.prediction:
            p = inc.prediction
            data["prediction"] = {
                "predicted_priority": p.predicted_priority,
                "priority_confidence": float(p.priority_confidence) if p.priority_confidence else None,
                "predicted_resolution_minutes": p.predicted_resolution_minutes,
                "road_closure_probability": float(p.road_closure_probability) if p.road_closure_probability else None,
                "road_closure_recommendation": p.road_closure_recommendation,
                "priority_reasons": p.priority_reasons or [],
                "closure_reasons": p.closure_reasons or [],
            }
            data["predicted_priority"] = p.predicted_priority
        else:
            data["prediction"] = None
            data["predicted_priority"] = "P4"

        return jsonify(data), 200
    except Exception as e:
        logger.exception("Failed to fetch incident detail")
        return jsonify({"error": "INTERNAL_ERROR", "message": str(e)}), 500


@incidents_bp.route("/incidents", methods=["POST"])
def create_incident():
    """Persist an incident and its prediction in the backend database."""
    data = request.get_json(silent=True) or {}
    prediction = data.get("prediction") or data.get("predictions") or {}

    try:
        incident_id = data.get("incident_id") or generate_incident_id()
        now = datetime.now(timezone.utc)
        corridor = data.get("corridor") or prediction.get("corridor") or "unknown"
        location = data.get("location") or corridor

        incident = Incident(
            incident_id=incident_id,
            incident_type=data.get("incident_type") or data.get("event_type_grouped"),
            event_cause=data.get("event_cause") or prediction.get("event_cause"),
            vehicle_type=data.get("vehicle_type") or data.get("veh_type_grouped"),
            location=location,
            corridor=corridor,
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            raw_transcript=data.get("raw_transcript"),
            status="REPORTED",
            is_cancelled=False,
            reported_at=now,
            created_at=now,
            updated_at=now,
        )
        db.session.add(incident)
        db.session.flush()

        pred = Prediction(
            incident_id=incident_id,
            predicted_priority=_normalize_priority(
                prediction.get("predicted_priority") or prediction.get("priority")
            ),
            priority_confidence=_coerce_probability(prediction.get("priority_confidence")),
            priority_reasons=prediction.get("priority_reasons"),
            predicted_resolution_minutes=(
                int(round(prediction.get("predicted_resolution_minutes")))
                if prediction.get("predicted_resolution_minutes") is not None
                else int(round(prediction.get("expected_resolution_minutes")))
                if prediction.get("expected_resolution_minutes") is not None
                else None
            ),
            resolution_range_low=(prediction.get("resolution_range") or {}).get("low"),
            resolution_range_high=(prediction.get("resolution_range") or {}).get("high"),
            road_closure_probability=_coerce_probability(prediction.get("road_closure_probability")),
            road_closure_recommendation=prediction.get("road_closure_recommendation")
            or ("Yes" if prediction.get("road_closure_required") else "No"),
            closure_reasons=prediction.get("closure_reasons"),
            recommended_resources=data.get("recommended_resources"),
            historical_context=data.get("historical_context"),
            model_version=prediction.get("model_version", "final_endpoints-1.0"),
        )
        db.session.add(pred)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "incident_id": incident.incident_id,
                "prediction_id": str(pred.prediction_id),
            }
        ), 201
    except IntegrityError as e:
        db.session.rollback()
        logger.exception("Failed to save incident/prediction")
        return jsonify({"error": "INTEGRITY_ERROR", "message": str(e), "details": {}}), 409
    except Exception as e:
        db.session.rollback()
        logger.exception("Failed to save incident/prediction")
        return jsonify({"error": "INTERNAL_ERROR", "message": str(e), "details": {}}), 500
