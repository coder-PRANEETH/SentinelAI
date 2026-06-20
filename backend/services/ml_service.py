"""
services/ml_service.py
Central ML service — loads CatBoost models + FAISS index from trained_model/.
Wraps the logic already proven in final_endpoints/models.py, adapting it for
the Flask application factory pattern with graceful degradation.

All three CatBoost models are run in parallel via ThreadPoolExecutor.
FAISS + SentenceTransformer are lazy-loaded on first /historical-search call.
"""

import os
import sys
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Feature sets — must match training scripts exactly
# (duplicated here so this service is self-contained)
# ─────────────────────────────────────────────────────────────────────────────

RISK_FEATURES = [
    "event_type_grouped", "event_cause", "corridor", "police_station_grouped",
    "veh_type_grouped", "day_of_week", "latitude", "longitude",
    "location_cluster", "hour_of_day", "month", "is_peak_hour",
    "is_weekend", "is_cascaded", "cascade_size",
]

CLOSURE_FEATURES = [
    "event_type_grouped", "event_cause", "corridor", "police_station_grouped",
    "veh_type_grouped", "day_of_week", "priority", "latitude", "longitude",
    "location_cluster", "hour_of_day", "month", "is_peak_hour",
    "is_weekend", "is_cascaded", "cascade_size",
]

TIME_FEATURES = [
    "event_type_grouped", "event_cause", "corridor", "police_station_grouped",
    "veh_type_grouped", "day_of_week", "priority", "latitude", "longitude",
    "location_cluster", "hour_of_day", "month", "is_peak_hour",
    "is_weekend", "is_cascaded", "cascade_size",
]

DEFAULTS = {
    "event_type_grouped": "unknown",
    "event_cause": "unknown",
    "corridor": "unknown",
    "police_station_grouped": "unknown",
    "veh_type_grouped": "unknown",
    "day_of_week": "unknown",
    "priority": "unknown",
    "latitude": 0.0,
    "longitude": 0.0,
    "location_cluster": -1,
    "hour_of_day": 12,
    "month": 1,
    "is_peak_hour": 0,
    "is_weekend": 0,
    "is_cascaded": 0,
    "cascade_size": 1,
}

PEAK_HOURS = {8, 9, 10, 17, 18, 19, 20}

HEAVY_VEHICLE_KEYWORDS = {"heavy", "truck", "bus", "lorry", "tanker", "trailer"}

RESOURCE_PACKAGES = {
    # (incident_type_key, priority) -> resources
    ("vehicle_breakdown_heavy", "P1"): {"officers": 4, "vehicles": 2, "tow_trucks": 1, "barricades": 2},
    ("vehicle_breakdown_light", "P2"): {"officers": 2, "vehicles": 1, "tow_trucks": 1, "barricades": 0},
    ("road_blockage", "P1"):           {"officers": 4, "vehicles": 2, "tow_trucks": 0, "barricades": 4},
    ("fallen_tree", "P2"):             {"officers": 3, "vehicles": 1, "tow_trucks": 0, "barricades": 2},
    ("traffic_disruption", "P2"):      {"officers": 3, "vehicles": 2, "tow_trucks": 0, "barricades": 2},
    ("road_closure", "P1"):            {"officers": 5, "vehicles": 3, "tow_trucks": 0, "barricades": 6},
}

DEFAULT_PACKAGE = {"officers": 2, "vehicles": 1, "tow_trucks": 0, "barricades": 2}

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
FEATURE_COLS = ["event_cause", "corridor", "junction", "priority", "veh_type", "police_station"]


