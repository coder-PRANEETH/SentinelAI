import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from services.extraction_service import extract_incident_fields
from services.geocoding_service import geocode_location
from services.incident_service import generate_incident_object
from services.llm_extraction_service_fallback import extract_incident_fields_fallback
from services.location_service import resolve_location
from services.module_dispatch_service import dispatch_incident_to_modules
from services.severity_service import assess_severity

load_dotenv()

logger = logging.getLogger(__name__)

LLM_FALLBACK_API_KEY = os.getenv("LLM_FALLBACK_API_KEY")
USE_LLM_EXTRACTION_FALLBACK = os.getenv("USE_LLM_EXTRACTION_FALLBACK", "false").lower() == "true"
MISSING_EVENT_TYPE_QUESTION = (
    "What happened exactly? Was it an accident, breakdown, congestion, road block, fire, or medical emergency?"
)
MISSING_LOCATION_QUESTION = (
    "Where exactly did this happen? Please mention road name, junction, landmark, or area."
)
MISSING_TRAFFIC_QUESTION = "Is traffic blocked, slow moving, or normal?"
MISSING_VEHICLE_QUESTION = (
    "What vehicle is involved, like bike, car, bus, truck, or lorry? If no vehicle is involved, say no vehicle."
)

LOCATION_NORMALIZATIONS = [
    ("tiruchiruode", "trichy road"),
    ("tiruchi road", "trichy road"),
    ("tiruchy road", "trichy road"),
    ("trichiro", "trichy road"),
    ("trichy road", "trichy road"),
    ("namakkal junction", "namakkal junction"),
    ("namakal junction", "namakkal junction"),
    ("namakal", "namakkal"),
    ("gandhipuram signal", "gandhipuram signal"),
    ("gandipuram", "gandhipuram"),
    ("hopes college", "hopes college signal"),
    ("avinashi", "avinashi road"),
    ("coimbatore", "coimbatore"),
]

ROAD_LOCATIONS = {
    "trichy road": "Trichy Road",
    "avinashi road": "Avinashi Road",
}

LANDMARK_LOCATIONS = {
    "namakkal junction": "Namakkal Junction",
    "gandhipuram signal": "Gandhipuram Signal",
    "hopes college signal": "Hopes College Signal",
}

AREA_LOCATIONS = {
    "namakkal": "Namakkal",
    "gandhipuram": "Gandhipuram",
    "coimbatore": "Coimbatore",
}


def normalize_interactive_transcript(text: str) -> str:
    normalized = (text or "").lower()
    for mistake, correction in LOCATION_NORMALIZATIONS:
        normalized = normalized.replace(mistake, correction)
    return normalized


def process_interactive_voice_turn(
    transcript: str,
    current_incident: Optional[dict],
) -> dict:
    """Merge one voice-call transcript turn and return the next action."""
    clean_transcript = (transcript or "").strip()
    normalized_transcript = normalize_interactive_transcript(clean_transcript)
    existing = current_incident.copy() if isinstance(current_incident, dict) else {}
    new_fields = _process_incident_pipeline(normalized_transcript) if normalized_transcript else {}
    _apply_interactive_overrides(normalized_transcript, new_fields)

    merged = _merge_incident_fields(existing, new_fields, clean_transcript, normalized_transcript)
    next_question = _next_missing_field_question(merged)

    if next_question:
        if _can_complete_after_repeated_question(merged, next_question):
            return _complete_incident_response(merged, clean_transcript)

        _record_asked_question(merged, next_question)
        return {
            "complete": False,
            "next_question": next_question,
            "current_incident": merged,
        }

    return _complete_incident_response(merged, clean_transcript)


