from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from schemas import IncidentRequest, InteractiveVoiceSessionRequest, IncidentSummaryRequest, LocationExtractRequest, VoiceReportRequest, DispatchIncidentRequest, IncidentChatRequest
from services.extraction_service import extract_incident_fields
from services.llm_extraction_service import extract_incident_fields_llm
from services.openai_extraction_service import extract_incident_fields_openai
from services.location_service import resolve_location
from services.geocoding_service import geocode_location
from services.severity_service import assess_severity
from services.incident_service import generate_incident_object
from services.summary_service import generate_incident_summary
from services.stt_service import transcribe_audio_file
from services.module_dispatch_service import dispatch_incident_to_modules
from services.chat_service import answer_incident_question
from services.interactive_call_service import process_interactive_voice_turn
import os
import shutil
import json
import uuid
import tempfile
import re
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import logging

from llm_backend.transcription import transcribe
from llm_backend.voice import (
    start_voice_session,
    normalize_streaming_transcript,
    get_streaming_expected_field,
    update_streaming_current_incident,
    get_streaming_next_question,
    get_streaming_default_severity,
    parse_streaming_severity
)

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SentinelAI Incident Copilot Backend")

# ── CORS ─────────────────────────────────────────────────────────────────────
# Single unified CORS policy covering both FastAPI and the Flask sub-app.
# The mounted Flask app also enables CORS now so preflight requests are
# handled correctly even when the browser reaches the WSGI sub-app directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://sentinel-ai-ashen-seven.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_http_traffic(request, call_next):
    origin = request.headers.get("origin")
    logger.info(
        "[FastAPI] -> %s %s origin=%s",
        request.method,
        request.url.path,
        origin,
    )
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "[FastAPI] !! %s %s origin=%s",
            request.method,
            request.url.path,
            origin,
        )
        raise
    logger.info(
        "[FastAPI] <- %s %s %s origin=%s",
        request.method,
        request.url.path,
        response.status_code,
        origin,
    )
    return response