class MLService:
    """
    Loads CatBoost models and FAISS index at Flask app startup.
    Never crashes the app — missing models → 503 from individual endpoints.
    """

    def __init__(self):
        self.priority_model = None
        self.resolution_model = None
        self.closure_model = None
        self.model_version = "unknown"

        # Lazy-loaded
        self._faiss_index = None
        self._encoder = None
        self._hist_df: Optional[pd.DataFrame] = None
        self._hist_loaded = False

    # ─────────────────────────────────────────────────────────────────────────
    # MODEL LOADING
    # ─────────────────────────────────────────────────────────────────────────

    def load_models(self, model_dir: str, faiss_index_path: str):
        """
        Scan model_dir for .cbm files by prefix.
        Load whatever is found; log warnings for missing models.
        Does NOT raise exceptions.
        """
        try:
            from catboost import CatBoostClassifier, CatBoostRegressor
        except ImportError:
            logger.error("catboost package not installed — ML endpoints will return 503")
            return

        files = []
        if os.path.isdir(model_dir):
            files = os.listdir(model_dir)

        # Priority model
        priority_file = self._find_model(files, ["priority_catboost_model.cbm", "priority"], model_dir)
        if priority_file:
            try:
                m = CatBoostClassifier()
                m.load_model(priority_file)
                self.priority_model = m
                logger.info(f"[MLService] Priority model loaded: {priority_file}")
            except Exception as e:
                logger.warning(f"[MLService] Priority model load failed: {e}")

        # Resolution model
        resolution_file = self._find_model(files, ["resolution_time_model.cbm", "resolution"], model_dir)
        if resolution_file:
            try:
                m = CatBoostRegressor()
                m.load_model(resolution_file)
                self.resolution_model = m
                logger.info(f"[MLService] Resolution model loaded: {resolution_file}")
            except Exception as e:
                logger.warning(f"[MLService] Resolution model load failed: {e}")

        # Closure model
        closure_file = self._find_model(files, ["road_closure_catboost_model.cbm", "closure"], model_dir)
        if closure_file:
            try:
                m = CatBoostClassifier()
                m.load_model(closure_file)
                self.closure_model = m
                logger.info(f"[MLService] Closure model loaded: {closure_file}")
            except Exception as e:
                logger.warning(f"[MLService] Closure model load failed: {e}")

        self.model_version = "1.0.0"
        self._faiss_index_path = faiss_index_path
        logger.info("[MLService] Model loading complete")

    def _find_model(self, files, candidates, model_dir) -> Optional[str]:
        """Return path to the first matching candidate file."""
        for candidate in candidates:
            full = os.path.join(model_dir, candidate)
            if os.path.isfile(full):
                return full
            # Fuzzy match — any file containing the keyword
            keyword = candidate.replace(".cbm", "").split("_")[0]
            for f in files:
                if keyword in f.lower() and f.endswith(".cbm"):
                    return os.path.join(model_dir, f)
        return None

    def models_status(self) -> dict:
        return {
            "priority_model": "loaded" if self.priority_model else "missing",
            "resolution_model": "loaded" if self.resolution_model else "missing",
            "closure_model": "loaded" if self.closure_model else "missing",
            "faiss_index": "loaded" if self._faiss_index else "missing",
            "sentence_transformer": "loaded" if self._encoder else "missing",
        }

    def catboost_ready(self) -> bool:
        return all([self.priority_model, self.resolution_model, self.closure_model])

    # ─────────────────────────────────────────────────────────────────────────
    # PREDICTION
    # ─────────────────────────────────────────────────────────────────────────

    def predict(self, incident_data: dict) -> dict:
        """
        Run all three CatBoost models in parallel.
        Returns combined prediction dict.
        Raises RuntimeError if models not loaded.
        """
        if not self.catboost_ready():
            raise RuntimeError("One or more CatBoost models not loaded")

        def _predict_priority():
            X = self._build_df(incident_data, RISK_FEATURES)
            pred = self.priority_model.predict(X)
            prob = float(self.priority_model.predict_proba(X)[0][1])
            raw_class = int(pred[0])
            # Map to P1-P4 (model was trained on high/low binary, map to P1/P2)
            priority = "P1" if raw_class == 1 else "P2"
            return priority, prob

        def _predict_closure(priority_label):
            payload = dict(incident_data)
            payload["priority"] = priority_label.lower().replace("P", "")
            X = self._build_df(payload, CLOSURE_FEATURES)
            prob = float(self.closure_model.predict_proba(X)[0][1])
            return prob

        def _predict_resolution(priority_label):
            payload = dict(incident_data)
            payload["priority"] = priority_label.lower().replace("P", "")
            X = self._build_df(payload, TIME_FEATURES)
            log_time = float(self.resolution_model.predict(X)[0])
            minutes = float(np.expm1(log_time))
            return minutes

        # Run in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            f_priority = executor.submit(_predict_priority)
            # Wait for priority before launching dependent tasks
        
        priority, priority_prob = f_priority.result()

        with ThreadPoolExecutor(max_workers=2) as executor:
            f_closure = executor.submit(_predict_closure, priority)
            f_resolution = executor.submit(_predict_resolution, priority)
            closure_prob = f_closure.result()
            resolution_mins = f_resolution.result()

        # Road closure recommendation
        if closure_prob < 0.30:
            closure_rec = "No"
        elif closure_prob <= 0.60:
            closure_rec = "Monitor"
        else:
            closure_rec = "Yes"

        # Resolution range (±30%)
        low = max(0, int(resolution_mins * 0.7))
        high = int(resolution_mins * 1.3)

        # Explainability reasons
        priority_reasons = self._build_priority_reasons(incident_data, priority, priority_prob)
        closure_reasons = self._build_closure_reasons(incident_data, closure_prob, closure_rec)

        return {
            "predicted_priority": priority,
            "priority_confidence": round(priority_prob, 4),
            "predicted_resolution_minutes": int(resolution_mins),
            "resolution_range_low": low,
            "resolution_range_high": high,
            "road_closure_probability": round(closure_prob, 4),
            "road_closure_recommendation": closure_rec,
            "priority_reasons": priority_reasons,
            "closure_reasons": closure_reasons,
            "model_version": self.model_version,
        }

    def _build_df(self, payload: dict, features: list) -> pd.DataFrame:
        """Build a single-row DataFrame aligned with training features."""
        row = {f: payload.get(f, DEFAULTS.get(f)) for f in features}
        return pd.DataFrame([row])[features]

    def _build_priority_reasons(self, data: dict, priority: str, conf: float) -> list:
        reasons = []
        veh = str(data.get("veh_type_grouped", data.get("vehicle_type", ""))).lower()
        if any(k in veh for k in HEAVY_VEHICLE_KEYWORDS):
            reasons.append("Heavy vehicle involvement increases incident priority")

        corridor = data.get("corridor", "unknown")
        if corridor and corridor != "unknown":
            reasons.append(f"Corridor '{corridor}' has historically high incident frequency")

        hour = int(data.get("hour_of_day", 12))
        if hour in PEAK_HOURS:
            reasons.append(f"Hour {hour}:00 falls within peak traffic period (8–10am or 5–8pm)")

        event_type = data.get("event_type_grouped", data.get("incident_type", "unknown"))
        reasons.append(f"Incident type '{event_type}' has a {priority} baseline severity")

        if conf > 0.8:
            reasons.append(f"Model confidence {round(conf*100,1)}% — high certainty prediction")
        elif conf > 0.6:
            reasons.append(f"Model confidence {round(conf*100,1)}% — moderate certainty prediction")

        return reasons[:4]  # cap at 4

    def _build_closure_reasons(self, data: dict, prob: float, rec: str) -> list:
        reasons = []
        if prob > 0.5:
            reasons.append(f"Road closure probability {round(prob*100,1)}% exceeds 50% threshold")
        if data.get("is_cascaded", 0):
            reasons.append("Cascaded incident pattern detected — higher congestion risk")
        veh = str(data.get("veh_type_grouped", "")).lower()
        if any(k in veh for k in HEAVY_VEHICLE_KEYWORDS):
            reasons.append("Heavy vehicle may require full lane clearance")
        corridor = data.get("corridor", "unknown")
        if corridor and corridor != "unknown":
            reasons.append(f"Corridor '{corridor}' has a history of road closures")
        if not reasons:
            reasons.append(f"Road closure probability {round(prob*100,1)}% — recommendation: {rec}")
        return reasons[:3]

    # ─────────────────────────────────────────────────────────────────────────
    # HISTORICAL SEARCH (lazy-loaded)
    # ─────────────────────────────────────────────────────────────────────────

    def _ensure_historical_loaded(self, faiss_index_path: str, data_file: str):
        """Lazy-load FAISS index and sentence transformer on first call."""
        if self._hist_loaded:
            return

        try:
            import faiss
            from sentence_transformers import SentenceTransformer

            index_file = os.path.join(faiss_index_path, "incidents.index")
            pkl_file = os.path.join(faiss_index_path, "incidents.pkl")

            if not os.path.isfile(index_file):
                logger.warning(f"[MLService] FAISS index not found: {index_file}")
                self._hist_loaded = True
                return

            self._faiss_index = faiss.read_index(index_file)
            self._hist_df = pd.read_pickle(pkl_file)
            self._encoder = SentenceTransformer(EMBEDDING_MODEL_NAME)
            self._hist_loaded = True
            logger.info(f"[MLService] FAISS index loaded — {self._faiss_index.ntotal} vectors")

        except Exception as e:
            logger.error(f"[MLService] Historical load failed: {e}")
            self._hist_loaded = True  # Don't retry indefinitely

    def historical_search(
        self, query_text: str, top_k: int = 10, min_similarity: float = 0.7,
        faiss_index_path: str = None, data_file: str = None,
    ) -> dict:
        """
        Encode query_text, search FAISS index, filter by similarity threshold.
        Returns results + aggregate stats. Sets low_confidence_warning if < 3 results.
        """
        if faiss_index_path:
            self._ensure_historical_loaded(faiss_index_path, data_file)

        if not self._faiss_index or not self._encoder:
            raise RuntimeError("FAISS index or sentence transformer not loaded")

        q_vec = self._encoder.encode([query_text], normalize_embeddings=True).astype("float32")
        scores, indices = self._faiss_index.search(q_vec, min(top_k * 3, self._faiss_index.ntotal))

        # Filter by similarity threshold
        filtered = [
            (float(s), int(idx))
            for s, idx in zip(scores[0], indices[0])
            if float(s) >= min_similarity
        ][:top_k]

        low_confidence_warning = len(filtered) < 3

        if not filtered:
            return {
                "similar_cases": [],
                "total_similar": 0,
                "average_resolution_time": None,
                "historical_priority": None,
                "most_common_outcome": None,
                "low_confidence_warning": True,
            }

        matched = self._hist_df.iloc[[idx for _, idx in filtered]].copy()
        matched["similarity_score"] = [s for s, _ in filtered]

        avg_res = matched["resolution_mins"].dropna().median() if "resolution_mins" in matched.columns else None
        most_common_priority = matched["priority"].value_counts().index[0] if "priority" in matched.columns else "Unknown"
        most_common_outcome = (
            matched["event_cause"].value_counts().index[0].replace("_", " ").title()
            if "event_cause" in matched.columns else "Unknown"
        )

        cases = []
        for _, row in matched.iterrows():
            cases.append({
                "event_cause": str(row.get("event_cause", "")),
                "corridor": str(row.get("corridor", "")),
                "junction": str(row.get("junction", "")),
                "priority": str(row.get("priority", "")),
                "veh_type": str(row.get("veh_type", "")),
                "police_station": str(row.get("police_station", "")),
                "status": str(row.get("status", "")),
                "resolution_mins": (
                    round(float(row["resolution_mins"]), 1)
                    if pd.notna(row.get("resolution_mins")) else None
                ),
                "similarity_score": round(float(row["similarity_score"]), 4),
            })

        # Total similar in full index (above threshold)
        all_scores, _ = self._faiss_index.search(q_vec, min(len(self._hist_df), 5000))
        total_similar = int((all_scores[0] >= min_similarity).sum())

        return {
            "similar_cases": cases,
            "total_similar": total_similar,
            "average_resolution_time": round(float(avg_res), 1) if avg_res else None,
            "historical_priority": most_common_priority,
            "most_common_outcome": most_common_outcome,
            "low_confidence_warning": low_confidence_warning,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # RESOURCE RECOMMENDATION
    # ─────────────────────────────────────────────────────────────────────────

    def recommend_resources(
        self,
        incident_type: str,
        priority: str,
        vehicle_type: str,
        road_closure_probability: float,
        hour: int,
    ) -> dict:
        """
        Hybrid rule + historical resource recommendation table.
        Returns officers, vehicles, tow_trucks, barricades counts.
        """
        # Normalise keys
        inc_key = incident_type.lower().replace(" ", "_")
        veh = vehicle_type.lower() if vehicle_type else ""
        is_heavy = any(k in veh for k in HEAVY_VEHICLE_KEYWORDS)

        if is_heavy and "breakdown" in inc_key:
            package_key = ("vehicle_breakdown_heavy", "P1" if priority in ["P1"] else "P2")
        elif "breakdown" in inc_key:
            package_key = ("vehicle_breakdown_light", "P2")
        elif "blockage" in inc_key:
            package_key = ("road_blockage", "P1")
        elif "tree" in inc_key:
            package_key = ("fallen_tree", "P2")
        elif "disruption" in inc_key:
            package_key = ("traffic_disruption", "P2")
        elif "closure" in inc_key:
            package_key = ("road_closure", "P1")
        else:
            package_key = None

        resources = dict(RESOURCE_PACKAGES.get(package_key, DEFAULT_PACKAGE))

        # Adjustments
        if is_heavy:
            resources["tow_trucks"] = max(resources["tow_trucks"], 1)
        if road_closure_probability > 0.50:
            resources["barricades"] = max(resources["barricades"], 2)
        if hour in PEAK_HOURS:
            resources["officers"] += 1

        return resources


# Module-level singleton — loaded once at app startup
ml_service = MLService()
