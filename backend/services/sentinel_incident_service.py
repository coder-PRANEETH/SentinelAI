"""
services/sentinel_incident_service.py
Incident state machine and lifecycle management.

Named sentinel_incident_service.py to avoid conflict with the existing
backend/services/incident_service.py (FastAPI-era service).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from models.base import db
from models.incidents import Incident
from models.audit_logs import AuditLog
from utils.id_generator import generate_incident_id

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# STATE MACHINE
# ─────────────────────────────────────────────────────────────────────────────

VALID_TRANSITIONS = {
    None:                   ["REPORTED"],
    "REPORTED":             ["UNDER_ASSESSMENT", "CANCELLED"],
    "UNDER_ASSESSMENT":     ["RESOURCES_ASSIGNED", "CANCELLED"],
    "RESOURCES_ASSIGNED":   ["IN_PROGRESS", "CANCELLED"],
    "IN_PROGRESS":          ["RESOLVED", "CANCELLED"],
    "RESOLVED":             ["CLOSED", "CANCELLED"],
    "CLOSED":               [],
    "CANCELLED":            [],
}

# Roles allowed to cancel (ANY → CANCELLED)
CANCEL_ROLES = {"SUPERVISOR", "ADMIN"}


class IncidentStateMachineError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class SentinelIncidentService:

    # ─────────────────────────────────────────────────────────────────────────
    # CREATE
    # ─────────────────────────────────────────────────────────────────────────

    def create_incident(self, data: dict, reporter_id=None) -> Incident:
        """
        Create a new REPORTED incident.
        Generates INC-YYYY-NNNNNN ID.
        """
        incident_id = generate_incident_id()
        incident = Incident(
            incident_id=incident_id,
            incident_type=data.get("incident_type"),
            event_cause=data.get("event_cause"),
            vehicle_type=data.get("vehicle_type"),
            location=data.get("location"),
            corridor=data.get("corridor"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            priority_indicators=data.get("priority_indicators"),
            status="REPORTED",
            reported_by=reporter_id,
            raw_transcript=data.get("raw_transcript"),
        )
        db.session.add(incident)

        self._write_audit(
            user_id=reporter_id,
            action="CREATE_INCIDENT",
            resource_type="incident",
            resource_id=incident_id,
            old_value=None,
            new_value={"status": "REPORTED"},
        )

        db.session.commit()
        logger.info(f"[IncidentService] Created {incident_id}")
        return incident

    # ─────────────────────────────────────────────────────────────────────────
    # TRANSITION
    # ─────────────────────────────────────────────────────────────────────────

    def transition(
        self,
        incident_id: str,
        new_status: str,
        operator_id=None,
        operator_role: str = None,
        reason: str = None,
    ) -> Incident:
        """
        Enforce state machine. Raises IncidentStateMachineError on invalid transition.
        Writes to audit_logs.
        """
        incident = Incident.query.filter_by(incident_id=incident_id).first()
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        current_status = incident.status
        allowed = VALID_TRANSITIONS.get(current_status, [])

        if new_status == "CANCELLED" and operator_role not in CANCEL_ROLES:
            raise IncidentStateMachineError(
                f"Only SUPERVISOR or ADMIN can cancel incidents (your role: {operator_role})"
            )

        if new_status not in allowed:
            raise IncidentStateMachineError(
                f"Transition '{current_status}' → '{new_status}' is not permitted. "
                f"Allowed: {allowed}"
            )

        old_status = incident.status
        incident.status = new_status
        incident.updated_at = datetime.now(timezone.utc)

        if new_status == "CANCELLED":
            incident.is_cancelled = True
        if new_status == "RESOLVED":
            incident.resolved_at = datetime.now(timezone.utc)
        if new_status == "CLOSED":
            incident.closed_at = datetime.now(timezone.utc)

        self._write_audit(
            user_id=operator_id,
            action="TRANSITION_INCIDENT",
            resource_type="incident",
            resource_id=incident_id,
            old_value={"status": old_status},
            new_value={"status": new_status, "reason": reason},
        )

        db.session.commit()
        logger.info(f"[IncidentService] {incident_id}: {old_status} → {new_status}")
        return incident

    # ─────────────────────────────────────────────────────────────────────────
    # AUTO-ADVANCE after AI prediction
    # ─────────────────────────────────────────────────────────────────────────

    def advance_to_under_assessment(self, incident_id: str) -> Incident:
        """Automatically advance REPORTED → UNDER_ASSESSMENT after AI runs."""
        return self.transition(
            incident_id,
            "UNDER_ASSESSMENT",
            operator_id=None,
            reason="AI prediction completed",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _write_audit(self, user_id, action, resource_type, resource_id, old_value, new_value):
        db.session.add(AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
        ))


# Module-level singleton
sentinel_incident_service = SentinelIncidentService()
