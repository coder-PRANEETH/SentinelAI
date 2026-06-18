"""Local landmark coordinate resolver for Bengaluru landmarks."""
from typing import Dict, Any


LANDMARK_COORDINATES: Dict[str, Dict[str, float]] = {
    "Peenya Metro Station": {"latitude": 13.0327, "longitude": 77.5196},
    "Orion Mall": {"latitude": 13.0110, "longitude": 77.5549},
    "Majestic Bus Station": {"latitude": 12.9767, "longitude": 77.5713},
    "Silk Board Junction": {"latitude": 12.9177, "longitude": 77.6238},
    "Hebbal Flyover": {"latitude": 13.0358, "longitude": 77.5970},
    "KR Puram Railway Station": {"latitude": 13.0005, "longitude": 77.6754},
}


def resolve_location(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve location from extracted fields using local landmark DB.

    Returns a dict with location_name, latitude, longitude, source, confidence.
    """
    landmark = extracted.get("landmark")
    road_name = extracted.get("road_name")

    if landmark:
        # match case-insensitive against the local DB
        for name, coords in LANDMARK_COORDINATES.items():
            if name.lower() == landmark.lower():
                return {
                    "location_name": name,
                    "latitude": coords["latitude"],
                    "longitude": coords["longitude"],
                    "source": "local_landmark_db",
                    "confidence": 0.95,
                }

    if road_name:
        return {
            "location_name": road_name,
            "latitude": None,
            "longitude": None,
            "source": "road_name_only",
            "confidence": 0.5,
        }

    return {
        "location_name": "Unknown Location",
        "latitude": None,
        "longitude": None,
        "source": "unknown",
        "confidence": 0.0,
    }