def _complete_incident_response(merged: dict, transcript: str) -> dict:
    combined_transcript = merged.get("combined_transcript") or transcript
    location = _resolve_location_with_geocoding(merged)
    severity = assess_severity(combined_transcript, merged)
    incident = generate_incident_object(combined_transcript, merged, severity, location)

    module_dispatch = None
    try:
        module_dispatch = dispatch_incident_to_modules(incident)
    except Exception as e:
        logger.warning(f"Module dispatch failed for interactive voice incident: {e}")

    response = {
        "complete": True,
        "next_question": None,
        "current_incident": merged,
        "incident": incident,
    }

    if module_dispatch is not None:
        response["module_dispatch"] = module_dispatch

    return response


def _process_incident_pipeline(transcript: str) -> dict:
    extraction_method = "rule_based_fallback"

    if USE_LLM_EXTRACTION_FALLBACK and LLM_FALLBACK_API_KEY:
        try:
            extracted = extract_incident_fields_fallback(transcript)
            if extracted:
                extracted["extraction_method"] = "llm"
                return extracted
        except Exception as e:
            logger.warning(f"Fallback LLM extraction failed for interactive turn: {e}")

    extracted = extract_incident_fields(transcript)
    extracted["extraction_method"] = extraction_method
    return extracted


def _resolve_location_with_geocoding(extracted: dict) -> dict:
    location = resolve_location(extracted)
    if location.get("latitude") and location.get("longitude"):
        return location

    query_to_geocode = (
        extracted.get("location_query")
        or extracted.get("road_name")
        or extracted.get("landmark")
        or extracted.get("location_name")
    )

    if query_to_geocode:
        try:
            geocoded = geocode_location(
                query_to_geocode,
                city=extracted.get("city"),
                state=extracted.get("state"),
                country=extracted.get("country"),
            )
            if geocoded.get("latitude") and geocoded.get("longitude"):
                return geocoded
            if geocoded.get("location_name") and geocoded.get("location_name") != "Unknown Location":
                return geocoded
        except Exception as e:
            logger.warning(f"Interactive voice geocoding failed: {e}")

    return location


def _merge_incident_fields(
    existing: dict,
    new_fields: dict,
    transcript: str,
    normalized_transcript: str,
) -> Dict[str, Any]:
    merged = existing.copy()

    previous_transcript = merged.get("combined_transcript") or merged.get("transcript") or ""
    if transcript:
        merged["combined_transcript"] = " ".join(
            part for part in [previous_transcript.strip(), transcript.strip()] if part
        )

    for key, value in new_fields.items():
        if key == "severity_indicators":
            merged[key] = _merge_unique_lists(merged.get(key), value)
            continue

        existing_value = merged.get(key)
        if _is_missing(existing_value) and not _is_missing(value):
            merged[key] = value
        elif key in {"normalized_text", "extraction_method"} and not _is_missing(value):
            merged[key] = value

    if normalized_transcript:
        merged["interactive_normalized_text"] = " ".join(
            part
            for part in [
                str(merged.get("interactive_normalized_text") or "").strip(),
                normalized_transcript.strip(),
            ]
            if part
        )

    _apply_location_overrides(normalized_transcript, merged)
    _apply_interactive_overrides(normalized_transcript, merged)
    return merged


def _merge_unique_lists(left: Any, right: Any) -> list:
    merged = []
    for item in (left or []) + (right or []):
        if item and item not in merged:
            merged.append(item)
    return merged


def _apply_interactive_overrides(transcript: str, fields: dict) -> None:
    text = transcript.lower()

    if any(term in text for term in ["traffic", "congestion", "jam", "slow moving", "vehicles moving slowly"]):
        fields["event_type"] = "congestion"

    if any(term in text for term in ["fire", "flames", "smoke"]):
        fields["event_type"] = "fire"
    elif any(term in text for term in ["medical emergency", "ambulance", "injured", "unconscious"]):
        fields["event_type"] = "medical_emergency"

    if any(term in text for term in ["lorry", "truck"]):
        fields["vehicle_type"] = "heavy_vehicle"
    elif any(term in text for term in ["no vehicle", "no vehicles", "not vehicle", "without vehicle"]):
        fields["vehicle_type"] = "not_applicable"

    severity_indicators = fields.get("severity_indicators") or []
    if any(term in text for term in ["blocked", "road block", "lane block"]):
        severity_indicators = _merge_unique_lists(severity_indicators, ["road_block"])
        fields["traffic_condition"] = "blocked"
    elif any(term in text for term in ["slow moving", "vehicles moving slowly", "heavy traffic", "jam"]):
        severity_indicators = _merge_unique_lists(severity_indicators, ["congestion"])
        fields["traffic_condition"] = "slow_moving"
    elif "normal" in text:
        severity_indicators = _merge_unique_lists(severity_indicators, ["low_traffic_impact"])
        fields["traffic_condition"] = "normal"

    if severity_indicators:
        fields["severity_indicators"] = severity_indicators


