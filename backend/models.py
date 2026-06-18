from pydantic import BaseModel
from typing import Optional, List


class IncidentRequest(BaseModel):
    transcript: str


class ExtractedIncident(BaseModel):
    event_type: Optional[str] = None
    vehicle_type: Optional[str] = None
    landmark: Optional[str] = None
    road_name: Optional[str] = None
    severity_indicators: List[str] = []


class IncidentSummaryRequest(BaseModel):
    incident: dict


class LocationExtractRequest(BaseModel):
    text: str


class VoiceReportRequest(BaseModel):
    transcript: str


class DispatchIncidentRequest(BaseModel):
    incident: dict


class IncidentChatRequest(BaseModel):
    question: str
    incident: dict
