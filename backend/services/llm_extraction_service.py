"""
LLM-based incident extraction using Google Gemini API.
Provides intelligent extraction of incident fields from transcripts.
"""

import json
import os
import logging
from typing import Optional
from datetime import datetime

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

# Initialize Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GENAI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Schema for LLM response
EXTRACTION_SCHEMA = {
    "event_type": "accident | vehicle_breakdown | congestion | road_block | illegal_parking | fire | medical_emergency | unknown",
    "event_cause": "string or null",
    "vehicle_type": "two_wheeler | car | bus | truck | heavy_vehicle | unknown",
    "landmark": "string or null",
    "junction": "string or null",
    "road_name": "string or null",
    "severity_indicators": "array of strings",
    "time_mentioned": "string or null",
    "additional_notes": "string or null",
}

EXTRACTION_PROMPT = """You are an expert incident traffic analysis AI. Extract structured incident information from the given transcript.

TRANSCRIPT: {transcript}

Return ONLY a valid JSON object (no markdown, no explanation, just JSON) with this schema:
{{
    "event_type": "accident | vehicle_breakdown | congestion | road_block | illegal_parking | fire | medical_emergency | unknown",
    "event_cause": "string or null (Attempt to infer from context if not explicit. e.g. tyre burst, engine failure, overheating)",
    "vehicle_type": "two_wheeler | car | bus | truck | heavy_vehicle | unknown",
    "landmark": "string or null (known landmark mentioned)",
    "junction": "string or null (junction mentioned)",
    "road_name": "string or null (road name mentioned)",
    "severity_indicators": ["array", "of", "indicators"],
    "time_mentioned": "string or null (any time reference)",
    "additional_notes": "string or null (any other relevant info)"
}}

Important:
1. Return ONLY valid JSON, no additional text.
2. Be accurate and extract what is actually mentioned.
3. If unsure, use "unknown" or null. Do not fabricate information.
4. Keep JSON compact and valid.
5. Corridor (road_name) and Location/Junction (landmark/junction) must not be identical; Location/Junction should be the more specific landmark, junction, or sub-location mentioned, not a repeat of the corridor name.
6. If event_cause is not explicitly labeled but can be inferred from context (e.g. "tyre burst", "engine failure"), extract it. Otherwise, leave it null."""


def extract_incident_fields_llm(transcript: str) -> Optional[dict]:
    """
    Extract incident fields using Google Gemini LLM.
    
    Args:
        transcript: Raw incident transcript
        
    Returns:
        Dictionary with extracted fields or None if extraction fails
        
    Raises:
        Exception: If Gemini API call fails
    """
    if not GENAI_AVAILABLE:
        logger.warning("google.generativeai not available, LLM extraction unavailable")
        return None
    
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not configured, LLM extraction unavailable")
        return None
    
    try:
        # Create prompt with transcript
        prompt = EXTRACTION_PROMPT.format(transcript=transcript)
        
        # Call Gemini API
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        
        if not response.text:
            logger.error("Empty response from Gemini API")
            return None
        
        # Parse JSON response
        json_text = response.text.strip()
        
        # Handle markdown code blocks if present
        if json_text.startswith("```"):
            json_text = json_text.split("```")[1]
            if json_text.startswith("json"):
                json_text = json_text[4:]
            json_text = json_text.strip()
        
        extracted = json.loads(json_text)
        
        # Validate required fields exist
        required_fields = ["event_type", "vehicle_type", "landmark", "road_name", "severity_indicators"]
        if not all(field in extracted for field in required_fields):
            logger.error(f"Response missing required fields. Got: {extracted.keys()}")
            return None
        
        # Ensure severity_indicators is a list
        if not isinstance(extracted.get("severity_indicators"), list):
            extracted["severity_indicators"] = []
        
        # Add normalized_text for consistency with rule-based extraction
        extracted["normalized_text"] = transcript.lower()
        
        logger.info(f"LLM extraction successful: {extracted.get('event_type')}")
        return extracted
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Gemini: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"LLM extraction failed: {str(e)}")
        return None
