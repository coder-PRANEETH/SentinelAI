"""Incident field extraction with rule-based and optional LLM providers."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from .exceptions import ConfigurationError, ExtractionError
from .logging_utils import get_logger, log_event
from .registry import get_model_registry

logger = get_logger(__name__)

KNOWN_LANDMARKS = [
    "Peenya Metro Station",
    "Orion Mall",
    "Majestic Bus Station",
    "Silk Board Junction",
    "Hebbal Flyover",
    "KR Puram Railway Station",
    "Hopes College Signal",
    "Gandhipuram Signal",
    "Avinashi Road Flyover",
]

KNOWN_ROADS = [
    "Tumkur Road",
    "Hosur Road",
    "Outer Ring Road",
    "Bellary Road",
    "Old Madras Road",
    "Mysore Road",
    "Trichy Road",
    "Avinashi Road",
]

STT_CORRECTIONS = {
    "break down": "breakdown",
    "pinyam metro station": "peenya metro station",
    "penya metro station": "peenya metro station",
    "peenya metro": "peenya metro station",
    "tumkhu road": "tumkur road",
    "tumkoor road": "tumkur road",
    "tumkur rod": "tumkur road",
    "neat": "near",
    "lorry": "truck",
    "jam": "congestion",
    "signal": "junction",
}

DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Coimbatore")
DEFAULT_STATE = os.getenv("DEFAULT_STATE", "Tamil Nadu")
DEFAULT_COUNTRY = os.getenv("DEFAULT_COUNTRY", "India")

EXTRACTION_PROMPT = """You are an expert incident traffic analysis AI. Extract structured incident information from the given transcript.

TRANSCRIPT: {transcript}

Return ONLY a valid JSON object (no markdown, no explanation, just JSON) with this schema:
{{
    "event_type": "accident | vehicle_breakdown | congestion | road_block | illegal_parking | fire | medical_emergency | unknown",
    "event_cause": "string or null (Attempt to infer from context if not explicit. e.g. tyre burst, engine failure, overheating)",
    "vehicle_type": "two_wheeler | car | bus | truck | heavy_vehicle | unknown",
    "landmark": "string or null (Specific building, station, mall)",
    "junction": "string or null (Junction name if mentioned)",
    "road_name": "string or null (Road or highway name)",
    "severity_indicators": ["array", "of", "indicators"],
    "time_mentioned": "string or null",
    "additional_notes": "string or null"
}}

Important:
1. Return ONLY valid JSON, no additional text.
2. Be accurate and extract what is actually mentioned.
3. If unsure, use "unknown" or null. Do not fabricate information.
4. Keep JSON compact and valid.
5. Corridor (road_name) and Location/Junction (landmark/junction) must not be identical; Location/Junction should be the more specific landmark, junction, or sub-location mentioned, not a repeat of the corridor name.
6. If event_cause is not explicitly labeled but can be inferred from context (e.g. "tyre burst", "engine failure"), extract it. Otherwise, leave it null."""


def normalize_transcript(text: str) -> str:
    """Normalize transcript text and common STT mistakes."""
    normalized = (text or "").lower()
    for mistake, correction in STT_CORRECTIONS.items():
        normalized = normalized.replace(mistake, correction)
    return normalized


def extract_incident_fields(transcript: str) -> dict[str, Any]:
    """Extract incident fields using deterministic rules."""
    text = normalize_transcript(transcript)
    event_type = "unknown"
    vehicle_type = "unknown"

    if any(word in text for word in ["accident", "crash", "collision"]):
        event_type = "accident"
    elif any(word in text for word in ["breakdown", "stalled"]):
        event_type = "vehicle_breakdown"
    elif any(word in text for word in ["blocked", "blocking", "road block", "lane block"]):
        event_type = "road_block"
    elif any(word in text for word in ["parked", "parking", "shoulder"]):
        event_type = "illegal_parking"
    elif (
        any(
            word in text
            for word in [
                "traffic building up",
                "heavy traffic",
                "congestion",
                "jam",
                "vehicles are moving slowly",
                "vehicles moving slowly",
            ]
        )
        and "no major traffic issue" not in text
        and "no traffic impact" not in text
    ):
        event_type = "congestion"
    elif (
        "traffic" in text
        and any(word in text for word in ["near", "at", "on", "road", "junction", "signal", "flyover"])
        and "no major traffic issue" not in text
        and "no traffic impact" not in text
    ):
        event_type = "congestion"

    if "truck" in text or "heavy vehicle" in text or "container" in text:
        vehicle_type = "heavy_vehicle"
    elif "bus" in text:
        vehicle_type = "bus"
    elif "car" in text:
        vehicle_type = "car"
    elif "bike" in text or "two wheeler" in text or "two-wheeler" in text:
        vehicle_type = "two_wheeler"

    landmark = next((item for item in KNOWN_LANDMARKS if item.lower() in text), None)
    road_name = next((road for road in KNOWN_ROADS if road.lower() in text), None)

    severity_indicators: list[str] = []
    if event_type != "unknown":
        severity_indicators.append(event_type)
    if vehicle_type != "unknown":
        severity_indicators.append(vehicle_type)
    if landmark:
        severity_indicators.append("known_landmark")
    if road_name:
        severity_indicators.append("known_road")
    if any(word in text for word in ["blocked", "blocking", "road block", "lane block"]):
        severity_indicators.append("road_block")
    if (
        any(
            word in text
            for word in [
                "traffic building up",
                "heavy traffic",
                "congestion",
                "jam",
                "vehicles are moving slowly",
                "vehicles moving slowly",
            ]
        )
        and "no major traffic issue" not in text
        and "no traffic impact" not in text
    ):
        severity_indicators.append("congestion")
    if "no major traffic issue" in text or "no traffic impact" in text:
        severity_indicators.append("low_traffic_impact")

    return {
        "event_type": event_type,
        "vehicle_type": vehicle_type,
        "landmark": landmark,
        "road_name": road_name,
        "severity_indicators": severity_indicators,
        "normalized_text": text,
    }


def extract_incident_fields_llm(transcript: str) -> Optional[dict[str, Any]]:
    """Extract incident fields using the configured Gemini model."""
    try:
        model = get_model_registry().get_gemini_model(os.getenv("GEMINI_EXTRACTION_MODEL", "gemini-2.0-flash"))
    except ConfigurationError as exc:
        log_event(logger, 30, "provider_unavailable", "Gemini extraction unavailable", error=str(exc))
        return None

    try:
        response = model.generate_content(EXTRACTION_PROMPT.format(transcript=transcript))
        response_text = getattr(response, "text", "") or ""
        if not response_text:
            log_event(logger, 40, "empty_provider_response", "Empty response from Gemini")
            return None

        json_text = _strip_json_code_fence(response_text)
        extracted = json.loads(json_text)
        if not isinstance(extracted, dict):
            return None
        _apply_extraction_defaults(extracted, transcript)
        log_event(logger, 20, "extraction_success", "Gemini extraction successful", method="gemini")
        return extracted
    except json.JSONDecodeError as exc:
        log_event(logger, 40, "json_parse_failed", "Failed to parse Gemini extraction JSON", error=str(exc))
        return None
    except Exception as exc:
        log_event(logger, 40, "provider_failed", "Gemini extraction failed", error=str(exc))
        return None


def extract_incident_fields_openai(transcript: str) -> Optional[dict[str, Any]]:
    """Extract incident fields using the configured OpenAI chat model."""
    try:
        client = get_model_registry().get_openai_client()
    except ConfigurationError as exc:
        log_event(logger, 30, "provider_unavailable", "OpenAI extraction unavailable", error=str(exc))
        return None

    system_prompt = f"""You are an expert traffic incident analyzer for roads.
