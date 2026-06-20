"""Incident chat support."""

from __future__ import annotations

import json
import os
from typing import Any

from .exceptions import ConfigurationError
from .logging_utils import get_logger, log_event
from .registry import get_model_registry

logger = get_logger(__name__)


def chat_with_incident(question: str, incident: dict[str, Any]) -> dict[str, str]:
    """Answer a natural-language question about a prepared incident."""
    incident = incident or {}
    use_llm_chat = os.getenv("USE_LLM_CHAT", "false").lower() == "true"

    if use_llm_chat:
        try:
            return _answer_with_gemini(question, incident)
        except Exception as exc:
            log_event(logger, 30, "chat_provider_failed", "Gemini chat failed", error=str(exc))

    return _answer_rule_based(question, incident)


def _answer_with_gemini(question: str, incident: dict[str, Any]) -> dict[str, str]:
    model_name = os.getenv("GEMINI_CHAT_MODEL", "gemini-1.5-mini")
    try:
        model = get_model_registry().get_gemini_model(model_name)
    except ConfigurationError:
        raise

    incident_json = json.dumps(incident, indent=2, ensure_ascii=False)
    prompt = (
        "You are an incident copilot assistant. Use ONLY the provided incident data to answer the question. "
        "Do not hallucinate or invent facts. If the information is missing from the incident data, respond exactly: "
        "\"This information is not available in the provided incident data.\"\n\n"
        f"Incident data:\n{incident_json}\n\n"
        f"Question: {question}\n"
        "Answer:"
    )
    response = model.generate_content(prompt)
    answer_text = getattr(response, "text", None)
    answer = answer_text.strip() if isinstance(answer_text, str) else ""
    if not answer:
        raise RuntimeError("Gemini returned no answer")
    return {"answer": answer, "source": "llm"}


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized or normalized.lower() in {"unknown", "n/a", "none"}:
            return None
        return normalized
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items if items else None
    return value


def _resolve_response_unit(location_name: str | None) -> str:
    if not location_name:
        return "Nearest available traffic response unit"
    mapping = {
        "peenya metro station": "Peenya Traffic Police Unit",
        "kr puram railway station": "KR Puram Traffic Police Unit",
        "silk board junction": "Silk Board Traffic Response Unit",
        "hebbal flyover": "Hebbal Traffic Response Unit",
        "orion mall": "Rajajinagar/Malleshwaram Traffic Unit",
    }
    return mapping.get(location_name.lower(), "Nearest available traffic response unit")


def _format_list(value: Any) -> str:
    cleaned = _clean_value(value)
    if isinstance(cleaned, list):
        return ", ".join(cleaned)
    if isinstance(cleaned, str):
        return cleaned
    return ""


def _answer_rule_based(question: str, incident: dict[str, Any]) -> dict[str, str]:
    normalized = (question or "").strip().lower()
    event_type = _clean_value(incident.get("event_type"))
    vehicle_type = _clean_value(incident.get("vehicle_type"))
    location_name = (
        _clean_value(incident.get("location_name"))
        or _clean_value(incident.get("landmark"))
        or _clean_value(incident.get("road_name"))
    )
    severity = _clean_value(incident.get("severity"))
    severity_reasons = _clean_value(incident.get("severity_reasons")) or []
    summary = _clean_value(incident.get("summary"))
    description = _clean_value(incident.get("description"))
    latitude = _clean_value(incident.get("latitude"))
    longitude = _clean_value(incident.get("longitude"))

    def unavailable() -> str:
        return "This information is not available in the provided incident data."

    def location_answer() -> str | None:
        if location_name and latitude and longitude:
            return f"The incident is located at {location_name} with coordinates latitude {latitude}, longitude {longitude}."
        if location_name:
            return f"The incident is located at {location_name}."
        if latitude and longitude:
            return f"The incident coordinates are latitude {latitude}, longitude {longitude}."
        return None

    if any(term in normalized for term in ["why", "priority", "urgent", "severity"]):
        if severity and severity_reasons:
            answer = f"This incident is classified as {severity} priority because {_format_list(severity_reasons)}."
        elif severity:
            answer = f"This incident is classified as {severity} priority based on the incident data provided."
        else:
            answer = unavailable()
        return {"answer": answer, "source": "rule_based"}

    if any(term in normalized for term in ["where", "location", "located", "coordinates", "latitude", "longitude", "address"]):
        return {"answer": location_answer() or unavailable(), "source": "rule_based"}

    if any(term in normalized for term in ["station", "respond", "response", "dispatch", "unit", "team"]):
        if location_name:
            unit = _resolve_response_unit(str(location_name))
            return {"answer": f"Recommend dispatching the {unit} for the incident at {location_name}.", "source": "rule_based"}
        return {"answer": unavailable(), "source": "rule_based"}

    if any(term in normalized for term in ["how long", "resolve", "resolution", "time", "eta", "estimate"]):
        if severity and str(severity).lower() == "high":
            answer = "For a high severity incident, estimated resolution time is 30 to 45 minutes."
        elif severity and str(severity).lower() == "medium":
            answer = "For a medium severity incident, estimated resolution time is 45 to 60 minutes."
        elif severity and str(severity).lower() == "low":
            answer = "This is a low severity incident; it should be monitored closely and may not require immediate dispatch."
        else:
            answer = unavailable()
        return {"answer": answer, "source": "rule_based"}

    if any(term in normalized for term in ["summary", "summarize", "brief", "recap"]):
        answer = f"Summary: {summary}" if summary else (f"Incident description: {description}" if description else unavailable())
        return {"answer": answer, "source": "rule_based"}

    if any(term in normalized for term in ["vehicle", "truck", "bus", "car", "motorcycle", "van", "heavy vehicle"]):
        answer = f"The incident involves a {vehicle_type}." if vehicle_type else unavailable()
        return {"answer": answer, "source": "rule_based"}

    if any(term in normalized for term in ["event", "incident type", "happened", "what happened"]):
        answer = f"The incident type is {event_type}." if event_type else unavailable()
        return {"answer": answer, "source": "rule_based"}

    details = [part for part in [severity, event_type, vehicle_type, f"at {location_name}" if location_name else None] if part]
    if details:
        base = "This incident involves " + ", ".join(str(part) for part in details) + "."
        if summary:
            base += f" Summary: {summary}."
        elif description:
            base += f" Description: {description}."
        return {"answer": base.strip(), "source": "rule_based"}

    return {"answer": unavailable(), "source": "rule_based"}
