from typing import Dict, Any


def _pretty_vehicle(vehicle_type: str) -> str:
    mapping = {
        "heavy_vehicle": "Heavy vehicle",
        "bus": "Bus",
        "car": "Car",
        "two_wheeler": "Two-wheeler",
        "unknown": "Vehicle",
    }
    return mapping.get(vehicle_type, vehicle_type.title() if vehicle_type else "Vehicle")


def _pretty_event(event_type: str) -> str:
    mapping = {
        "vehicle_breakdown": "breakdown",
        "congestion": "congestion",
        "accident": "accident",
        "road_block": "road block",
        "unknown": "incident",
    }
    return mapping.get(event_type, event_type.replace("_", " ") if event_type else "incident")


def generate_incident_summary(incident: Dict[str, Any]) -> str:
    """Generate a simple rule-based incident summary string from the incident dict."""
    vehicle = _pretty_vehicle(incident.get("vehicle_type") or "unknown")
    event = _pretty_event(incident.get("event_type") or "unknown")

    location_name = incident.get("location_name") or "Unknown Location"
    corridor = incident.get("corridor") or "Unknown Corridor"
    severity = incident.get("severity") or "unknown"

    reasons_list = incident.get("severity_reasons") or []
    if reasons_list:
        reasons = " ".join([r.capitalize().rstrip('.') + '.' for r in reasons_list])
    else:
        reasons = "No specific reasons provided."

    lat = incident.get("latitude")
    lon = incident.get("longitude")
    coords = f"{lat}, {lon}" if lat is not None and lon is not None else "Unknown"

    # Recommended action
    recommended = "Log the incident and monitor for further updates."
    if severity == "high":
        recommended = "Dispatch nearest traffic response unit immediately and alert control room supervisor."
    elif severity == "medium":
        recommended = "Assign traffic officer for verification and monitor congestion buildup."

    summary = (
        "Incident Summary\n\n"
        f"{vehicle} {event} reported near {location_name} on {corridor}.\n\n"
        f"Severity: {severity}\n\n"
        "Reason:\n"
        f"{reasons}\n\n"
        "Coordinates:\n"
        f"{coords}\n\n"
        "Recommended Action:\n"
        f"{recommended}"
    )

    return summary
