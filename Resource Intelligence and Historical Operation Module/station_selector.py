"""
station_selector.py
SentinelAI – Station Selector (high-level interface)
Combines historical search + load balancer into one call.
This is the entry-point that the SentinelAI dispatch engine calls.
"""

import json
from load_balancer import LoadBalancer
from historical_search import search_similar_incidents

_lb: LoadBalancer = None


def get_balancer() -> LoadBalancer:
    global _lb
    if _lb is None:
        _lb = LoadBalancer()
    return _lb


def dispatch(
    incident_text: str,
    corridor: str = None,
    min_officers: int = 1,
    min_vehicles: int = 1,
    search_top_k: int = 20,
) -> dict:
    """
    Full dispatch pipeline:
      1. Historical search -> context
      2. Load balancer -> best station

    Returns a unified response dict.
    """
    lb = get_balancer()

    # Step 1 – Historical context
    history = search_similar_incidents(incident_text, top_k=search_top_k)

    # Step 2 – Station selection
    selection = lb.select_station(
        incident_location=incident_text,
        corridor=corridor,
        min_officers=min_officers,
        min_vehicles=min_vehicles,
    )

    return {
        "dispatch": {
            "incident":             incident_text,
            "recommended_station":  selection["recommended_station"],
            "readiness_score":      selection["readiness_score"],
            "reasons":              selection["reason"],
            "top_candidates":       selection["all_candidates"],
        },
        "historical_context": {
            "similar_cases":            history["total_similar"],
            "average_resolution_time":  history["average_resolution_time"],
            "historical_priority":      history["historical_priority"],
            "most_common_outcome":      history["most_common_outcome"],
        },
    }


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    incident = " ".join(sys.argv[1:]) if len(sys.argv) > 1 \
        else "Vehicle Breakdown Tumkur Road Heavy Vehicle"
    corridor = "Tumkur Road" if "Tumkur" in incident else None

    print(f"\n[StationSelector] Incident: '{incident}'")
    result = dispatch(incident, corridor=corridor, min_officers=2, min_vehicles=1)

    d = result["dispatch"]
    h = result["historical_context"]

    print(f"\n{'='*60}")
    print(f"  DISPATCH RECOMMENDATION")
    print(f"{'='*60}")
    print(f"  Station     : {d['recommended_station']}")
    print(f"  Readiness   : {d['readiness_score']}%")
    print(f"  Reasons     : {', '.join(d['reasons'])}")
    print(f"\n  HISTORICAL CONTEXT")
    print(f"  Similar Cases        : {h['similar_cases']}")
    print(f"  Avg Resolution Time  : {h['average_resolution_time']} mins")
    print(f"  Historical Priority  : {h['historical_priority']}")
    print(f"  Most Common Outcome  : {h['most_common_outcome']}")
    print(f"\n  Candidate Stations:")
    for c in d["top_candidates"]:
        bar = "#" * int(c["readiness_pct"] / 5)
        print(f"    {c['station']:<30} {bar:<20} {c['readiness_pct']:>5.1f}%")
    print()

    print("[Full JSON]")
    print(json.dumps(result, indent=2))
