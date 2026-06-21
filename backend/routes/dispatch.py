"""
routes/dispatch.py
POST /dispatch — Human-in-the-loop dispatch.
This is the ONLY place a Dispatch record is created.
Resource allocation ONLY happens here.
"""

import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError

from models.base import db
from models.incidents import Incident
from models.dispatches import Dispatch
from models.audit_logs import AuditLog
from services.readiness_service import readiness_service
from middleware.rbac import require_role
from utils.validators import DispatchSchema
from utils.id_generator import generate_dispatch_id

logger = logging.getLogger(__name__)
dispatch_bp = Blueprint("dispatch", __name__)
_dispatch_schema = DispatchSchema()


@dispatch_bp.route("/dispatch", methods=["POST"])
@jwt_required()
@require_role("OPERATOR", "SUPERVISOR", "ADMIN")
def create_dispatch():
    """
    CRITICAL: This is the ONLY endpoint that creates dispatch records and
    allocates resources. No auto-dispatch exists anywhere in the system.
    Operator confirmation is MANDATORY.
    """
    try:
        data = _dispatch_schema.load(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": "VALIDATION_ERROR", "message": "Invalid request body", "details": e.messages}), 400

    claims = get_jwt()
    user_id = get_jwt_identity()
    user_role = claims.get("role", "")

    incident_id = data["incident_id"]
    station_id = data["station_id"]
    resources = data["resources_dispatched"]
    is_override = data.get("override", False)
    override_reason = data.get("override_reason")

    # Enforce: override=true requires override_reason
    if is_override and not override_reason:
        return jsonify({
            "error": "VALIDATION_ERROR",
            "message": "override_reason is required when override=true",
            "details": {"override_reason": ["Required field when override is true"]},
        }), 400

    # Validate incident exists and is in dispatchable state
    incident = Incident.query.filter_by(incident_id=incident_id).first()
    if not incident:
        return jsonify({"error": "NOT_FOUND", "message": f"Incident '{incident_id}' not found", "details": {}}), 404

    if incident.status not in ("REPORTED", "UNDER_ASSESSMENT", "RESOURCES_ASSIGNED", "IN_PROGRESS"):
        return jsonify({
            "error": "CONFLICT",
            "message": (
                f"Incident '{incident_id}' is in status '{incident.status}'. "
                f"Dispatch requires REPORTED, UNDER_ASSESSMENT, RESOURCES_ASSIGNED, or IN_PROGRESS."
            ),
            "details": {"current_status": incident.status},
        }), 409

    # Resolve vehicle count (support both field names)
    officers = resources.get("officers", 0)
    vehicles = resources.get("vehicles", resources.get("patrol_vehicles", 0))
    tow_trucks = resources.get("tow_trucks", 0)
    barricades = resources.get("barricades", 0)

    # Atomic resource allocation
    try:
        readiness_service.allocate_resources(
            station_id=station_id,
            resources={
                "officers": officers,
                "vehicles": vehicles,
                "tow_trucks": tow_trucks,
                "barricades": barricades,
            },
            incident_id=incident_id,
            operator_id=user_id,
        )
    except ValueError as e:
        msg = str(e)
        if "Insufficient" in msg:
            return jsonify({"error": "CONFLICT", "message": msg, "details": {"station_id": station_id}}), 409
        return jsonify({"error": "NOT_FOUND", "message": msg, "details": {}}), 404

    # Create dispatch record — THE ONLY PLACE THIS HAPPENS
    dispatch_id = generate_dispatch_id()
    dispatch = Dispatch(
        dispatch_id=dispatch_id,
        incident_id=incident_id,
        station_id=station_id,
        officers_dispatched=officers,
        vehicles_dispatched=vehicles,
        tow_trucks_dispatched=tow_trucks,
        barricades_dispatched=barricades,
        dispatched_by=user_id,
        dispatch_override=is_override,
        override_reason=override_reason if is_override else None,
        notes=data.get("notes"),
    )
    db.session.add(dispatch)

    # Audit log for override
    if is_override:
        db.session.add(AuditLog(
            user_id=user_id,
            action="DISPATCH_OVERRIDE",
            resource_type="dispatch",
            resource_id=dispatch_id,
            new_value={
                "incident_id": incident_id,
                "station_id": station_id,
                "override_reason": override_reason,
            },
            ip_address=request.remote_addr,
        ))

    # Mark incident as in progress once dispatch is confirmed.
    incident.status = "IN_PROGRESS"
    incident.updated_at = datetime.now(timezone.utc)
    db.session.add(incident)

    db.session.commit()
    logger.info(f"[Dispatch] {dispatch_id} created for {incident_id} → {station_id}")

    # Fetch updated station
    from models.stations import Station
    updated_station = Station.query.filter_by(station_id=station_id).first()

    return jsonify({
        "success": True,
        "dispatch_id": dispatch_id,
        "incident_id": incident_id,
        "station_id": station_id,
        "incident_status": "IN_PROGRESS",
        "resources_dispatched": {
            "officers": officers,
            "vehicles": vehicles,
            "tow_trucks": tow_trucks,
            "barricades": barricades,
        },
        "dispatch_override": is_override,
        "station_readiness": float(updated_station.readiness_score) if updated_station else None,
        "dispatched_at": dispatch.dispatched_at.isoformat(),
    }), 200
