# OpenAI-Powered Incident Extraction with Geocoding - Implementation Guide

## Overview
Replaced manual-only location entry with intelligent OpenAI-powered extraction plus geocoding fallback. The system now understands natural language incident reports with correct spelling, Indian traffic terminology, and automatic geocoding of locations.

## Architecture

### Extraction Pipeline (Priority Order)
1. **OpenAI Extraction** (if `USE_OPENAI_EXTRACTION=true` and `OPENAI_API_KEY` exists)
   - Understands natural language, typos, Indian terminology
   - Returns structured incident data with confidence scores
   - Returns JSON with all fields standardized

2. **Gemini LLM Extraction** (fallback, if `USE_LLM_EXTRACTION=true` and `GEMINI_API_KEY` exists)
   - Existing Gemini extraction service
   
3. **Rule-Based Extraction** (fallback)
   - Existing rule-based extraction with keyword matching
   - Enhanced with Indian traffic terms and improved congestion detection

### Location Resolution Pipeline
1. **Local Known Landmarks/Roads Database**
   - Pre-defined landmarks with coordinates (Peenya Metro, Silk Board Junction, etc.)
   - Pre-defined roads (Tumkur Road, Mysore Road, etc.)
   - Returns location if found in database

2. **Geocoding (geopy Nominatim)**
   - Geocodes `location_query`, `road_name`, or `landmark`
   - Uses context (city, state, country) for better results
   - Returns latitude/longitude if found
   - Falls back if no results

3. **Safe Fallback**
   - Returns `Unknown Location` without breaking pipeline
   - Response includes `location_source` and `location_confidence` for tracking

## Files Changed

### 1. requirements.txt
- ✅ Added: `openai` (OpenAI Python client)
- ✅ Added: `geopy` (Geocoding library using Nominatim)

### 2. .env.example
- ✅ Added: `OPENAI_API_KEY=your_openai_api_key_here`
- ✅ Added: `USE_OPENAI_EXTRACTION=true`
- ✅ Added: `DEFAULT_CITY=Coimbatore`
- ✅ Added: `DEFAULT_STATE=Tamil Nadu`
- ✅ Added: `DEFAULT_COUNTRY=India`

### 3. backend/services/openai_extraction_service.py (NEW)
```python
extract_incident_fields_openai(transcript: str) -> dict
```
- Uses OpenAI GPT-4o-mini with structured output
- Corrects spelling errors (neat → near)
- Understands Indian traffic terminology (lorry, tanker, jam, signal, etc.)
- Returns:
  ```json
  {
    "event_type": "accident|vehicle_breakdown|congestion|road_block|illegal_parking|fire|medical_emergency|unknown",
    "vehicle_type": "two_wheeler|car|bus|truck|heavy_vehicle|unknown",
    "landmark": "string or null",
    "junction": "string or null",
    "road_name": "string or null",
    "location_query": "string or null",
    "city": "string",
    "state": "string",
    "country": "string",
    "severity_indicators": ["array"],
    "normalized_text": "string",
    "confidence": 0.0-1.0
  }
  ```

### 4. backend/services/geocoding_service.py (NEW)
```python
geocode_location(
  location_query: str,
  city: str | None,
  state: str | None,
  country: str | None,
  timeout: int = 10
) -> dict
```
- Uses geopy Nominatim (OpenStreetMap data)
- Context-aware: appends city/state/country for better results
- Returns:
  ```json
  {
    "location_name": "string",
    "latitude": number or null,
    "longitude": number or null,
    "location_source": "geocoder|unresolved",
    "location_confidence": 0.75 or 0.0
  }
  ```

### 5. backend/main.py
- ✅ Added imports for new services
- ✅ Added configuration for OpenAI API key and extraction flags
- ✅ Updated `process_incident_pipeline()`:
  - New priority: OpenAI → Gemini LLM → Rule-based
  - Extraction method tracking: "openai", "llm", "rule_based_fallback"
- ✅ Added `resolve_location_with_geocoding()`:
  - Multi-strategy location resolution
  - Tracks location source and confidence
