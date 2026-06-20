"""Location resolution and geocoding."""

from __future__ import annotations

import os
from typing import Any, Optional

from .exceptions import ConfigurationError
from .logging_utils import get_logger, log_event
from .registry import get_model_registry

logger = get_logger(__name__)

DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Coimbatore")
DEFAULT_STATE = os.getenv("DEFAULT_STATE", "Tamil Nadu")
DEFAULT_COUNTRY = os.getenv("DEFAULT_COUNTRY", "India")

LANDMARK_COORDINATES: dict[str, dict[str, float]] = {
    "Peenya Metro Station": {"latitude": 13.0327, "longitude": 77.5196},
    "Orion Mall": {"latitude": 13.0110, "longitude": 77.5549},
    "Majestic Bus Station": {"latitude": 12.9767, "longitude": 77.5713},
    "Silk Board Junction": {"latitude": 12.9177, "longitude": 77.6238},
    "Hebbal Flyover": {"latitude": 13.0358, "longitude": 77.5970},
    "KR Puram Railway Station": {"latitude": 13.0005, "longitude": 77.6754},
}


def resolve_location(extracted: dict[str, Any]) -> dict[str, Any]:
    """Resolve extracted location fields against a small local landmark index."""
    landmark = extracted.get("landmark")
    road_name = extracted.get("road_name")

    if landmark:
        for name, coords in LANDMARK_COORDINATES.items():
            if name.lower() == str(landmark).lower():
                return {
                    "location_name": name,
                    "latitude": coords["latitude"],
                    "longitude": coords["longitude"],
                    "source": "local_landmark_db",
                    "confidence": 0.95,
                    "location_source": "local_landmark_db",
                    "location_confidence": 0.95,
                }

    if road_name:
        return _location_payload(str(road_name), None, None, "road_name_only", 0.5)

    return _location_payload("Unknown Location", None, None, "unknown", 0.0)


def resolve_location_with_geocoding(extracted: dict[str, Any]) -> dict[str, Any]:
    """Resolve location locally, then geocode a generic query if needed."""
    location = resolve_location(extracted)
    if location.get("latitude") and location.get("longitude"):
        return location

    query_to_geocode = (
        extracted.get("location_query")
        or extracted.get("road_name")
        or extracted.get("landmark")
        or extracted.get("location_name")
    )
    if not query_to_geocode:
        return location

    geocoded = geocode_location(
        str(query_to_geocode),
        city=extracted.get("city"),
        state=extracted.get("state"),
        country=extracted.get("country"),
    )
    if geocoded.get("latitude") and geocoded.get("longitude"):
        return geocoded
    if geocoded.get("location_name") and geocoded.get("location_name") != "Unknown Location":
        return geocoded
    return location


def geocode_location(
    location_query: str,
    city: Optional[str] = None,
    state: Optional[str] = None,
    country: Optional[str] = None,
    timeout: int = 10,
) -> dict[str, Any]:
    """Geocode a location query using the singleton geocoder."""
    if not location_query:
        return _location_payload("Unknown Location", None, None, "unresolved", 0.0)

    try:
        geocoder = get_model_registry().get_geocoder()
    except ConfigurationError as exc:
        log_event(logger, 30, "provider_unavailable", "Geocoder unavailable", error=str(exc))
        return _location_payload(location_query, None, None, "unresolved", 0.0)

    city = city or DEFAULT_CITY
    state = state or DEFAULT_STATE
    country = country or DEFAULT_COUNTRY
    query_parts = [location_query.strip(), city.strip(), state.strip(), country.strip()]
    full_query = ", ".join(part for part in query_parts if part)
    country_codes = "in" if country.strip().lower().startswith("india") else None

    try:
        geocode_kwargs: dict[str, Any] = {"timeout": timeout, "exactly_one": True, "addressdetails": True}
        if country_codes:
            geocode_kwargs["country_codes"] = country_codes

        log_event(logger, 20, "geocode_request", "Geocoding location", query=full_query)
        location = geocoder.geocode(full_query, **geocode_kwargs)
        if location and country_codes and not _matches_country(location, "in"):
            location = None

        if location:
            return _location_payload(
                location.address or location_query,
                round(float(location.latitude), 6),
                round(float(location.longitude), 6),
                "geocoder",
                0.75,
            )

        if _looks_like_road_only(location_query):
            return {
                **_location_payload(location_query, None, None, "known_road_only", 0.65),
                "corridor": location_query,
            }

        return _location_payload(location_query, None, None, "unresolved", 0.0)
    except Exception as exc:
        log_event(logger, 40, "geocode_failed", "Geocoding failed", query=full_query, error=str(exc))
        return _location_payload(location_query, None, None, "unresolved", 0.0)


def _location_payload(
    name: str,
    latitude: Optional[float],
    longitude: Optional[float],
    source: str,
    confidence: float,
) -> dict[str, Any]:
    return {
        "location_name": name,
        "corridor": None,
        "latitude": latitude,
        "longitude": longitude,
        "source": source,
        "confidence": confidence,
        "location_source": source,
        "location_confidence": confidence,
    }


def _matches_country(location: Any, expected_country_code: str) -> bool:
    raw = getattr(location, "raw", {}) or {}
    address = raw.get("address", {}) if isinstance(raw, dict) else {}
    country_code = str(address.get("country_code") or "").lower()
    country_name = str(address.get("country") or "").lower()
    address_str = str(getattr(location, "address", "") or "").lower()
    return (
        country_code == expected_country_code
        or "india" in country_name
        or "india" in address_str
    )


def _looks_like_road_only(query: str) -> bool:
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
        "square",
    ]
    q = (query or "").lower()
    return any(keyword in q for keyword in keywords)
