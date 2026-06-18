"""
embedding_pipeline.py
SentinelAI – Historical Incident Embedding Pipeline
Builds sentence-transformer embeddings + FAISS index from the Astram dataset.
"""

import os
import pickle
import numpy as np
import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer

# ── Config ──────────────────────────────────────────────────────────────────
DATA_FILE   = "Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"
INDEX_DIR   = "faiss_index"
MODEL_NAME  = "all-MiniLM-L6-v2"          # fast, 384-dim, good quality

FEATURE_COLS = [
    "event_cause", "corridor", "junction",
    "priority", "veh_type", "police_station",
]

# ── Helpers ──────────────────────────────────────────────────────────────────
def load_and_clean(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="latin1")

    # Parse datetimes
    df["start_dt"]    = pd.to_datetime(df["start_datetime"],   utc=True, errors="coerce")
    df["resolved_dt"] = pd.to_datetime(df["resolved_datetime"], utc=True, errors="coerce")

    # Resolution time in minutes
    df["resolution_mins"] = (
        (df["resolved_dt"] - df["start_dt"]).dt.total_seconds() / 60
    )

    # Day / hour features
    df["day"]  = df["start_dt"].dt.day_name()
    df["hour"] = df["start_dt"].dt.hour

    # Fill NaN in text cols
    for col in FEATURE_COLS:
        if col in df.columns:
            df[col] = df[col].fillna("unknown")

    return df


def build_text_repr(row: pd.Series) -> str:
    """Concatenate features into a single sentence for embedding."""
    parts = []
    for col in FEATURE_COLS:
        val = str(row.get(col, "unknown")).strip().lower().replace("_", " ")
        parts.append(val)
    if "day" in row:
        parts.append(str(row["day"]).lower())
    if "hour" in row:
        parts.append(f"hour {row['hour']}")
    return " | ".join(parts)


def build_embeddings(df: pd.DataFrame, model: SentenceTransformer) -> np.ndarray:
    texts = df.apply(build_text_repr, axis=1).tolist()
    print(f"[EmbeddingPipeline] Encoding {len(texts)} incidents …")
    embeddings = model.encode(texts, batch_size=256, show_progress_bar=True,
                              normalize_embeddings=True)
    return embeddings.astype("float32")


def build_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    dim   = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)   # Inner-product == cosine on L2-normalised vecs
    index.add(embeddings)
    print(f"[EmbeddingPipeline] FAISS index built – {index.ntotal} vectors, dim={dim}")
    return index


def save_artifacts(df, embeddings, index, out_dir=INDEX_DIR):
    os.makedirs(out_dir, exist_ok=True)
    faiss.write_index(index, os.path.join(out_dir, "incidents.index"))
    np.save(os.path.join(out_dir, "embeddings.npy"), embeddings)
    df.reset_index(drop=True).to_pickle(os.path.join(out_dir, "incidents.pkl"))
    print(f"[EmbeddingPipeline] Artifacts saved -> {out_dir}/")


def load_artifacts(out_dir=INDEX_DIR):
    index      = faiss.read_index(os.path.join(out_dir, "incidents.index"))
    embeddings = np.load(os.path.join(out_dir, "embeddings.npy"))
    df         = pd.read_pickle(os.path.join(out_dir, "incidents.pkl"))
    return df, embeddings, index


# ── Main ─────────────────────────────────────────────────────────────────────
def run_pipeline(data_file=DATA_FILE, out_dir=INDEX_DIR, force=False):
    if not force and os.path.exists(os.path.join(out_dir, "incidents.index")):
        print("[EmbeddingPipeline] Index already exists – skipping build.")
        return load_artifacts(out_dir)

    df    = load_and_clean(data_file)
    model = SentenceTransformer(MODEL_NAME)
    embs  = build_embeddings(df, model)
    index = build_faiss_index(embs)
    save_artifacts(df, embs, index, out_dir)
    return df, embs, index


if __name__ == "__main__":
    df, embs, idx = run_pipeline(force=True)
    print(f"Done. Dataset shape: {df.shape}")
