from datetime import datetime
import random
from typing import Dict, Any
from services.summary_service import generate_incident_summary


def _generate_incident_id() -> str:
    date = datetime.utcnow().strftime("%Y%m%d")
    suffix = f"{random.randint(0, 99999):05d}"
    return f"INC-{date}-{suffix}"


def generate_incident_object(
    transcript: str, extracted: Dict, severity: Dict, location: Dict
) -> Dict[str, Any]:
    """Generate standardized incident object including resolved location."""
    incident_id = _generate_incident_id()
    timestamp = datetime.utcnow().isoformat() + "Z"

    location_name = location.get("location_name") or extracted.get("landmark") or extracted.get("road_name") or "unknown"

    incident = {
        "incident_id": incident_id,
        "event_type": extracted.get("event_type") or "unknown",
        "vehicle_type": extracted.get("vehicle_type") or "unknown",
        "location_name": location_name,
        "corridor": extracted.get("road_name") or None,
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "location_source": location.get("source"),
        "location_confidence": location.get("confidence"),
        "severity": severity.get("severity"),
        "confidence": severity.get("confidence"),
        "severity_score": severity.get("severity_score"),
        "severity_reasons": severity.get("severity_reasons"),
        "description": transcript,
        "timestamp": timestamp,
    }

    # Generate and attach a human-readable summary
    try:
        summary = generate_incident_summary(incident)
        incident["summary"] = summary
    except Exception:
        incident["summary"] = ""

    return incident
