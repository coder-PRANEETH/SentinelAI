"""
routes/stations.py
GET /stations, GET /stations/<id>,
POST /stations/<id>/allocate, POST /stations/<id>/release
"""

import json
import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError

from models.base import db
from models.stations import Station
from services.readiness_service import readiness_service
from middleware.rbac import require_role
from utils.validators import AllocateSchema, ReleaseSchema
from config import STATION_LIST_CACHE_TTL

logger = logging.getLogger(__name__)
stations_bp = Blueprint("stations", __name__)
_allocate_schema = AllocateSchema()
_release_schema = ReleaseSchema()


@stations_bp.route("/stations", methods=["GET"])
@jwt_required()
def list_stations():
    """Return all stations sorted by readiness_score DESC. Redis-cached (30s TTL)."""
    min_readiness = request.args.get("min_readiness", 0, type=float)
    sort = request.args.get("sort", "readiness_desc")

    cache_key = f"stations:list:{min_readiness}:{sort}"
    try:
        from extensions import redis_client
        cached = redis_client.get(cache_key)
        if cached:
            return jsonify(json.loads(cached)), 200
    except Exception:
        pass

    query = Station.query
    if min_readiness > 0:
        query = query.filter(Station.readiness_score >= min_readiness)
    query = query.order_by(Station.readiness_score.desc())
    stations = query.all()
    result = [s.to_summary_dict() for s in stations]

    # Cache result
    try:
        from extensions import redis_client
        redis_client.setex(cache_key, STATION_LIST_CACHE_TTL, json.dumps(result))
    except Exception:
        pass

    return jsonify(result), 200


@stations_bp.route("/stations/<station_id>", methods=["GET"])
@jwt_required()
def get_station(station_id: str):
    """Return full station details including all resource counts."""
    station = Station.query.filter_by(station_id=station_id).first()
    if not station:
        return jsonify({"error": "NOT_FOUND", "message": f"Station '{station_id}' not found", "details": {}}), 404
    return jsonify(station.to_dict()), 200


@stations_bp.route("/stations/<station_id>", methods=["PUT"])
@jwt_required()
@require_role("SUPERVISOR", "ADMIN")
def update_station(station_id: str):
    """Update station total resources."""
    station = Station.query.filter_by(station_id=station_id).first()
    if not station:
        return jsonify({"error": "NOT_FOUND", "message": f"Station '{station_id}' not found", "details": {}}), 404

    data = request.get_json(silent=True) or {}
    
    if "total_officers" in data:
        diff = int(data["total_officers"]) - station.total_officers
        station.total_officers = int(data["total_officers"])
        station.available_officers = max(0, station.available_officers + diff)
        
    if "total_vehicles" in data:
        diff = int(data["total_vehicles"]) - station.total_vehicles
        station.total_vehicles = int(data["total_vehicles"])
        station.available_vehicles = max(0, station.available_vehicles + diff)
        
    if "total_tow_trucks" in data:
        diff = int(data["total_tow_trucks"]) - station.total_tow_trucks
        station.total_tow_trucks = int(data["total_tow_trucks"])
        station.available_tow_trucks = max(0, station.available_tow_trucks + diff)
        
    if "total_barricades" in data:
        diff = int(data["total_barricades"]) - station.total_barricades
        station.total_barricades = int(data["total_barricades"])
        station.available_barricades = max(0, station.available_barricades + diff)

    # Recalculate readiness
    try:
        from services.readiness_service import readiness_service
        station.readiness_score = readiness_service.calculate_readiness_score(station.to_dict())
    except Exception:
        pass

    db.session.commit()
    return jsonify(station.to_dict()), 200


@stations_bp.route("/stations/<station_id>/allocate", methods=["POST"])
@jwt_required()
@require_role("OPERATOR", "SUPERVISOR", "ADMIN")
def allocate(station_id: str):
    """Deduct resources from station for an incident dispatch."""
    try:
        data = _allocate_schema.load(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": "VALIDATION_ERROR", "message": "Invalid request body", "details": e.messages}), 400

    user_id = get_jwt_identity()

    try:
        updated_station = readiness_service.allocate_resources(
            station_id=station_id,
            resources=data["resources"],
            incident_id=data["incident_id"],
            operator_id=user_id,
        )
    except ValueError as e:
        msg = str(e)
        if "Insufficient" in msg:
            return jsonify({
                "error": "CONFLICT",
                "message": msg,
                "details": {"station_id": station_id},
            }), 409
        return jsonify({"error": "NOT_FOUND", "message": msg, "details": {}}), 404

    # Generate dispatch_id for caller reference
    from utils.id_generator import generate_dispatch_id
    dispatch_id = generate_dispatch_id()

    return jsonify({
        "success": True,
        "dispatch_id": dispatch_id,
        "station": updated_station,
        "resources_allocated": data["resources"],
        "new_readiness_score": float(updated_station["readiness_score"]),
    }), 200


@stations_bp.route("/stations/<station_id>/release", methods=["POST"])
@jwt_required()
@require_role("OPERATOR", "SUPERVISOR", "ADMIN")
def release(station_id: str):
    """Return resources to station after incident resolution."""
    try:
        data = _release_schema.load(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": "VALIDATION_ERROR", "message": "Invalid request body", "details": e.messages}), 400

    user_id = get_jwt_identity()

    try:
        updated_station = readiness_service.release_resources(
            station_id=station_id,
            dispatch_id=data["dispatch_id"],
            operator_id=user_id,
        )
    except ValueError as e:
        return jsonify({"error": "NOT_FOUND", "message": str(e), "details": {}}), 404

    return jsonify({
        "success": True,
        "station": updated_station,
        "new_readiness_score": float(updated_station["readiness_score"]),
    }), 200
