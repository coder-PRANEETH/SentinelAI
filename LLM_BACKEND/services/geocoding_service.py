"""Location geocoding service using geopy Nominatim.

This module appends default city/state/country context to every query using
environment variables and restricts geocoding to India when DEFAULT_COUNTRY
is set to India. It also validates returned results and avoids returning
foreign-country locations when the defaults indicate India.
"""
import logging
import os
import re
from typing import Dict, Any, Optional
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

logger = logging.getLogger(__name__)

# Environment defaults
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Coimbatore")
DEFAULT_STATE = os.getenv("DEFAULT_STATE", "Tamil Nadu")
DEFAULT_COUNTRY = os.getenv("DEFAULT_COUNTRY", "India")

# Initialize Nominatim geocoder (uses OpenStreetMap data)
try:
    geocoder = Nominatim(user_agent="sentinelai_incident_copilot")
except Exception as e:
    logger.error(f"Failed to initialize Nominatim geocoder: {e}")
    geocoder = None


def _looks_like_road_only(query: str) -> bool:
    """Heuristic to detect road/road-like queries.

    Returns True for queries like 'Trichy Road', 'Avinashi Road Flyover',
    'Gandhipuram Signal', 'Peenya Metro Station on Tumkur Road', etc.
    """
    q = (query or "").lower()
    # common road/station/flyover/signal keywords
    keywords = [
        "road",
        "rd",
        "street",
        "st",
        "flyover",
        "signal",
        "junction",
        "station",
        "metro",
        "highway",
        "expressway",
        "avenue",
        "lane",
        "circle",
        "bridge",
        "flyover",
        "square",
    ]
    return any(k in q for k in keywords)


def geocode_location(
    location_query: str,
    city: Optional[str] = None,
    state: Optional[str] = None,
    country: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """
    Geocode a location query using Nominatim with default context and country
    restrictions.

    Behavior changes:
    - Always append DEFAULT_CITY, DEFAULT_STATE, DEFAULT_COUNTRY to the query
      (unless explicit city/state/country args are provided).
    - If DEFAULT_COUNTRY is India, restrict requests with `country_codes='in'`.
    - If the geocoder returns a result outside India, reject it and return
      an unresolved or road-only fallback.
    """
    if not geocoder or not location_query:
        return {
            "location_name": "Unknown Location",
            "corridor": None,
            "latitude": None,
            "longitude": None,
            "location_source": "unresolved",
            "location_confidence": 0.0,
        }

    # Use provided params or fall back to env defaults
    city = city or DEFAULT_CITY
    state = state or DEFAULT_STATE
    country = country or DEFAULT_COUNTRY

    # Build the full query with defaults
    query_parts = [location_query.strip(), city.strip(), state.strip(), country.strip()]
    full_query = ", ".join([p for p in query_parts if p])

    logger.info(f"Geocoding query: {full_query}")

    # Determine country_codes parameter for Nominatim (use 'in' for India)
    cc = None
    if (country or "").strip().lower().startswith("india"):
        cc = "in"

    try:
        # Attempt geocoding with country restriction when available
        geocode_kwargs = {"timeout": timeout, "exactly_one": True}
        if cc:
            geocode_kwargs["country_codes"] = cc

        location = geocoder.geocode(full_query, **geocode_kwargs)

        # If we got a result, validate it's in the expected country
        if location:
            country_code = ""
            country_name = ""
            try:
                addr = location.raw.get("address", {})
                country_code = (addr.get("country_code") or "").lower()
                country_name = (addr.get("country") or "").lower()
            except Exception:
                country_code = ""
                country_name = ""

            address_str = (location.address or "").lower()

            # Accept results that clearly indicate India even if country_code is missing
            if cc:
                is_india = country_code == "in" or "india" in country_name or "india" in address_str
                if not is_india:
                    logger.warning(
                        f"Geocoding returned result outside expected country for query '{full_query}': {location.address} ({country_code})"
                    )
                    location = None

        # If location found and validated
        if location:
            logger.info(f"Geocoding successful: {location.address} ({location.latitude}, {location.longitude})")
            return {
                "location_name": location.address or location_query,
                "corridor": None,
                "latitude": round(location.latitude, 6),
                "longitude": round(location.longitude, 6),
                "location_source": "geocoder",
                "location_confidence": 0.75,
            }

        # No valid geocoding result (either None or rejected due to country)
        # If the query looks like a known road/landmark, return a road-only
        # fallback instead of returning a foreign location.
        if _looks_like_road_only(location_query):
            logger.info(f"Returning road-only fallback for query: {location_query}")
            return {
                "location_name": location_query,
                "corridor": location_query,
                "latitude": None,
                "longitude": None,
                "location_source": "known_road_only",
                "location_confidence": 0.65,
            }

        # As a last resort, return unresolved preserving original query
        logger.warning(f"Geocoding returned no valid India result for: {full_query}")
        return {
            "location_name": location_query,
            "corridor": None,
            "latitude": None,
            "longitude": None,
            "location_source": "unresolved",
            "location_confidence": 0.0,
        }

    except GeocoderTimedOut:
        logger.warning(f"Geocoding timed out for: {location_query}")
        return {
            "location_name": location_query,
            "corridor": None,
            "latitude": None,
            "longitude": None,
            "location_source": "unresolved",
            "location_confidence": 0.0,
        }
    except GeocoderServiceError as e:
        logger.error(f"Geocoding service error: {e}")
        return {
            "location_name": location_query,
            "corridor": None,
            "latitude": None,
            "longitude": None,
            "location_source": "unresolved",
            "location_confidence": 0.0,
        }
    except Exception as e:
        logger.error(f"Unexpected error in geocoding: {e}")
        return {
            "location_name": location_query,
            "corridor": None,
            "latitude": None,
            "longitude": None,
            "location_source": "unresolved",
            "location_confidence": 0.0,
        }