# Create temp_uploads folder if it doesn't exist
TEMP_UPLOADS_DIR = "temp_uploads"
Path(TEMP_UPLOADS_DIR).mkdir(exist_ok=True)

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USE_LLM_EXTRACTION = os.getenv("USE_LLM_EXTRACTION", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USE_OPENAI_EXTRACTION = os.getenv("USE_OPENAI_EXTRACTION", "false").lower() == "true"


def process_incident_pipeline(transcript: str) -> dict:
    """
    Process incident through extraction pipeline:
    1. OpenAI extraction (if enabled and API key exists)
    2. Gemini LLM extraction (if enabled and API key exists)
    3. Rule-based extraction (fallback)
    
    Args:
        transcript: Incident transcript
        
    Returns:
        Dictionary with extracted fields and metadata including extraction_method
    """
    extraction_method = "rule_based_fallback"
    
    # Priority 1: Try OpenAI extraction if enabled and API key exists
    if USE_OPENAI_EXTRACTION and OPENAI_API_KEY:
        try:
            extracted = extract_incident_fields_openai(transcript)
            if extracted:
                extracted["extraction_method"] = "openai"
                logger.info("Extraction via OpenAI successful")
                return extracted
        except Exception as e:
            logger.warning(f"OpenAI extraction failed, trying next method: {str(e)}")
    
    # Priority 2: Try LLM extraction if enabled and API key exists
    if USE_LLM_EXTRACTION and GEMINI_API_KEY:
        try:
            extracted = extract_incident_fields_llm(transcript)
            if extracted:
                extracted["extraction_method"] = "llm"
                logger.info("Extraction via Gemini LLM successful")
                return extracted
        except Exception as e:
            logger.warning(f"LLM extraction failed, falling back to rule-based: {str(e)}")
    
    # Priority 3: Fallback to rule-based extraction
    extracted = extract_incident_fields(transcript)
    extracted["extraction_method"] = extraction_method
    logger.info("Extraction via rule-based fallback")
    return extracted


def resolve_location_with_geocoding(extracted: dict) -> dict:
    """
    Resolve location from extracted fields using multiple strategies:
    1. Local known landmarks/roads
    2. Geocoding with location_query if available
    3. Fallback to Unknown Location
    
    Args:
        extracted: Dictionary with extracted incident fields
        
    Returns:
        Dictionary with resolved location including lat/lng
    """
    landmark = extracted.get("landmark")
    road_name = extracted.get("road_name")
    location_query = extracted.get("location_query")
    city = extracted.get("city")
    state = extracted.get("state")
    country = extracted.get("country")
    
    # Strategy 1: Try local known landmarks/roads
    location = resolve_location(extracted)
    
    # If we got a known landmark with coordinates, return it
    if location.get("latitude") and location.get("longitude"):
        logger.info(f"Location resolved via local DB: {location.get('location_name')}")
        return location
    
    # Strategy 2: Try geocoding if we have location_query or road_name
    query_to_geocode = location_query or road_name or landmark
    
    if query_to_geocode:
        try:
            geocoded = geocode_location(query_to_geocode, city=city, state=state, country=country)
            
            # If geocoding found coordinates, use it
            if geocoded.get("latitude") and geocoded.get("longitude"):
                logger.info(f"Location geocoded: {geocoded.get('location_name')} ({geocoded.get('latitude')}, {geocoded.get('longitude')})")
                return geocoded
            
            # If geocoding at least found location name (even without coords), use it
            if geocoded.get("location_name") and geocoded.get("location_name") != "Unknown Location":
                logger.info(f"Location identified via geocoder: {geocoded.get('location_name')}")
                return geocoded
        except Exception as e:
            logger.warning(f"Geocoding failed, keeping local resolution: {str(e)}")
    
    # Strategy 3: Return what we have from local resolution (may have road_name without coords)
    logger.info(f"Location resolution final: {location.get('location_name')}")
    return location

def transcribe_streaming_audio(file_path: str) -> str:
    try:
        return transcribe_audio_file(file_path)
    except Exception as e:
        logger.warning(f"Streaming transcription failed: {e}")
        return ""
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
    normalized = (
        normalized
        .replace("__CONGESTION__", "congestion")
        .replace("__ACCIDENT__", "accident")
        .replace("__ROAD_BLOCK__", "road block")
        .replace("__NAMAKKAL__", "Namakkal")
    )
    return normalized.strip()
def get_v2_expected_field(current_incident: dict) -> Optional[str]:
    if not current_incident.get("event_type"):
        return "event_type"
    if not current_incident.get("location_name") and not current_incident.get("road_name"):
        return "location"
    if not current_incident.get("traffic_condition"):
        return "traffic_condition"
    if not current_incident.get("severity"):
        return "severity"
    return None
def update_v2_current_incident(current_incident: dict, transcript: str, expected_field: Optional[str]) -> None:
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
    is_severity_answer = expected_field == "severity" or any(
        phrase in text
        for phrase in ["high", "serious", "major", "emergency", "critical", "medium", "moderate", "low", "minor", "small"]
    )
    if is_severity_answer and any(phrase in text for phrase in ["high", "serious", "major", "emergency", "critical"]):
        current_incident["severity"] = "high"
    elif is_severity_answer and any(phrase in text for phrase in ["medium", "moderate"]):
        current_incident["severity"] = "medium"
    elif is_severity_answer and any(phrase in text for phrase in ["low", "minor", "small"]):
        current_incident["severity"] = "low"
def parse_v2_severity(transcript: str) -> Optional[str]:
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
def get_v2_default_severity(current_incident: dict) -> str:
    if current_incident.get("event_type") == "road_block" and current_incident.get("traffic_condition") == "blocked":
        return "high"
    if current_incident.get("event_type") == "congestion":
        return "medium"
    return "medium"
def get_v2_next_question(current_incident: dict) -> tuple[bool, Optional[str]]:
    if not current_incident.get("event_type"):
        return False, "What happened exactly? Was it an accident, breakdown, congestion, road block, fire, or medical emergency?"
    if not current_incident.get("location_name") and not current_incident.get("road_name"):
        return False, "Where is the incident happening?"
    if not current_incident.get("traffic_condition"):
        return False, "Is traffic blocked, slow moving, or normal?"
    if not current_incident.get("severity"):
        return False, "How severe is it? Please say low, medium, or high."
    return True, None
@app.websocket("/ws/voice-call")
async def voice_call_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("websocket connected")
    ai_speaking = False
    
    session = start_voice_session()
    severity_retry_count = 0
    completion_message = "Thank you. Incident details are complete. The incident has been created and sent to the control room."
    
    await websocket.send_json({
        "type": "ai_question",
        "text": "Please describe the traffic incident.",
    })
    
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                logger.info("voice websocket disconnected")
                break
                
            if "text" in message and message["text"] is not None:
                try:
                    payload = json.loads(message["text"])
                    logger.info(f"voice websocket text JSON: {payload}")
                    if payload.get("type") == "ai_speaking":
                        ai_speaking = bool(payload.get("value"))
                except json.JSONDecodeError:
                    logger.info(f"voice websocket text: {message['text']}")
                    
            if "bytes" in message and message["bytes"] is not None:
                if ai_speaking:
                    continue
                segment_audio = message["bytes"]
                byte_count = len(segment_audio)
                logger.info(f"received complete segment: {byte_count} bytes")
                temp_path = None
                
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
                        temp_file.write(segment_audio)
                        temp_path = temp_file.name
                        
                    logger.info(f"saved temp segment path: {temp_path}")
                    await websocket.send_json({
                        "type": "audio_segment_ready",
                        "message": "User audio segment captured",
                        "bytes": byte_count,
                    })
                    
                    transcript_raw = transcribe(temp_path)
                    normalized_transcript = normalize_streaming_transcript(transcript_raw)
                    print("RAW STREAMING TRANSCRIPT:", transcript_raw)
                    print("NORMALIZED STREAMING TRANSCRIPT:", normalized_transcript)
                    
                    current_inc = session.state.current_incident
                    expected_field = get_streaming_expected_field(current_inc)
                    print("EXPECTED FIELD:", expected_field)
                    
                    transcript_text = normalized_transcript if normalized_transcript else "No clear speech detected. Please speak after the beep."
                    
                    if expected_field == "severity":
                        severity = parse_streaming_severity(normalized_transcript)
                        if severity:
                            current_inc["severity"] = severity
                            normalized_transcript = severity
                            transcript_text = severity
                        else:
                            severity_retry_count += 1
                            transcript_text = "No clear severity detected. Please say low, medium, or high."
                            if severity_retry_count >= 2:
                                default_severity = get_streaming_default_severity(current_inc)
                                current_inc["severity"] = default_severity
                                transcript_text = f"Severity unclear. Marked as {default_severity}."
                                completion_message = f"Severity was unclear, so I marked it as {default_severity}. Thank you. Incident details are complete. The incident has been created and sent to the control room."
                                
                    print("SEVERITY RETRY COUNT:", severity_retry_count)
                    await websocket.send_json({
                        "type": "transcript",
                        "text": transcript_text,
                    })
                    
                    if normalized_transcript and expected_field != "severity":
                        update_streaming_current_incident(current_inc, normalized_transcript, expected_field)
                        
                    complete, next_question = get_streaming_next_question(current_inc)
                    print("V2 CURRENT INCIDENT:", current_inc)
                    print("V2 NEXT QUESTION:", next_question)
                    print("V2 COMPLETE:", complete)
                    
                    await websocket.send_json({
                        "type": "current_incident",
                        "incident": current_inc,
                    })
                    
                    if complete:
                        final_res = session.finalize()
                        await websocket.send_json({
                            "type": "complete",
                            "message": completion_message,
                            "incident": final_res["incident"],
                        })
                    else:
                        await websocket.send_json({
                            "type": "ai_question",
                            "text": next_question,
                        })
                finally:
                    if temp_path and os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception as e:
                            logger.warning(f"Failed to remove temp streaming segment {temp_path}: {e}")
    except WebSocketDisconnect:
        logger.info("voice websocket disconnected")


@app.get("/")
def root():
    return {"message": "SentinelAI Incident Copilot Backend Running"}


@app.post("/report-incident")
def report_incident(request: IncidentRequest):
    transcript = request.transcript.strip()
    extracted = process_incident_pipeline(transcript)
    location = resolve_location_with_geocoding(extracted)
    severity = assess_severity(transcript, extracted)
    incident = generate_incident_object(transcript, extracted, severity, location)

    # Attempt to dispatch to other modules; do not let dispatch failures break incident creation
    module_dispatch = None
    try:
        module_dispatch = dispatch_incident_to_modules(incident)
    except Exception as e:
        logger.warning(f"Module dispatch failed: {e}")

    response = {
        "success": True,
        "extraction_method": extracted.get("extraction_method"),
        "transcript": transcript,
        "extracted": extracted,
        "incident": incident,
    }

    if module_dispatch is not None:
        response["module_dispatch"] = module_dispatch

    return response


@app.post("/incident-summary")
def incident_summary(request: IncidentSummaryRequest):
    incident = request.incident
    summary = generate_incident_summary(incident)
    return {"success": True, "summary": summary}


@app.post("/dispatch-incident")
def dispatch_incident(request: DispatchIncidentRequest):
    """Dispatch a prepared incident to downstream SentinelAI modules (or webhooks)."""
    incident = request.incident
    try:
        module_dispatch = dispatch_incident_to_modules(incident)
        return {"success": True, "module_dispatch": module_dispatch}
    except Exception as e:
        # Do not fail; return error status per module
        import logging
        logging.warning(f"Dispatch endpoint error: {e}")
        return {"success": False, "error": str(e)}


@app.post("/incident-chat")
def incident_chat(request: IncidentChatRequest):
    """Answer natural language questions about a prepared incident."""
    answer_payload = answer_incident_question(request.question, request.incident)
    return {"success": True, "answer": answer_payload["answer"], "source": answer_payload["source"]}


@app.post("/extract-location")
def extract_location(request: LocationExtractRequest):
    text = request.text.strip()
    extracted = extract_incident_fields(text)
    location = resolve_location_with_geocoding(extracted)

    return {
        "success": True,
        "input_text": text,
        "extracted_location": {
            "landmark": extracted.get("landmark"),
            "road_name": extracted.get("road_name"),
            "location_query": extracted.get("location_query"),
        },
        "resolved_location": location,
    }


@app.post("/stt")
async def stt_endpoint(audio: UploadFile = File(...)):
    """
    Direct Speech-to-Text endpoint for transcriptions.
    """
    try:
        if not audio or not audio.filename:
            raise HTTPException(status_code=400, detail="No audio file provided")
            
        allowed_extensions = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".webm", ".mp4"}
        file_extension = os.path.splitext(audio.filename)[1].lower() or ".webm"
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format: {file_extension}. Allowed: {', '.join(allowed_extensions)}"
            )
            
        safe_filename = f"stt-{uuid.uuid4().hex}{file_extension}"
        temp_file_path = os.path.join(TEMP_UPLOADS_DIR, safe_filename)
        
        try:
            with open(temp_file_path, "wb") as buffer:
                contents = await audio.read()
                buffer.write(contents)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save upload: {str(e)}")
            
        try:
            transcript = transcribe(temp_file_path)
            return {"success": True, "transcript": transcript}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")
        finally:
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception:
                    pass
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.post("/voice-report")
def voice_report(request: VoiceReportRequest):
    transcript = request.transcript.strip()
    extracted = process_incident_pipeline(transcript)
    location = resolve_location_with_geocoding(extracted)
    severity = assess_severity(transcript, extracted)
    incident = generate_incident_object(transcript, extracted, severity, location)

    return {
        "success": True,
        "input_type": "voice_transcript",
        "extraction_method": extracted.get("extraction_method"),
        "transcript": transcript,
        "extracted": extracted,
        "incident": incident,
    }