def _apply_location_overrides(transcript: str, fields: dict) -> None:
    text = transcript.lower()

    for key, display_name in ROAD_LOCATIONS.items():
        if key in text:
            fields["road_name"] = display_name
            fields["location_query"] = display_name
            if _is_unknown_location(fields.get("location_name")):
                fields["location_name"] = display_name
            return

    for key, display_name in LANDMARK_LOCATIONS.items():
        if key in text:
            fields["landmark"] = display_name
            fields["location_query"] = display_name
            if _is_unknown_location(fields.get("location_name")):
                fields["location_name"] = display_name
            return

    for key, display_name in AREA_LOCATIONS.items():
        if key in text:
            fields["location_query"] = display_name
            if _is_unknown_location(fields.get("location_name")):
                fields["location_name"] = display_name
            return


def _next_missing_field_question(incident: dict) -> Optional[str]:
    if _is_unknown(incident.get("event_type")):
        return MISSING_EVENT_TYPE_QUESTION

    if not _has_location(incident):
        return MISSING_LOCATION_QUESTION

    if not _has_traffic_condition_or_severity(incident):
        return MISSING_TRAFFIC_QUESTION

    if _needs_vehicle_type(incident) and _is_unknown(incident.get("vehicle_type")):
        return MISSING_VEHICLE_QUESTION

    return None


def _has_location(incident: dict) -> bool:
    return any(
        not _is_unknown_location(incident.get(key))
        for key in ["location_name", "road_name", "location_query", "landmark"]
    )


def _has_traffic_condition_or_severity(incident: dict) -> bool:
    if not _is_unknown(incident.get("severity")):
        return True

    if not _is_missing(incident.get("traffic_condition")):
        return True

    indicators = incident.get("severity_indicators") or []
    if any(item in indicators for item in ["road_block", "low_traffic_impact"]):
        return True

    text = " ".join(
        str(incident.get(key) or "").lower()
        for key in ["combined_transcript", "normalized_text", "interactive_normalized_text", "description"]
    )
    return any(term in text for term in ["blocked", "slow", "slow moving", "normal", "heavy traffic", "jam"])


def _needs_vehicle_type(incident: dict) -> bool:
    event_type = (incident.get("event_type") or "").lower()
    if event_type in {"congestion", "road_block", "fire", "medical_emergency"}:
        return False
    return True


def _is_unknown(value: Any) -> bool:
    return _is_missing(value) or str(value).strip().lower() == "unknown"


def _is_unknown_location(value: Any) -> bool:
    if _is_missing(value):
        return True
    return str(value).strip().lower() in {"unknown", "unknown location"}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _record_asked_question(incident: dict, question: str) -> None:
    counts = incident.get("_question_counts")
    if not isinstance(counts, dict):
        counts = {}
    counts[question] = int(counts.get(question, 0)) + 1
    incident["_question_counts"] = counts


def _can_complete_after_repeated_question(incident: dict, question: str) -> bool:
    counts = incident.get("_question_counts") if isinstance(incident.get("_question_counts"), dict) else {}
    return (
        int(counts.get(question, 0)) >= 2
        and not _is_unknown(incident.get("event_type"))
        and _has_location(incident)
    )
