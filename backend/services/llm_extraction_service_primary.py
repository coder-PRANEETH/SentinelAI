"""Primary LLM-powered incident field extraction with structured output."""
import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI, APIError, RateLimitError

logger = logging.getLogger(__name__)

# Initialize primary LLM client
LLM_PRIMARY_API_KEY = os.getenv("LLM_PRIMARY_API_KEY")
client = OpenAI(api_key=LLM_PRIMARY_API_KEY) if LLM_PRIMARY_API_KEY else None

# Default location for fallback
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Coimbatore")
DEFAULT_STATE = os.getenv("DEFAULT_STATE", "Tamil Nadu")
DEFAULT_COUNTRY = os.getenv("DEFAULT_COUNTRY", "India")


def extract_incident_fields_primary(transcript: str) -> Optional[Dict[str, Any]]:
    """
    Extract incident fields using OpenAI with structured output.
    
    Args:
        transcript: Natural language incident report
        
    Returns:
        Dictionary with structured incident fields or None if extraction fails
    """
    if not client:
        logger.warning("primary LLM client not initialized - API key missing")
        return None
    
    try:
        system_prompt = f"""You are an expert traffic incident analyzer for Indian roads. 
Your task is to extract structured incident information from natural language reports.

IMPORTANT RULES:
1. Correct common spelling errors (e.g., "neat" → "near", "lorry" → "lorry")
2. Understand Indian traffic terminology:
   - "lorry", "truck", "heavy vehicle" = commercial transport
   - "tanker" = special vehicle
   - "jam", "congestion", "heavy traffic" = traffic issues
   - "signal" = traffic signal/junction
   - "junction", "flyover", "road" = location markers
   - "bike", "two wheeler" = motorcycle/scooter
3. Classification rules:
   - If user mentions "traffic near/at X", classify event_type as "congestion"
   - If breakdown/stalled is mentioned, classify as "vehicle_breakdown"
   - If accident/crash/collision is mentioned, classify as "accident"
   - Only classify as accident/breakdown if explicitly mentioned - DO NOT hallucinate
4. Location extraction:
   - Extract landmark names, junction names, road names separately
   - If city/state/country not mentioned, use defaults
   - Create location_query from all location hints combined
5. Return ONLY valid JSON matching the exact schema below.
6. Corridor (road_name) and Location/Junction (landmark/junction) must not be identical; Location/Junction should be the more specific landmark, junction, or sub-location mentioned, not a repeat of the corridor name.
7. If event_cause is not explicitly labeled but can be inferred from context (e.g. "tyre burst", "engine failure"), extract it. Otherwise, leave it null.

DEFAULT LOCATION (if not mentioned in report):
- city: {DEFAULT_CITY}
- state: {DEFAULT_STATE}
- country: {DEFAULT_COUNTRY}

VALID EVENT TYPES:
- accident: collision, crash, impact
- vehicle_breakdown: breakdown, stalled, mechanical failure
- congestion: traffic jam, heavy traffic, slow-moving vehicles
- road_block: obstruction, blockage
- illegal_parking: parked vehicle, parking violation
- fire: fire, burning
- medical_emergency: medical, injury, health
- unknown: cannot determine

VALID VEHICLE TYPES:
- two_wheeler: bike, motorcycle, scooter
- car: sedan, hatchback, SUV
- bus: public transport bus
- truck: lorry, heavy vehicle, commercial truck
- heavy_vehicle: tanker, container truck
- unknown: cannot determine

Return JSON with these exact fields:
{{
  "event_type": "string (one of the valid types above)",
  "event_cause": "string or null (Attempt to infer from context if not explicit. e.g. tyre burst, engine failure, overheating)",
  "vehicle_type": "string (one of the valid types above)",
  "landmark": "string or null (specific building, station, mall)",
  "junction": "string or null (junction name if mentioned)",
  "road_name": "string or null (road or highway name)",
  "location_query": "string or null (combined location description for geocoding)",
  "city": "string (extracted or default city)",
  "state": "string (extracted or default state)",
  "country": "string (extracted or default country)",
  "severity_indicators": ["array of strings indicating severity cues"],
  "normalized_text": "string (cleaned up incident description)",
  "confidence": 0.0-1.0 (confidence score of extraction)
}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this incident report and extract structured fields:\n\n{transcript}"}
            ],
            temperature=0.1,  # Low temperature for consistent structured output
            max_tokens=500,
        )
        
        # Extract the response content
        response_text = response.choices[0].message.content.strip()
        
        # Try to parse JSON from response
        try:
            # Find JSON in response (in case there's extra text)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                extracted = json.loads(json_str)
                
                # Ensure required fields exist with safe defaults
                extracted.setdefault("event_type", "unknown")
                extracted.setdefault("event_cause", None)
                extracted.setdefault("vehicle_type", "unknown")
                extracted.setdefault("landmark", None)
                extracted.setdefault("junction", None)
                extracted.setdefault("road_name", None)
                extracted.setdefault("location_query", None)
                extracted.setdefault("city", DEFAULT_CITY)
                extracted.setdefault("state", DEFAULT_STATE)
                extracted.setdefault("country", DEFAULT_COUNTRY)
                extracted.setdefault("severity_indicators", [])
                extracted.setdefault("normalized_text", transcript)
                extracted.setdefault("confidence", 0.8)
                
                logger.info(f"Extraction via LLM (openai) successful: event_type={extracted.get('event_type')}")
                return extracted
            else:
                logger.error("No JSON found in primary LLM response")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse primary LLM JSON response: {e}\nResponse: {response_text}")
            return None
        
    except RateLimitError:
        logger.warning("primary LLM rate limit exceeded")
        return None
    except APIError as e:
        logger.error(f"primary LLM API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in OpenAI extraction: {e}")
        return None