@app.post("/voice-report-audio")
async def voice_report_audio(audio: UploadFile = File(...)):
    """
    Process voice report from audio file upload.
    Uses Faster-Whisper for speech-to-text transcription.
    """
    try:
        # Validate file is uploaded
        if not audio or not audio.filename:
            raise HTTPException(status_code=400, detail="No audio file provided")
        
        # Validate file format (accept common audio formats)
        allowed_extensions = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".webm", ".mp4"}
        file_extension = os.path.splitext(audio.filename)[1].lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format: {file_extension}. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Save uploaded file temporarily
        temp_file_path = os.path.join(TEMP_UPLOADS_DIR, audio.filename)
        try:
            with open(temp_file_path, "wb") as buffer:
                contents = await audio.read()
                buffer.write(contents)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save upload: {str(e)}")
        
        # Transcribe audio file
        try:
            transcript = transcribe_audio_file(temp_file_path)
        except Exception as e:
            # Clean up temp file on transcription error
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")
        
        # Process transcript through incident pipeline
        try:
            extracted = process_incident_pipeline(transcript)
            location = resolve_location_with_geocoding(extracted)
            severity = assess_severity(transcript, extracted)
            incident = generate_incident_object(transcript, extracted, severity, location)
        except Exception as e:
            # Clean up temp file on processing error
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"Failed to process incident: {str(e)}")

        # Attempt to dispatch to other modules; do not let dispatch failures break incident creation
        module_dispatch = None
        try:
            module_dispatch = dispatch_incident_to_modules(incident)
        except Exception as e:
            logger.warning(f"Module dispatch failed for voice incident: {e}")
        
        # Clean up temp file after successful processing
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        except:
            pass  # Silently ignore cleanup errors
        
        response = {
            "success": True,
            "input_type": "audio_file",
            "extraction_method": extracted.get("extraction_method"),
            "transcript": transcript,
            "extracted": extracted,
            "incident": incident,
        }

        if module_dispatch is not None:
            response["module_dispatch"] = module_dispatch

        return response
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.post("/interactive-voice-turn")
def interactive_voice_turn(request: InteractiveVoiceSessionRequest):
    transcript = request.transcript.strip()
    result = process_interactive_voice_turn(transcript, request.current_incident)
    return {
        "success": True,
        "session_id": request.session_id,
        **result,
    }