- ✅ Updated all endpoints to use new location resolution:
  - `/report-incident`
  - `/extract-location`
  - `/voice-report`
  - `/voice-report-audio`
- ✅ Kept existing APIs unchanged (backward compatible)

### 6. backend/services/extraction_service.py
- ✅ Added new landmarks: Hopes College Signal, Gandhipuram Signal, Avinashi Road Flyover
- ✅ Added new roads: Trichy Road, Avinashi Road
- ✅ Enhanced STT corrections: "neat"→"near", "lorry"→"truck", "jam"→"congestion"
- ✅ Improved congestion detection: standalone "traffic" + location context
- ✅ All changes backward compatible

## Test Results

### Rule-Based Extraction (Fallback)
```
✓ New: Traffic near Trichy Road (typo: 'neat')
  ✓ Trichy Road resolved via geocoding: (11.00556, 77.067621)
✓ New: Heavy traffic near Gandhipuram Signal
  ✓ Event type: congestion
✓ New: Lorry breakdown near Hopes College Signal
  ✓ Event type: vehicle_breakdown
  ✓ Vehicle type: heavy_vehicle
✓ New: Accident near Avinashi Road Flyover
  ✓ Avinashi Road resolved via geocoding: (11.007103, 76.977281)
✓ New: Bike accident near Silk Board Junction
  ✓ Landmark resolved locally: (12.9177, 77.6238)
✓ Old: Heavy truck breakdown near Peenya Metro Station on Tumkur Road
  ✓ All fields preserved and working
✓ Old: Bus breakdown near Hebbal Flyover
  ✓ All fields preserved and working
✓ Old: Car parked near Orion Mall
  ✓ All fields preserved and working

SUMMARY: 8/8 tests passing
```

## Backward Compatibility

✅ **All existing APIs unchanged**:
- `/report-incident` - response format same
- `/voice-report` - response format same
- `/voice-report-audio` - response format same
- `/extract-location` - response format same
- `/incident-summary` - unchanged
- `/dispatch-incident` - unchanged
- `/incident-chat` - unchanged

✅ **Extraction method tracking**:
- Old: `extraction_method` = "llm" or "rule_based_fallback"
- New: `extraction_method` = "openai", "llm", or "rule_based_fallback"
- Clients can check this field to know which method was used

✅ **Location response format unchanged**:
- Still returns `location_name`, `latitude`, `longitude`, `source`, `confidence`
- Now uses geocoding as fallback for better coordinate resolution

## Setup Instructions

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and update:
```bash
cp .env.example .env
```

Edit `.env`:
```
# Add your OpenAI API key (get from https://platform.openai.com/api-keys)
OPENAI_API_KEY=sk-proj-...

# Enable OpenAI extraction
USE_OPENAI_EXTRACTION=true

# Keep existing settings for fallback
USE_LLM_EXTRACTION=true
GEMINI_API_KEY=your_gemini_key
USE_LLM_CHAT=true
```

### 3. Run Tests
```bash
python test_new_extraction.py
```

### 4. Start Backend
```bash
python main.py
# or with uvicorn directly:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Usage Examples

### Example 1: Text Report with Typo
```bash
curl -X POST http://localhost:8000/report-incident \
  -H "Content-Type: application/json" \
  -d '{"transcript": "traffic neat trichy road"}'
```

**Response** (with OpenAI enabled):
```json
{
  "success": true,
  "extraction_method": "openai",
  "transcript": "traffic neat trichy road",
  "extracted": {
    "event_type": "congestion",
    "vehicle_type": "unknown",
    "road_name": "Trichy Road",
    "location_query": "traffic near Trichy Road",
    "city": "Coimbatore",
    "state": "Tamil Nadu",
    "country": "India",
    "normalized_text": "traffic near trichy road",
    "confidence": 0.92
  },
  "incident": {
    "incident_id": "...",
    "event_type": "congestion",
    "severity": "medium",
    "location": {
      "location_name": "Coimbatore-Trichy Road, Ondipudur, Sulur",
      "latitude": 11.00556,
      "longitude": 77.067621,
      "location_source": "geocoder",
      "location_confidence": 0.75
    }
  }
}
```

### Example 2: Voice Report (Existing Flow)
```bash
curl -X POST http://localhost:8000/voice-report-audio \
  -F "audio=@voice_recording.mp3"
