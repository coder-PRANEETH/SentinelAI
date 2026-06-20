"""Typed data models used by the importable backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, TypedDict


class IncidentDict(TypedDict, total=False):
    incident_id: str
    event_type: str
    vehicle_type: str
    location_name: str
    corridor: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    location_source: Optional[str]
    location_confidence: Optional[float]
    severity: str
    confidence: float
    severity_score: int
    severity_reasons: list[str]
    description: str
    timestamp: str
    summary: str


@dataclass(slots=True)
class ProcessingResult:
    """Result returned by text and audio processing helpers."""

    success: bool
    transcript: str
    extracted: dict[str, Any]
    incident: dict[str, Any]
    extraction_method: Optional[str] = None
    input_type: str = "text"

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "input_type": self.input_type,
            "extraction_method": self.extraction_method,
            "transcript": self.transcript,
            "extracted": self.extracted,
            "incident": self.incident,
        }


@dataclass(slots=True)
class VoiceTurnResult:
    """Result for a single voice session turn."""

    complete: bool
    next_question: Optional[str]
    current_incident: dict[str, Any]
    incident: Optional[dict[str, Any]] = None
    transcript: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "complete": self.complete,
            "next_question": self.next_question,
            "current_incident": self.current_incident,
        }
        if self.incident is not None:
            payload["incident"] = self.incident
        if self.transcript is not None:
            payload["transcript"] = self.transcript
        return payload


@dataclass
class VoiceSessionState:
    """Mutable state for one importable voice session."""

    current_incident: dict[str, Any] = field(default_factory=dict)
    finalized_incident: Optional[dict[str, Any]] = None
