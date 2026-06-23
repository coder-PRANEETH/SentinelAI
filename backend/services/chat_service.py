import json
import logging
import os
from typing import Dict, Any

try:
    import google.generativeai as genai
except ImportError:
    genai = None


def answer_incident_question(question: str, incident: Dict[str, Any]) -> Dict[str, str]:
    incident = incident or {}
    use_llm_chat = os.getenv("USE_LLM_CHAT_FALLBACK", "false").lower() == "true"
    fallback_llm_key = os.getenv("LLM_FALLBACK_API_KEY", "").strip()

    if use_llm_chat and fallback_llm_key and genai is not None:
        try:
            return _answer_with_fallback_llm(question, incident, fallback_llm_key)
        except Exception as e:
            logging.warning(f"Fallback LLM chat failed, falling back to rule-based chat: {e}")

    return _answer_rule_based(question, incident)


def _answer_with_fallback_llm(question: str, incident: Dict[str, Any], api_key: str) -> Dict[str, str]:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name="gemini-1.5-mini")
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

    if not answer_text:
        candidates = getattr(response, "candidates", None)
        if candidates and len(candidates) > 0:
            first = candidates[0]
            content = getattr(first, "content", None)
            if isinstance(content, list):
                answer_text = "".join(getattr(part, "text", "") for part in content)
            elif hasattr(content, "text"):
                answer_text = getattr(content, "text")

    answer = answer_text.strip() if isinstance(answer_text, str) else ""
    if not answer:
        raise RuntimeError("Fallback LLM returned no answer")

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


def _resolve_response_unit(location_name: str) -> str:
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


def _answer_rule_based(question: str, incident: Dict[str, Any]) -> Dict[str, str]:
    normalized = question.strip().lower()
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

    def unavailable():
        return "This information is not available in the provided incident data."

    def build_location_answer():
        if location_name and latitude and longitude:
            return f"The incident is located at {location_name} with coordinates latitude {latitude}, longitude {longitude}."
        if location_name:
            return f"The incident is located at {location_name}."
        if latitude and longitude:
            return f"The incident coordinates are latitude {latitude}, longitude {longitude}."
        return None

    def build_priority_answer():
        if severity and severity_reasons:
            return f"This incident is classified as {severity} priority because { _format_list(severity_reasons) }."
        if severity:
            return f"This incident is classified as {severity} priority based on the incident data provided."
        return None

    def build_response_answer():
        unit = _resolve_response_unit(location_name)
        if location_name:
            return f"Recommend dispatching the {unit} for the incident at {location_name}."
        return None

    def build_resolution_answer():
        if severity:
            if severity.lower() == "high":
                return "For a high severity incident, estimated resolution time is 30 to 45 minutes."
            if severity.lower() == "medium":
                return "For a medium severity incident, estimated resolution time is 45 to 60 minutes."
            if severity.lower() == "low":
                return "This is a low severity incident; it should be monitored closely and may not require immediate dispatch."
            return f"Estimated resolution time is not defined for severity level {severity}."
        return None

    def build_summary_answer():
        if summary:
            return f"Summary: {summary}"
        if description:
            return f"Incident description: {description}"
        return None

    def build_similar_answer():
        parts = []
        if event_type:
            parts.append(f"other incidents involving {event_type}")
        if location_name:
            parts.append(f"near {location_name}")
        if not parts:
            return None
        return f"Similar incidents would involve {' and '.join(parts)}."

    def build_action_answer():
        if severity or event_type or vehicle_type or location_name:
            pieces = []
            if severity:
                pieces.append(f"{severity} severity")
            if event_type:
                pieces.append(event_type)
            if vehicle_type:
                pieces.append(vehicle_type)
            if location_name:
                pieces.append(f"at {location_name}")
            details = " ".join(pieces)
            return (
                f"Recommend that the control room notify the response team and monitor the situation. "
                f"Incident details: {details}."
            )
        return None

    if any(term in normalized for term in ["why", "priority", "urgent", "severity"]):
        answer = build_priority_answer()
        return {"answer": answer or unavailable(), "source": "rule_based"}

    if any(term in normalized for term in ["where", "location", "located", "coordinates", "latitude", "longitude", "address"]):
        answer = build_location_answer()
        return {"answer": answer or unavailable(), "source": "rule_based"}

    if any(term in normalized for term in ["station", "respond", "response", "dispatch", "unit", "team"]):
        answer = build_response_answer()
        return {"answer": answer or unavailable(), "source": "rule_based"}

    if any(term in normalized for term in ["how long", "resolve", "resolution", "time", "eta", "estimate"]):
        answer = build_resolution_answer()
        return {"answer": answer or unavailable(), "source": "rule_based"}

    if any(term in normalized for term in ["summary", "summarize", "brief", "recap"]):
        answer = build_summary_answer()
        return {"answer": answer or unavailable(), "source": "rule_based"}

    if any(term in normalized for term in ["similar", "other incident", "like this", "resemble"]):
        answer = build_similar_answer()
        return {"answer": answer or unavailable(), "source": "rule_based"}

    if any(term in normalized for term in ["recommend", "action", "next step", "should", "advise", "control room", "notify", "message"]):
        answer = build_action_answer()
        return {"answer": answer or unavailable(), "source": "rule_based"}

    if any(term in normalized for term in ["vehicle", "truck", "bus", "car", "motorcycle", "van", "heavy vehicle"]):
        if vehicle_type:
            return {"answer": f"The incident involves a {vehicle_type}.", "source": "rule_based"}
        return {"answer": unavailable(), "source": "rule_based"}

    if any(term in normalized for term in ["event", "incident type", "happened", "what happened"]):
        if event_type:
            return {"answer": f"The incident type is {event_type}.", "source": "rule_based"}
        return {"answer": unavailable(), "source": "rule_based"}

    if summary or description or severity or event_type or vehicle_type or location_name:
        details = []
        if severity:
            details.append(f"{severity} severity")
        if event_type:
            details.append(event_type)
        if vehicle_type:
            details.append(vehicle_type)
        if location_name:
            details.append(f"at {location_name}")
        base = "This incident involves " + ", ".join(details) + "." if details else ""
        if summary:
            base += f" Summary: {summary}."
        elif description:
            base += f" Description: {description}."
        if base:
            return {"answer": base.strip(), "source": "rule_based"}

    return {"answer": unavailable(), "source": "rule_based"}