```

**Response** (same format as text):
```json
{
  "success": true,
  "extraction_method": "openai",
  "transcript": "heavy traffic near gandhipuram signal",
  "extracted": { ... },
  "incident": { ... }
}
```

### Example 3: With Fallback (No OpenAI)
If `USE_OPENAI_EXTRACTION=false` or `OPENAI_API_KEY` not set:

```bash
curl -X POST http://localhost:8000/report-incident \
  -H "Content-Type: application/json" \
  -d '{"transcript": "accident near silk board junction"}'
```

**Response** (rule-based extraction):
```json
{
  "success": true,
  "extraction_method": "rule_based_fallback",  // or "llm" if Gemini enabled
  "extracted": {
    "event_type": "accident",
    "landmark": "Silk Board Junction",
    // ... rest of fields
  },
  "incident": {
    "location": {
      "location_name": "Silk Board Junction",
      "latitude": 12.9177,
      "longitude": 77.6238,
      "location_source": "local_landmark_db"
    }
  }
}
```

## Configuration Options

### Control Extraction Method
```python
# .env settings
USE_OPENAI_EXTRACTION=true       # Enable OpenAI (highest priority)
USE_LLM_EXTRACTION=true          # Enable Gemini (fallback)
# If both false: uses rule-based extraction

# Disable OpenAI but keep it installed (for cost savings):
USE_OPENAI_EXTRACTION=false
```

### Control Location Resolution
The system automatically handles location resolution based on what's available:
- **Local DB hit**: Returns known coordinates immediately
- **Unknown location**: Automatically tries geocoding
- **Geocoding timeout/error**: Safely returns `Unknown Location` without breaking
- **No query**: Returns `Unknown Location` if no road/landmark/location_query exists

## Performance Considerations

### Latency
- **OpenAI extraction**: ~1-2 seconds (network dependent)
- **Geocoding**: ~1-3 seconds (Nominatim shared service)
- **Rule-based**: <100ms (instant)
- **Local DB lookup**: <1ms

### Recommendations
1. **Production**: Use OpenAI for better understanding, but keep fallback enabled
2. **Cost control**: Set `USE_OPENAI_EXTRACTION=false` if needed, use rule-based fallback
3. **Offline use**: Rule-based extraction works without any API keys
4. **Batch processing**: Can process multiple incidents in parallel

## Troubleshooting

### OpenAI extraction not working
```
Error: "OpenAI client not initialized - API key missing"
```
- Check `OPENAI_API_KEY` in `.env`
- Verify key format: should start with `sk-proj-`
- Check API key has correct permissions

### Geocoding returning "Unknown Location"
- This is normal for very new roads or misspelled locations
- Rule-based extraction still works and returns `road_name`
- OpenAI extraction helps catch spelling errors

### Rate limiting
```
Error: "OpenAI rate limit exceeded"
```
- OpenAI API has rate limits based on tier
- System automatically falls back to rule-based extraction
- Check OpenAI console for usage stats

## Migration Guide for Frontend

The response format is **fully backward compatible**. No frontend changes required.

### Optional: Track extraction method
```javascript
// Frontend can now check how incident was extracted
if (response.extraction_method === "openai") {
  console.log("Used AI extraction - better understanding");
} else if (response.extraction_method === "llm") {
  console.log("Used Gemini extraction");
} else {
  console.log("Used rule-based extraction - fallback");
}
```

## Future Enhancements

1. **Multi-language support**: OpenAI can handle multiple Indian languages
2. **Custom extraction rules**: Add domain-specific extraction patterns
3. **Location caching**: Cache geocoding results for faster response
4. **Analytics**: Track which extraction method works best for your use case
5. **Custom model fine-tuning**: Fine-tune OpenAI models on your incident data

## Support

- **OpenAI API docs**: https://platform.openai.com/docs
- **geopy docs**: https://geopy.readthedocs.io/
- **Nominatim docs**: https://nominatim.org/
