"""
historical_search.py
SentinelAI – Historical Incident Search
Given a free-text incident query, finds similar historical cases using FAISS + Sentence Transformers.
"""

import json
from typing import Optional
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from embedding_pipeline import run_pipeline, build_text_repr, MODEL_NAME, INDEX_DIR

# ── Loader ────────────────────────────────────────────────────────────────────
_df: Optional[pd.DataFrame]    = None
_index                          = None
_model: Optional[SentenceTransformer] = None


def _load(index_dir=INDEX_DIR):
    global _df, _index, _model
    if _df is None:
        _df, _, _index = run_pipeline(out_dir=index_dir)
        _model = SentenceTransformer(MODEL_NAME)


# ── Core search ───────────────────────────────────────────────────────────────
def search_similar_incidents(
    query: str,
    top_k: int = 20,
    index_dir: str = INDEX_DIR,
) -> dict:
    """
    Parameters
    ----------
    query   : Free-text description, e.g. 'Vehicle Breakdown Tumkur Road Heavy Vehicle'
    top_k   : Number of neighbours to retrieve

    Returns
    -------
    dict with keys: similar_cases, average_resolution_time, historical_priority,
                    most_common_outcome, total_similar
    """
    _load(index_dir)

    # Embed query (L2-normalised to match inner-product index)
    q_vec = _model.encode([query], normalize_embeddings=True).astype("float32")

    scores, indices = _index.search(q_vec, top_k)
    matched = _df.iloc[indices[0]].copy()
    matched["similarity_score"] = scores[0]

    # ── Aggregate stats ──────────────────────────────────────────────────────
    avg_res_time = (
        matched["resolution_mins"].dropna().median()
        if "resolution_mins" in matched.columns else None
    )

    priority_counts = matched["priority"].value_counts()
    most_common_priority = (
        priority_counts.index[0] if not priority_counts.empty else "Unknown"
    )

    # "outcome" proxied by event_cause (dominant event type in results)
    outcome_counts = matched["event_cause"].value_counts()
    most_common_outcome = (
        outcome_counts.index[0].replace("_", " ").title()
        if not outcome_counts.empty else "Unknown"
    )

    # Build per-case summaries (serialisable)
    cases = []
    for _, row in matched.iterrows():
        cases.append({
            "event_cause":       str(row.get("event_cause", "")),
            "corridor":          str(row.get("corridor", "")),
            "junction":          str(row.get("junction", "")),
            "priority":          str(row.get("priority", "")),
            "veh_type":          str(row.get("veh_type", "")),
            "police_station":    str(row.get("police_station", "")),
            "status":            str(row.get("status", "")),
            "resolution_mins":   (
                round(float(row["resolution_mins"]), 1)
                if pd.notna(row.get("resolution_mins")) else None
            ),
            "similarity_score":  round(float(row["similarity_score"]), 4),
        })

    # Count total similar in full dataset (cosine threshold 0.75)
    all_scores, _ = _index.search(q_vec, min(len(_df), 5000))
    total_similar = int((all_scores[0] >= 0.75).sum())

    result = {
        "similar_cases":          cases,
        "total_similar":          total_similar,
        "average_resolution_time": round(avg_res_time, 1) if avg_res_time else None,
        "historical_priority":    most_common_priority,
        "most_common_outcome":    most_common_outcome,
    }
    return result


# ── Pretty print ──────────────────────────────────────────────────────────────
def display_search_result(result: dict):
    print(f"\n{'='*55}")
    print(f"  Similar Cases Found : {result['total_similar']}")
    print(f"  Avg Resolution Time : {result['average_resolution_time']} mins")
    print(f"  Most Common Priority: {result['historical_priority']}")
    print(f"  Most Common Outcome : {result['most_common_outcome']}")
    print(f"{'='*55}")
    print(f"  Top {len(result['similar_cases'])} nearest cases:")
    for i, c in enumerate(result["similar_cases"][:5], 1):
        print(f"  {i}. [{c['similarity_score']:.2f}] {c['event_cause']} | "
              f"{c['corridor']} | {c['priority']} | {c['police_station']}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Vehicle Breakdown Tumkur Road Heavy Vehicle"
    print(f"[HistoricalSearch] Query: '{query}'")
    result = search_similar_incidents(query, top_k=20)
    display_search_result(result)
    print("[JSON Output]")
    print(json.dumps(result, indent=2))
