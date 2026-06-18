#!/usr/bin/env python3
"""
Test script for OpenAI-powered incident extraction with geocoding fallback.

This script tests the new extraction and location resolution pipeline.
Run with: python test_new_extraction.py
"""

import os
import sys
import json
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

# Load environment
from dotenv import load_dotenv
load_dotenv(backend_path / ".env")

from backend.services.extraction_service import extract_incident_fields
from backend.services.location_service import resolve_location
from backend.services.geocoding_service import geocode_location

# Try to import OpenAI service (may not have API key in test)
try:
    from backend.services.openai_extraction_service import extract_incident_fields_openai
    HAS_OPENAI = os.getenv("OPENAI_API_KEY") is not None
except ImportError:
    HAS_OPENAI = False
    print("⚠️  OpenAI service not available (missing dependencies or API key)")

print("\n" + "="*80)
print("INCIDENT EXTRACTION PIPELINE TEST")
print("="*80)

test_cases = [
    {
        "name": "New: Traffic near Trichy Road (typo: 'neat')",
        "input": "traffic neat trichy road",
        "expected": {
            "event_type": "congestion",
            "road_name": "Trichy Road",  # May be resolved by rule-based or OpenAI
        }
    },
    {
        "name": "New: Heavy traffic near Gandhipuram Signal",
        "input": "heavy traffic near gandhipuram signal",
        "expected": {
            "event_type": "congestion",
        }
    },
    {
        "name": "New: Lorry breakdown near Hopes College Signal",
        "input": "lorry breakdown near hopes college signal",
        "expected": {
            "event_type": "vehicle_breakdown",
            "vehicle_type": "heavy_vehicle",
        }
    },
    {
        "name": "New: Accident near Avinashi Road Flyover",
        "input": "accident near avinashi road flyover",
        "expected": {
            "event_type": "accident",
        }
    },
    {
        "name": "New: Bike accident near Silk Board Junction",
        "input": "bike accident near silk board junction",
        "expected": {
            "event_type": "accident",
            "vehicle_type": "two_wheeler",
            "landmark": "Silk Board Junction",
        }
    },
    {
        "name": "Old: Heavy truck breakdown near Peenya Metro Station on Tumkur Road",
        "input": "heavy truck breakdown near peenya metro station on tumkur road",
        "expected": {
            "event_type": "vehicle_breakdown",
            "vehicle_type": "heavy_vehicle",
            "landmark": "Peenya Metro Station",
            "road_name": "Tumkur Road",
        }
    },
    {
        "name": "Old: Bus breakdown near Hebbal Flyover",
        "input": "bus breakdown near hebbal flyover",
        "expected": {
            "event_type": "vehicle_breakdown",
            "vehicle_type": "bus",
            "landmark": "Hebbal Flyover",
        }
    },
    {
        "name": "Old: Car parked near Orion Mall",
        "input": "car parked near orion mall",
        "expected": {
            "event_type": "illegal_parking",
            "vehicle_type": "car",
            "landmark": "Orion Mall",
        }
    },
]

def check_field(extracted, field_name, expected_value):
    """Check if extracted field matches expected value."""
    actual = extracted.get(field_name)
    if expected_value is None:
        return True
    if actual is None:
        return False
    # Case-insensitive comparison for strings
    if isinstance(expected_value, str) and isinstance(actual, str):
        return expected_value.lower() in actual.lower() or actual.lower() in expected_value.lower()
    return actual == expected_value


def test_extraction(test_case):
    """Test rule-based extraction (fallback method)."""
    print(f"\n📝 Test: {test_case['name']}")
    print(f"   Input: '{test_case['input']}'")
    
    # Test rule-based extraction
    try:
        extracted = extract_incident_fields(test_case['input'])
        print(f"   ✓ Rule-based extraction: {extracted.get('event_type')} / {extracted.get('vehicle_type')}")
        
        # Check expected fields
        all_match = True
        for field, expected in test_case['expected'].items():
            match = check_field(extracted, field, expected)
            status = "✓" if match else "✗"
            print(f"     {status} {field}: {extracted.get(field)} (expected: {expected})")
            if not match:
                all_match = False
        
        return all_match, extracted
    except Exception as e:
        print(f"   ✗ Extraction failed: {e}")
        return False, None


def test_location_resolution(extracted, test_case_name):
    """Test location resolution with fallback."""
    if not extracted:
        return
    
    print(f"   Location resolution:")
    
    # Local resolution first
    location = resolve_location(extracted)
    print(f"     Local DB: {location.get('location_name')} ({location.get('latitude')}, {location.get('longitude')})")
    
    # Try geocoding if no coordinates
    if not location.get('latitude') and not location.get('longitude'):
        query = extracted.get('road_name') or extracted.get('landmark')
        if query:
            try:
                geocoded = geocode_location(query, city="Coimbatore", state="Tamil Nadu", country="India", timeout=5)
                print(f"     Geocoded: {geocoded.get('location_name')} ({geocoded.get('latitude')}, {geocoded.get('longitude')})")
            except Exception as e:
                print(f"     Geocoding error: {e}")


# Run tests
print("\n" + "="*80)
print("RULE-BASED EXTRACTION TESTS (Fallback Method)")
print("="*80)

passed = 0
failed = 0

for test_case in test_cases:
    all_match, extracted = test_extraction(test_case)
    if all_match:
        passed += 1
    else:
        failed += 1
    
    # Also test location resolution
    test_location_resolution(extracted, test_case['name'])

print("\n" + "="*80)
print(f"SUMMARY: {passed} passed, {failed} failed")
print("="*80)

# Test OpenAI extraction if available
if HAS_OPENAI:
    print("\n" + "="*80)
    print("OPENAI EXTRACTION TESTS (New Method)")
    print("="*80)
    
    openai_test_cases = test_cases[:5]  # Test first 5 with OpenAI
    
    for test_case in openai_test_cases:
        print(f"\n🤖 OpenAI Test: {test_case['name']}")
        print(f"   Input: '{test_case['input']}'")
        
        try:
            extracted = extract_incident_fields_openai(test_case['input'])
            if extracted:
                print(f"   ✓ OpenAI extraction: {extracted.get('event_type')} / {extracted.get('vehicle_type')}")
                print(f"     Confidence: {extracted.get('confidence')}")
                print(f"     Location query: {extracted.get('location_query')}")
                print(f"     Normalized: {extracted.get('normalized_text')}")
            else:
                print(f"   ✗ OpenAI extraction returned None")
        except Exception as e:
            print(f"   ✗ OpenAI extraction error: {e}")
else:
    print("\n" + "="*80)
    print("⚠️  OPENAI TESTS SKIPPED")
    print("Set OPENAI_API_KEY in .env to test OpenAI extraction")
    print("="*80)

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80 + "\n")
