"""Stateful voice-session support without module-level session retention."""

from __future__ import annotations

import re
from typing import Any, Optional

from .engine import generate_incident_object, process_text
from .extraction import extract_with_best_provider
from .geocoding import resolve_location_with_geocoding
from .models import VoiceSessionState, VoiceTurnResult
from .severity import assess_severity
from .summary import generate_summary

MISSING_EVENT_TYPE_QUESTION = (
    "What happened exactly? Was it an accident, breakdown, congestion, road block, fire, or medical emergency?"
)
MISSING_LOCATION_QUESTION = "Where exactly did this happen? Please mention road name, junction, landmark, or area."
MISSING_TRAFFIC_QUESTION = "Is traffic blocked, slow moving, or normal?"
MISSING_VEHICLE_QUESTION = "What vehicle is involved, like bike, car, bus, truck, or lorry? If no vehicle is involved, say no vehicle."

LOCATION_NORMALIZATIONS = [
    ("tiruchiruode", "trichy road"),
    ("tiruchi road", "trichy road"),
    ("tiruchy road", "trichy road"),
    ("trichiro", "trichy road"),
    ("namakal junction", "namakkal junction"),
    ("namakal", "namakkal"),
    ("gandipuram", "gandhipuram"),
    ("hopes college", "hopes college signal"),
    ("avinashi", "avinashi road"),
]

ROAD_LOCATIONS = {"trichy road": "Trichy Road", "avinashi road": "Avinashi Road"}
LANDMARK_LOCATIONS = {
    "namakkal junction": "Namakkal Junction",
    "gandhipuram signal": "Gandhipuram Signal",
    "hopes college signal": "Hopes College Signal",
}
AREA_LOCATIONS = {"namakkal": "Namakkal", "gandhipuram": "Gandhipuram", "coimbatore": "Coimbatore"}


class VoiceSession:
    """One isolated interactive voice session."""

    def __init__(self, initial_incident: Optional[dict[str, Any]] = None) -> None:
        self.state = VoiceSessionState(current_incident=initial_incident.copy() if initial_incident else {})

    def process(self, user_text: str) -> dict[str, Any]:
        """Process one user utterance and return either a question or incident."""
        result = process_interactive_voice_turn(user_text, self.state.current_incident)
        self.state.current_incident = result["current_incident"]
        if result.get("complete"):
            self.state.finalized_incident = result.get("incident")
        return result

    def finalize(self) -> dict[str, Any]:
        """Finalize the current session into an incident summary payload."""
        if self.state.finalized_incident is not None:
            incident = self.state.finalized_incident
        else:
            incident = _complete_incident(self.state.current_incident, "").incident or {}
            self.state.finalized_incident = incident
        return {"incident": incident, "summary": generate_summary(incident)}


def start_voice_session(initial_incident: Optional[dict[str, Any]] = None) -> VoiceSession:
    """Create a new isolated voice session."""
    return VoiceSession(initial_incident)


