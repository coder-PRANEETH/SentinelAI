from typing import Dict, List


def assess_severity(transcript: str, extracted: Dict) -> Dict:
    """Assess severity based on rule-based scoring and return details."""
    score = 0
    reasons: List[str] = []
    text = transcript.lower()

    vehicle_type = extracted.get("vehicle_type")
    if vehicle_type in ("heavy_vehicle", "bus"):
        score += 3
        reasons.append("involves heavy vehicle or bus")

    # road or lane blocked
    if any(k in text for k in ["blocked", "road block", "road blocked", "lane closed", "road closed"]):
        score += 3
        reasons.append("road or lane blocked")

    # congestion
    negative_phrases = ["no major traffic issue", "no traffic impact"]
    has_negative = any(p in text for p in negative_phrases)

    if not has_negative and any(k in text for k in ["traffic building", "traffic is building", "traffic", "congestion", "jam", "vehicles moving slowly", "moving slowly", "slow moving"]):
        score += 2
        reasons.append("traffic congestion building")

    # known landmark
    if extracted.get("landmark"):
        score += 1
        reasons.append(f"near landmark: {extracted.get('landmark')}")

    # accident/injury/fire
    if any(k in text for k in ["accident", "injury", "injured", "killed", "fire", "crash"]):
        score += 4
        reasons.append("accident or injury reported")

    # Negative severity indicators reduce score
    # Apply explicit negative phrases
    if "no major traffic issue" in text:
        score -= 3
        reasons.append("report indicates no major traffic issue")
    if "no traffic impact" in text:
        score -= 3
        reasons.append("report indicates no traffic impact")
    if "parked on the shoulder" in text:
        score -= 2
        reasons.append("parked on the shoulder")
    elif "shoulder" in text:
        score -= 1
        reasons.append("shoulder mentioned")

    # Cap score non-negative
    if score < 0:
        score = 0

    # Severity label
    if score >= 6:
        severity = "high"
    elif 3 <= score <= 5:
        severity = "medium"
    else:
        severity = "low"

    # Confidence heuristic: base 0.5 + 0.1 per reason up to 0.95
    confidence = min(0.95, 0.5 + 0.1 * len(reasons))

    return {
        "severity": severity,
        "confidence": round(confidence, 2),
        "severity_score": score,
        "severity_reasons": reasons,
    }
