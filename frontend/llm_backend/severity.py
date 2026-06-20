"""Rule-based incident severity scoring."""

from __future__ import annotations

from typing import Any


def assess_severity(transcript: str, extracted: dict[str, Any]) -> dict[str, Any]:
    """Assess severity based on incident text and extracted fields."""
    score = 0
    reasons: list[str] = []
    text = (transcript or "").lower()

    vehicle_type = extracted.get("vehicle_type")
    if vehicle_type in ("heavy_vehicle", "bus", "truck"):
        score += 3
        reasons.append("involves heavy vehicle or bus")

    if any(k in text for k in ["blocked", "road block", "road blocked", "lane closed", "road closed"]):
        score += 3
        reasons.append("road or lane blocked")

    negative_phrases = ["no major traffic issue", "no traffic impact"]
    has_negative = any(p in text for p in negative_phrases)

    if not has_negative and any(
        k in text
        for k in [
            "traffic building",
            "traffic is building",
            "traffic",
            "congestion",
            "jam",
            "vehicles moving slowly",
            "moving slowly",
            "slow moving",
        ]
    ):
        score += 2
        reasons.append("traffic congestion building")

    if extracted.get("landmark"):
        score += 1
        reasons.append(f"near landmark: {extracted.get('landmark')}")

    if any(k in text for k in ["accident", "injury", "injured", "killed", "fire", "crash"]):
        score += 4
        reasons.append("accident or injury reported")

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

    score = max(score, 0)
    if score >= 6:
        severity = "high"
    elif 3 <= score <= 5:
        severity = "medium"
    else:
        severity = "low"

    confidence = min(0.95, 0.5 + 0.1 * len(reasons))
    return {
        "severity": severity,
        "confidence": round(confidence, 2),
        "severity_score": score,
        "severity_reasons": reasons,
    }