@app.post("/interactive-voice-audio-turn")
async def interactive_voice_audio_turn(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    current_incident_json: Optional[str] = Form(None),
):
    """
    Process one phone-call style voice turn from browser-recorded audio.
    """
    temp_file_path = None

    try:
        if not audio or not audio.filename:
            raise HTTPException(status_code=400, detail="No audio file provided")

        allowed_extensions = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".webm", ".mp4"}
        file_extension = os.path.splitext(audio.filename)[1].lower() or ".webm"
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format: {file_extension}. Allowed: {', '.join(allowed_extensions)}"
            )

        current_incident = None
        if current_incident_json:
            try:
                current_incident = json.loads(current_incident_json)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="current_incident_json must be valid JSON")

        safe_filename = f"interactive-{uuid.uuid4().hex}{file_extension}"
        temp_file_path = os.path.join(TEMP_UPLOADS_DIR, safe_filename)
        try:
            with open(temp_file_path, "wb") as buffer:
                contents = await audio.read()
                buffer.write(contents)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save upload: {str(e)}")

        try:
            transcript = transcribe_audio_file(temp_file_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

        if not transcript or not transcript.strip():
            return {
                "success": True,
                "complete": False,
                "transcript": "",
                "next_question": "I could not hear that clearly. Please repeat the incident.",
                "current_incident": current_incident or {},
                "error": "empty_transcript",
            }

        try:
            result = process_interactive_voice_turn(transcript, current_incident)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process interactive voice turn: {str(e)}")

        return {
            "success": True,
            "session_id": session_id,
            "transcript": transcript,
            **result,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

# ── Flask sub-application (catch-all fallback) ────────────────────────────────
# FastAPI evaluates its own routes first (/, /report-incident, /stt,
# /ws/voice-call, etc.).  Any path that doesn't match a FastAPI route falls
# through to the Flask WSGI app which handles:
#   /auth/*  /incidents  /stations/*  /analytics/*  /dispatch
#   /predict  /historical-search  /health  /admin/*  /feedback/*  /risk/*
#
# Note on WebSockets: WSGIMiddleware only handles HTTP — FastAPI's native
# @app.websocket handlers run *before* the mount, so /ws/voice-call is safe.
#
# Note on CORS: Flask-CORS is intentionally NOT initialised inside
# create_app() when running in mounted mode — FastAPI's CORSMiddleware wraps
# the whole ASGI app (including the WSGI sub-mount) and handles all preflight
# OPTIONS requests and response headers globally.

try:
    from app import create_app as _create_flask_app
    _flask_app = _create_flask_app()
    app.mount("/", WSGIMiddleware(_flask_app))
    logger.info("[main] Flask sub-app mounted — unified backend active")
except Exception as _flask_init_err:
    logger.error(f"[main] Flask sub-app failed to mount: {_flask_init_err}")