Extract structured incident information from natural language reports.

Rules:
1. Correct common spelling errors.
2. Understand lorry/truck/heavy vehicle, jam/congestion, signal/junction, bike/two wheeler.
3. If user mentions traffic near/at a place, classify event_type as congestion.
4. Only classify accident or breakdown if explicitly mentioned.
5. Extract landmark, junction, road_name, and location_query separately.
6. If city/state/country are missing, use defaults.
7. Return ONLY valid JSON matching the schema.

Default location:
- city: {DEFAULT_CITY}
- state: {DEFAULT_STATE}
- country: {DEFAULT_COUNTRY}

Return JSON with:
event_type, vehicle_type, landmark, junction, road_name, location_query,
city, state, country, severity_indicators, normalized_text, confidence."""

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_EXTRACTION_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this incident report:\n\n{transcript}"},
            ],
            temperature=0.1,
            max_tokens=500,
        )
        response_text = (response.choices[0].message.content or "").strip()
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start < 0 or json_end <= json_start:
            return None
        extracted = json.loads(response_text[json_start:json_end])
        if not isinstance(extracted, dict):
            return None
        _apply_extraction_defaults(extracted, transcript)
        log_event(logger, 20, "extraction_success", "OpenAI extraction successful", method="openai")
        return extracted
    except Exception as exc:
        log_event(logger, 40, "provider_failed", "OpenAI extraction failed", error=str(exc))
        return None


def extract_with_best_provider(transcript: str) -> dict[str, Any]:
    """Extract fields with OpenAI, Gemini, then rule-based fallback."""
    clean_transcript = (transcript or "").strip()
    if not clean_transcript:
        raise ExtractionError("Transcript is empty")

    if os.getenv("USE_OPENAI_EXTRACTION", "false").lower() == "true":
        extracted = extract_incident_fields_openai(clean_transcript)
        if extracted:
            extracted["extraction_method"] = "openai"
            return extracted

    if os.getenv("USE_LLM_EXTRACTION", "false").lower() == "true":
        extracted = extract_incident_fields_llm(clean_transcript)
        if extracted:
            extracted["extraction_method"] = "llm"
            return extracted

    extracted = extract_incident_fields(clean_transcript)
    extracted["extraction_method"] = "rule_based_fallback"
    return extracted


def _strip_json_code_fence(text: str) -> str:
    json_text = text.strip()
    if json_text.startswith("```"):
        json_text = json_text.split("```")[1]
        if json_text.startswith("json"):
            json_text = json_text[4:]
    return json_text.strip()


def _apply_extraction_defaults(extracted: dict[str, Any], transcript: str) -> None:
    extracted.setdefault("event_type", "unknown")
    extracted.setdefault("vehicle_type", "unknown")
    extracted.setdefault("landmark", None)
    extracted.setdefault("junction", None)
    extracted.setdefault("road_name", None)
    extracted.setdefault("location_query", None)
    extracted.setdefault("city", DEFAULT_CITY)
    extracted.setdefault("state", DEFAULT_STATE)
    extracted.setdefault("country", DEFAULT_COUNTRY)
    extracted.setdefault("severity_indicators", [])
    extracted.setdefault("normalized_text", transcript.lower())
    extracted.setdefault("confidence", 0.8)
    if not isinstance(extracted.get("severity_indicators"), list):
        extracted["severity_indicators"] = []
