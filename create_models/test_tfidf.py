import os
import sys
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def test_tfidf():
    df = pd.read_csv('dataset_processed/astram_events_processed.csv')
    
    def prep_text(row):
        return f"{row.get('event_type_grouped','')} {row.get('event_cause','')} {row.get('corridor','')} {row.get('description','')} {row.get('zone','')}"

    df['search_text'] = df.apply(prep_text, axis=1).fillna('')
    vectorizer = TfidfVectorizer(stop_words='english', min_df=2)
    tfidf_matrix = vectorizer.fit_transform(df['search_text'])
    
    queries = [
        {"event_type_grouped": "planned", "event_cause": "rally", "corridor": "hosur road", "description": "huge political rally expected"},
        {"event_type_grouped": "planned", "event_cause": "vip_movement", "corridor": "orr east 1", "description": "CM convoy passing"},
        {"event_type_grouped": "accident", "event_cause": "accident", "corridor": "silk board", "description": "two wheeler collision"}
    ]
    
    for q in queries:
        print(f"\nQuery: {q['event_cause']} @ {q['corridor']}")
        q_text = prep_text(q)
        q_vec = vectorizer.transform([q_text])
        sims = cosine_similarity(q_vec, tfidf_matrix).flatten()
        
        # apply event_cause boosting (0.6 / 0.4)
        boosted_sims = []
        for i in range(len(df)):
            base_score = sims[i]
            if df.iloc[i]['event_cause'] == q['event_cause']:
                final_score = (base_score * 0.4) + 0.6
            else:
                final_score = base_score * 0.4
            boosted_sims.append(final_score)
            
        top_indices = np.argsort(boosted_sims)[-3:][::-1]
        for idx in top_indices:
            row = df.iloc[idx]
            print(f"  Score: {boosted_sims[idx]:.4f} | Cause: {row['event_cause']} | Corridor: {row['corridor']} | Desc: {row['description']}")

import numpy as np
test_tfidf()
