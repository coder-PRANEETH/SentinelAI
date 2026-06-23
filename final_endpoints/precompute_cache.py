import os
import sys
import pickle
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

# Ensure we can import from the directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import DATA_FILE, compute_station_loads, _load_and_clean, _build_text_repr
from safe_harbour import KerbSafeHarborIdentifier

def main():
    print("Starting precomputation...")
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Precompute Station Loads
    print("Precomputing station loads...")
    loads = compute_station_loads(DATA_FILE)
    with open(os.path.join(base_dir, "station_loads_cache.pkl"), "wb") as f:
        pickle.dump(loads, f)

    # 2. Precompute Safe Harbor Clusters
    print("Precomputing safe harbor clusters...")
    identifier = KerbSafeHarborIdentifier(DATA_FILE)
    identifier.initialize()
    with open(os.path.join(base_dir, "safe_harbor_cache.pkl"), "wb") as f:
        pickle.dump(identifier.harbors, f)

    # 3. Precompute Historical Search TF-IDF
    print("Precomputing historical search index...")
    df = _load_and_clean(DATA_FILE)
    corpus = df.apply(_build_text_repr, axis=1).tolist()
    
    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(corpus)
    
    historical_data = {
        "df": df,
        "vectorizer": vectorizer,
        "matrix": matrix
    }
    with open(os.path.join(base_dir, "historical_search_cache.pkl"), "wb") as f:
        pickle.dump(historical_data, f)

    print("Precomputation finished successfully.")

if __name__ == "__main__":
    main()
