import logging
from flask import Blueprint, jsonify, request
from models.incidents import Incident
from models.predictions import Prediction

logger = logging.getLogger(__name__)
incidents_bp = Blueprint("incidents", __name__)

@incidents_bp.route("/incidents/active", methods=["GET"])
def get_active_incidents():
    try:
        active_incidents = Incident.query.filter(
            Incident.status.notin_(["CLOSED", "CANCELLED", "RESOLVED"])
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
