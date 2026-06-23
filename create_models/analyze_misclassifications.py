import pandas as pd
import numpy as np

def main():
    # Load same test data
    import tune_v5
    df = pd.read_csv('dataset_processed/astram_events_processed.csv')
    valid_priorities = ['high', 'low']
    df = df[df['priority'].isin(valid_priorities)].copy()
    
    df = tune_v5.feature_engineering(df)
    
    cat_features = ['event_type_grouped', 'event_cause', 'requires_road_closure', 'veh_type_grouped', 'day_of_week', 'zone', 'cause_x_peak', 'cause_x_zone', 'veh_x_zone', 'authenticated']
    num_features = ['hour_of_day', 'month', 'is_peak_hour', 'is_weekend', 'zone_historical_risk']
    
    from sklearn.feature_extraction.text import TfidfVectorizer
    df['description'] = df['description'].fillna('').astype(str).str.lower()
    tfidf = TfidfVectorizer(max_features=30, stop_words='english')
    tfidf_mat = tfidf.fit_transform(df['description'])
    tfidf_cols = [f"tfidf_{i}" for i in range(30)]
    df_tfidf = pd.DataFrame(tfidf_mat.toarray(), columns=tfidf_cols, index=df.index)
    df = pd.concat([df, df_tfidf], axis=1)
    num_features += tfidf_cols
    
    features = cat_features + num_features
    for col in cat_features:
        df[col] = df[col].fillna('unknown').astype(str)
    for col in num_features:
        if df[col].isnull().any():
            df[col] = df[col].fillna(df[col].median())
            
    X = df[features]
    y = df['priority_target']
    
    from sklearn.model_selection import train_test_split
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)
    
    # Load final model
    from catboost import CatBoostClassifier
    model = CatBoostClassifier()
    model.load_model('../trained_model/priority_catboost_model.cbm')
    
    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:, 1]
    
    test_df = df.loc[X_test.index].copy()
    test_df['predicted'] = preds
    test_df['pred_prob'] = probs
    test_df['actual'] = y_test
    
    misclassified = test_df[test_df['actual'] != test_df['predicted']]
    
    # Print 10 random misclassifications
    sample = misclassified.sample(10, random_state=42)
    for _, row in sample.iterrows():
        print("="*60)
        print(f"ACTUAL: {'HIGH' if row['actual']==1 else 'LOW'} | PRED: {'HIGH' if row['predicted']==1 else 'LOW'} (Prob: {row['pred_prob']:.2f})")
        print(f"Cause: {row['event_cause']} | Vehicle: {row['veh_type']} | Zone: {row['zone']}")
        print(f"Desc: {row['description']}")
        print(f"Hour: {row['hour_of_day']} | Peak: {row['is_peak_hour']} | Historical Zone Risk: {row['zone_historical_risk']:.2f}")

if __name__ == '__main__':
    main()
