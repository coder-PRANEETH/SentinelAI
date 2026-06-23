"""Importable incident processing engine."""

from __future__ import annotations

from datetime import datetime
import random
from pathlib import Path
from typing import Any

from .extraction import extract_incident_fields, extract_with_best_provider
from .geocoding import resolve_location_with_geocoding
from .models import ProcessingResult
from .severity import assess_severity
from .summary import generate_summary
from .transcription import transcribe


def process_text(text: str) -> dict[str, Any]:
    """Run the full incident intelligence pipeline for text input."""
    transcript = (text or "").strip()
    extracted = extract_with_best_provider(transcript)
    location = resolve_location_with_geocoding(extracted)
    severity = assess_severity(transcript, extracted)
    incident = generate_incident_object(transcript, extracted, severity, location)
    return ProcessingResult(
        success=True,
        transcript=transcript,
        extracted=extracted,
        incident=incident,
        extraction_method=extracted.get("extraction_method"),
        input_type="text",
    ).to_dict()


def process_audio(audio_path: str | Path) -> dict[str, Any]:
    """Transcribe an audio file, then run the incident pipeline."""
    transcript = transcribe(audio_path)
    result = process_text(transcript)
    result["input_type"] = "audio_file"
    return result


def generate_incident_object(
    transcript: str,
    extracted: dict[str, Any],
    severity: dict[str, Any],
    location: dict[str, Any],
) -> dict[str, Any]:
    """Generate a standardized incident object including resolved location."""
    location_name = (
        location.get("location_name")
        or extracted.get("location_name")
        or extracted.get("landmark")
        or extracted.get("road_name")
        or "unknown"
    )
    incident = {
        "incident_id": _generate_incident_id(),
        "event_type": extracted.get("event_type") or "unknown",
        "event_cause": extracted.get("event_cause"),
        "vehicle_type": extracted.get("vehicle_type") or "unknown",
        "location_name": location_name,
        "corridor": extracted.get("road_name") or location.get("corridor"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "location_source": location.get("location_source") or location.get("source"),
        "location_confidence": location.get("location_confidence") or location.get("confidence"),
        "severity": severity.get("severity"),
        "confidence": severity.get("confidence"),
        "severity_score": severity.get("severity_score"),
        "severity_reasons": severity.get("severity_reasons"),
        "description": transcript,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    incident["summary"] = generate_summary(incident)
    return incident


def extract_location_from_text(text: str) -> dict[str, Any]:
    """Extract and resolve only location data from free text."""
    extracted = extract_incident_fields(text)
    location = resolve_location_with_geocoding(extracted)
    return {
        "input_text": (text or "").strip(),
        "extracted_location": {
            "landmark": extracted.get("landmark"),
            "road_name": extracted.get("road_name"),
            "location_query": extracted.get("location_query"),
        },
        "resolved_location": location,
    }


def _generate_incident_id() -> str:
    date = datetime.utcnow().strftime("%Y%m%d")
    suffix = f"{random.randint(0, 99999):05d}"
    return f"INC-{date}-{suffix}"
