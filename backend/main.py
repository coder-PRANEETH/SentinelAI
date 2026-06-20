from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from models import IncidentRequest, InteractiveVoiceSessionRequest, IncidentSummaryRequest, LocationExtractRequest, VoiceReportRequest, DispatchIncidentRequest, IncidentChatRequest
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
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SentinelAI Incident Copilot Backend")

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
            transcript = transcribe_audio_file(temp_file_path)
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