def process_interactive_voice_turn(
    transcript: str,
    current_incident: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Merge one voice-call transcript turn and return the next action."""
    clean_transcript = (transcript or "").strip()
    normalized_transcript = normalize_interactive_transcript(clean_transcript)
    existing = current_incident.copy() if isinstance(current_incident, dict) else {}
    new_fields = extract_with_best_provider(normalized_transcript) if normalized_transcript else {}
    _apply_interactive_overrides(normalized_transcript, new_fields)

    merged = _merge_incident_fields(existing, new_fields, clean_transcript, normalized_transcript)
    next_question = _next_missing_field_question(merged)

    if next_question:
        if _can_complete_after_repeated_question(merged, next_question):
            return _complete_incident(merged, clean_transcript).to_dict()

        _record_asked_question(merged, next_question)
        return VoiceTurnResult(False, next_question, merged).to_dict()

    return _complete_incident(merged, clean_transcript).to_dict()


def normalize_interactive_transcript(text: str) -> str:
    normalized = (text or "").lower()
    for mistake, correction in LOCATION_NORMALIZATIONS:
        normalized = normalized.replace(mistake, correction)
    return normalized


def normalize_streaming_transcript(transcript: str) -> str:
    text = transcript.strip()
    if not text:
        return ""
    lower_text = text.lower()
    if "i'm sorry, i'm sorry" in lower_text or "i am sorry, i am sorry" in lower_text:
        return ""
    replacements = {
        "traffic condition": "__CONGESTION__",
        "traffic jam": "__CONGESTION__",
        "heavy traffic": "__CONGESTION__",
        "slow traffic": "__CONGESTION__",
        "slow moving": "__CONGESTION__",
        "conjition": "__CONGESTION__",
        "condition": "__CONGESTION__",
        "conjection": "__CONGESTION__",
        "conjestion": "__CONGESTION__",
        "congestion": "__CONGESTION__",
        "jam": "__CONGESTION__",
        "action": "__ACCIDENT__",
        "axident": "__ACCIDENT__",
        "accident": "__ACCIDENT__",
        "crash": "__ACCIDENT__",
        "collision": "__ACCIDENT__",
        "good luck": "__ROAD_BLOCK__",
        "another block": "__ROAD_BLOCK__",
        "roadblock": "__ROAD_BLOCK__",
        "road block": "__ROAD_BLOCK__",
        "road black": "__ROAD_BLOCK__",
        "blocked": "__ROAD_BLOCK__",
        "block": "__ROAD_BLOCK__",
        "namakal junction": "__NAMAKKAL__",
        "namakkal junction": "__NAMAKKAL__",
        "namakal": "__NAMAKKAL__",
        "namakkal": "__NAMAKKAL__",
    }
    normalized = text
    for source, target in replacements.items():
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized, flags=re.IGNORECASE)
    return (
        normalized.replace("__CONGESTION__", "congestion")
        .replace("__ACCIDENT__", "accident")
        .replace("__ROAD_BLOCK__", "road block")
        .replace("__NAMAKKAL__", "Namakkal")
        .strip()
    )


def get_streaming_expected_field(current_incident: dict[str, Any]) -> Optional[str]:
    if not current_incident.get("event_type"):
        return "event_type"
    if not current_incident.get("location_name") and not current_incident.get("road_name"):
        return "location"
    if not current_incident.get("traffic_condition"):
        return "traffic_condition"
    if not current_incident.get("severity"):
        return "severity"
    return None


def update_streaming_current_incident(
    current_incident: dict[str, Any],
    transcript: str,
    expected_field: Optional[str],
) -> None:
    text = transcript.lower()
    if expected_field == "event_type" or not current_incident.get("event_type"):
        if any(phrase in text for phrase in ["congestion", "traffic", "jam", "slow moving"]):
            current_incident["event_type"] = "congestion"
        if "accident" in text:
            current_incident["event_type"] = "accident"
        if "road block" in text or "blocked" in text:
            current_incident["event_type"] = "road_block"
        if "breakdown" in text:
            current_incident["event_type"] = "vehicle_breakdown"
        if "fire" in text:
            current_incident["event_type"] = "fire"
        if any(phrase in text for phrase in ["medical", "ambulance", "injured"]):
            current_incident["event_type"] = "medical_emergency"

    location = extract_location_from_text(transcript)
    if location.get("location_name"):
        current_incident["location_name"] = location["location_name"]
    if location.get("road_name"):
        current_incident["road_name"] = location["road_name"]
    if location.get("lat") is not None and location.get("lng") is not None:
        current_incident["lat"] = location["lat"]
        current_incident["lng"] = location["lng"]

    is_traffic_answer = expected_field == "traffic_condition" or any(
        phrase in text
        for phrase in ["blocked", "road blocked", "not moving", "stopped", "slow", "slow moving", "heavy traffic", "jam", "normal", "clear", "okay", "moving"]
    )
    if is_traffic_answer and any(phrase in text for phrase in ["blocked", "road blocked", "road block", "not moving", "stopped"]):
        current_incident["traffic_condition"] = "blocked"
    elif is_traffic_answer and any(phrase in text for phrase in ["slow", "slow moving", "heavy traffic", "jam", "congestion"]):
        current_incident["traffic_condition"] = "slow_moving"
    elif is_traffic_answer and any(phrase in text for phrase in ["normal", "clear", "okay", "moving"]):
        current_incident["traffic_condition"] = "normal"

    severity = parse_streaming_severity(transcript)
    if severity and (expected_field == "severity" or not current_incident.get("severity")):
        current_incident["severity"] = severity


def parse_streaming_severity(transcript: str) -> Optional[str]:
    text = transcript.lower()

    def has_phrase(phrases: list[str]) -> bool:
        return any(re.search(rf"\b{re.escape(phrase)}\b", text) for phrase in phrases)

    if has_phrase(["i can hear you, i can hear you", "i can hear you i can hear you"]):
        return None
    if has_phrase(["not too serious", "medium", "mediam", "median", "moderate", "normal severity"]):
        return "medium"
    if has_phrase(["not serious", "low", "lo", "love", "hello", "hi", "minor", "small"]):
        return "low"
    if has_phrase(["high", "hai", "height", "serious", "major", "emergency", "critical"]):
        return "high"
    return None


def get_streaming_default_severity(current_incident: dict[str, Any]) -> str:
    if current_incident.get("event_type") == "road_block" and current_incident.get("traffic_condition") == "blocked":
        return "high"
    if current_incident.get("event_type") == "congestion":
        return "medium"
    return "medium"


def get_streaming_next_question(current_incident: dict[str, Any]) -> tuple[bool, Optional[str]]:
    if not current_incident.get("event_type"):
        return False, "What happened exactly? Was it an accident, breakdown, congestion, road block, fire, or medical emergency?"
    if not current_incident.get("location_name") and not current_incident.get("road_name"):
        return False, "Where is the incident happening?"
    if not current_incident.get("traffic_condition"):
        return False, "Is traffic blocked, slow moving, or normal?"
    if not current_incident.get("severity"):
        return False, "How severe is it? Please say low, medium, or high."
    return True, None


def extract_location_from_text(text: str) -> dict[str, Any]:
    result = process_text(text)
    incident = result["incident"]
    return {
        "location_name": incident.get("location_name"),
        "road_name": incident.get("corridor"),
        "lat": incident.get("latitude"),
        "lng": incident.get("longitude"),
    }


def _complete_incident(merged: dict[str, Any], transcript: str) -> VoiceTurnResult:
    combined_transcript = merged.get("combined_transcript") or transcript
    location = resolve_location_with_geocoding(merged)
    severity = assess_severity(combined_transcript, merged)
    incident = generate_incident_object(combined_transcript, merged, severity, location)
    return VoiceTurnResult(True, None, merged, incident=incident)


def _merge_incident_fields(
    existing: dict[str, Any],
    new_fields: dict[str, Any],
    transcript: str,
    normalized_transcript: str,
) -> dict[str, Any]:
    merged = existing.copy()
    previous_transcript = merged.get("combined_transcript") or merged.get("transcript") or ""
    if transcript:
        merged["combined_transcript"] = " ".join(part for part in [previous_transcript.strip(), transcript.strip()] if part)

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
        previous = str(merged.get("interactive_normalized_text") or "").strip()
        merged["interactive_normalized_text"] = " ".join(part for part in [previous, normalized_transcript.strip()] if part)

    _apply_location_overrides(normalized_transcript, merged)
    _apply_interactive_overrides(normalized_transcript, merged)
    return merged


def _merge_unique_lists(left: Any, right: Any) -> list[Any]:
    merged: list[Any] = []
    for item in (left or []) + (right or []):
        if item and item not in merged:
            merged.append(item)
    return merged


def _apply_interactive_overrides(transcript: str, fields: dict[str, Any]) -> None:
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
        fields["traffic_condition"] = "blocked"
        severity_indicators = _merge_unique_lists(severity_indicators, ["road_block"])
    elif any(term in text for term in ["slow moving", "vehicles moving slowly", "heavy traffic", "jam"]):
        fields["traffic_condition"] = "slow_moving"
        severity_indicators = _merge_unique_lists(severity_indicators, ["congestion"])
    elif "normal" in text:
        fields["traffic_condition"] = "normal"
        severity_indicators = _merge_unique_lists(severity_indicators, ["low_traffic_impact"])
    if severity_indicators:
        fields["severity_indicators"] = severity_indicators


def _apply_location_overrides(transcript: str, fields: dict[str, Any]) -> None:
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


def _next_missing_field_question(incident: dict[str, Any]) -> Optional[str]:
    if _is_unknown(incident.get("event_type")):
        return MISSING_EVENT_TYPE_QUESTION
    if not _has_location(incident):
        return MISSING_LOCATION_QUESTION
    if not _has_traffic_condition_or_severity(incident):
        return MISSING_TRAFFIC_QUESTION
    if _needs_vehicle_type(incident) and _is_unknown(incident.get("vehicle_type")):
        return MISSING_VEHICLE_QUESTION
    return None


def _has_location(incident: dict[str, Any]) -> bool:
    return any(not _is_unknown_location(incident.get(key)) for key in ["location_name", "road_name", "location_query", "landmark"])


def _has_traffic_condition_or_severity(incident: dict[str, Any]) -> bool:
    if not _is_unknown(incident.get("severity")):
        return True
    if not _is_missing(incident.get("traffic_condition")):
        return True
    indicators = incident.get("severity_indicators") or []
    if any(item in indicators for item in ["road_block", "low_traffic_impact"]):
        return True
    text = " ".join(str(incident.get(key) or "").lower() for key in ["combined_transcript", "normalized_text", "interactive_normalized_text", "description"])
    return any(term in text for term in ["blocked", "slow", "slow moving", "normal", "heavy traffic", "jam"])


def _needs_vehicle_type(incident: dict[str, Any]) -> bool:
    event_type = (incident.get("event_type") or "").lower()
    return event_type not in {"congestion", "road_block", "fire", "medical_emergency"}


def _is_unknown(value: Any) -> bool:
    return _is_missing(value) or str(value).strip().lower() == "unknown"


def _is_unknown_location(value: Any) -> bool:
    return _is_missing(value) or str(value).strip().lower() in {"unknown", "unknown location"}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _record_asked_question(incident: dict[str, Any], question: str) -> None:
    counts = incident.get("_question_counts")
    if not isinstance(counts, dict):
        counts = {}
    counts[question] = int(counts.get(question, 0)) + 1
    incident["_question_counts"] = counts


def _can_complete_after_repeated_question(incident: dict[str, Any], question: str) -> bool:
    counts = incident.get("_question_counts") if isinstance(incident.get("_question_counts"), dict) else {}
    return int(counts.get(question, 0)) >= 2 and not _is_unknown(incident.get("event_type")) and _has_location(incident)
