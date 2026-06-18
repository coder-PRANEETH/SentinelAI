KNOWN_LANDMARKS = [
    "Peenya Metro Station",
    "Orion Mall",
    "Majestic Bus Station",
    "Silk Board Junction",
    "Hebbal Flyover",
    "KR Puram Railway Station",
    "Hopes College Signal",
    "Gandhipuram Signal",
    "Avinashi Road Flyover",
]

KNOWN_ROADS = [
    "Tumkur Road",
    "Hosur Road",
    "Outer Ring Road",
    "Bellary Road",
    "Old Madras Road",
    "Mysore Road",
    "Trichy Road",
    "Avinashi Road",
]

# STT mistake mappings for normalization
STT_CORRECTIONS = {
    "break down": "breakdown",
    "pinyam metro station": "peenya metro station",
    "penya metro station": "peenya metro station",
    "peenya metro": "peenya metro station",
    "tumkhu road": "tumkur road",
    "tumkoor road": "tumkur road",
    "tumkur rod": "tumkur road",
    "neat": "near",
    "lorry": "truck",
    "jam": "congestion",
    "signal": "junction",
}


def normalize_transcript(text: str) -> str:
    """
    Normalize transcript by correcting common STT mistakes.
    
    Args:
        text: Raw transcript from speech-to-text
        
    Returns:
        Normalized transcript with corrections applied
    """
    text = text.lower()
    
    # Apply STT corrections
    for mistake, correction in STT_CORRECTIONS.items():
        text = text.replace(mistake, correction)
    
    return text


def extract_incident_fields(transcript: str) -> dict:
    text = normalize_transcript(transcript)

    event_type = "unknown"
    vehicle_type = "unknown"

    if any(word in text for word in ["accident", "crash", "collision"]):
        event_type = "accident"
    elif any(word in text for word in ["breakdown", "stalled"]):
        event_type = "vehicle_breakdown"
    elif any(word in text for word in ["blocked", "blocking", "road block", "lane block"]):
        event_type = "road_block"
    elif any(word in text for word in ["parked", "parking", "shoulder"]):
        event_type = "illegal_parking"
    elif (
        any(word in text for word in [
            "traffic building up",
            "heavy traffic",
            "congestion",
            "jam",
            "vehicles are moving slowly",
            "vehicles moving slowly"
        ])
        and "no major traffic issue" not in text
        and "no traffic impact" not in text
    ):
        event_type = "congestion"
    # Standalone "traffic" with location context is likely congestion
    elif (
        "traffic" in text
        and any(word in text for word in ["near", "at", "on", "road", "junction", "signal", "flyover"])
        and "no major traffic issue" not in text
        and "no traffic impact" not in text
    ):
        event_type = "congestion"

    if "truck" in text or "heavy vehicle" in text:
        vehicle_type = "heavy_vehicle"
    elif "bus" in text:
        vehicle_type = "bus"
    elif "car" in text:
        vehicle_type = "car"
    elif "bike" in text or "two wheeler" in text or "two-wheeler" in text:
        vehicle_type = "two_wheeler"

    landmark = None
    for item in KNOWN_LANDMARKS:
        if item.lower() in text:
            landmark = item
            break

    road_name = None
    for road in KNOWN_ROADS:
        if road.lower() in text:
            road_name = road
            break

    severity_indicators = []

    if event_type != "unknown":
        severity_indicators.append(event_type)

    if vehicle_type != "unknown":
        severity_indicators.append(vehicle_type)

    if landmark:
        severity_indicators.append("known_landmark")

    if road_name:
        severity_indicators.append("known_road")

    if any(word in text for word in ["blocked", "blocking", "road block", "lane block"]):
        severity_indicators.append("road_block")

    if (
        any(word in text for word in [
            "traffic building up",
            "heavy traffic",
            "congestion",
            "jam",
            "vehicles are moving slowly",
            "vehicles moving slowly"
        ])
        and "no major traffic issue" not in text
        and "no traffic impact" not in text
    ):
        severity_indicators.append("congestion")

    if "no major traffic issue" in text or "no traffic impact" in text:
        severity_indicators.append("low_traffic_impact")

    return {
        "event_type": event_type,
        "vehicle_type": vehicle_type,
        "landmark": landmark,
        "road_name": road_name,
        "severity_indicators": severity_indicators,
        "normalized_text": text,
    }
