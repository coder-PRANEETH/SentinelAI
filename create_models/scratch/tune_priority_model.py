import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from catboost import CatBoostClassifier, Pool
def feature_engineering(df):
    df = df.copy()
    
    # Text keyword flags (from 'description' or 'incident_text' if available)
    # The processed dataset doesn't have a 'description' column by default, let's check what it has.
    # In theme2.csv it had 'incident_text', we mapped it to something? We'll check 'incident_text' or 'raw_transcript' 
    # Actually, let's just stick to the requested interaction features and basic keywords if they exist.
    
    # Interaction Features
    df['cause_x_peak'] = df['event_cause'].astype(str) + "_" + df['is_peak_hour'].astype(str)
    df['cause_x_zone'] = df['event_cause'].astype(str) + "_" + df['zone'].astype(str)
    df['veh_x_zone'] = df['veh_type_grouped'].astype(str) + "_" + df['zone'].astype(str)
    
    # Ensure start_datetime is datetime
    if 'start_datetime' in df.columns:
        df['start_datetime'] = pd.to_datetime(df['start_datetime'], errors='coerce')
        df = df.sort_values('start_datetime').reset_index(drop=True)
        df['priority_target'] = df['priority'].map({'high': 1, 'low': 0})
        df['zone_historical_risk'] = df.groupby('zone')['priority_target'].transform(
            lambda x: x.shift(1).expanding().mean()
        ).fillna(0.5)
    else:
        df['zone_historical_risk'] = 0.5
        
    return df

def main():
    print("Loading data...")
    df = pd.read_csv('dataset_processed/astram_events_processed.csv')
    df_raw = pd.read_csv('theme2.csv')
    # Merge description from raw data
    df = df.merge(df_raw[['id', 'description', 'authenticated', 'client_id', 'created_by_id']], on='id', how='left')
    
    valid_priorities = ['high', 'low']
    df = df[df['priority'].isin(valid_priorities)].copy()
    
    df = feature_engineering(df)
    
    cat_features = [
        'event_type_grouped',
        'event_cause',
        'requires_road_closure',
        'veh_type_grouped',
        'day_of_week',
        'zone',
        'cause_x_peak',
        'cause_x_zone',
        'veh_x_zone',
        'authenticated',
    ]

    num_features = [
        'hour_of_day',
        'month',
        'is_peak_hour',
        'is_weekend',
        'zone_historical_risk'
    ]
    
    # TF-IDF on description
    from sklearn.feature_extraction.text import TfidfVectorizer
    df['description'] = df['description'].fillna('').astype(str).str.lower()
    tfidf = TfidfVectorizer(max_features=50, stop_words='english')
    tfidf_mat = tfidf.fit_transform(df['description'])
    tfidf_cols = [f"tfidf_{i}" for i in range(50)]
    df_tfidf = pd.DataFrame(tfidf_mat.toarray(), columns=tfidf_cols, index=df.index)
    df = pd.concat([df, df_tfidf], axis=1)
    num_features += tfidf_cols
    
    features = cat_features + num_features
    
    for col in cat_features:
        df[col] = df[col].fillna('unknown').astype(str)
    for col in num_features:
        if df[col].isnull().any():
            df[col] = df[col].fillna(df[col].median())
            
    # We must maintain the EXACT SAME 20% test set as before.
    # The previous code was:
    # train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)
    
    X = df[features]
    y = df['priority_target']
    
    # Split 1: Train+Val (80%) vs Test (20%)
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)
    
    # Split 2: Train (80% of 80% = 64%) vs Val (20% of 80% = 16%)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.20, random_state=42, stratify=y_temp)
    
    print(f"Data Split: Train ({len(X_train)}), Val ({len(X_val)}), Test ({len(X_test)})")
    
    # Hyperparameter tuning with Randomized Search
    import random
    
    best_f1 = -1
    best_params = {}
    
    trials = [
        {'iterations': 500, 'learning_rate': 0.03, 'depth': 6, 'l2_leaf_reg': 3, 'auto_class_weights': 'Balanced'},
        {'iterations': 1000, 'learning_rate': 0.05, 'depth': 8, 'l2_leaf_reg': 5, 'auto_class_weights': 'Balanced'},
        {'iterations': 800, 'learning_rate': 0.01, 'depth': 6, 'l2_leaf_reg': 1, 'auto_class_weights': 'Balanced'},
        {'iterations': 500, 'learning_rate': 0.1, 'depth': 4, 'l2_leaf_reg': 5, 'auto_class_weights': 'Balanced'},
        {'iterations': 800, 'learning_rate': 0.05, 'depth': 8, 'l2_leaf_reg': 3, 'auto_class_weights': None},
        {'iterations': 1000, 'learning_rate': 0.03, 'depth': 6, 'l2_leaf_reg': 5, 'auto_class_weights': None},
    ]
    
    for params in trials:
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        f1_scores = []
        for train_idx, val_idx in cv.split(X_temp, y_temp):
            X_tr, y_tr = X_temp.iloc[train_idx], y_temp.iloc[train_idx]
            X_v, y_v = X_temp.iloc[val_idx], y_temp.iloc[val_idx]
            
            model = CatBoostClassifier(**params, loss_function='Logloss', eval_metric='F1', random_seed=42, verbose=0)
            model.fit(X_tr, y_tr, cat_features=cat_features, eval_set=(X_v, y_v), early_stopping_rounds=50)
            
            preds = model.predict(X_v)
            f1 = f1_score(y_v, preds, average='macro')
            f1_scores.append(f1)
            
        mean_f1 = np.mean(f1_scores)
        if mean_f1 > best_f1:
            best_f1 = mean_f1
            best_params = params
            
    print("\nBest params:", best_params)
    print("Best CV Macro-F1:", best_f1)
    
    # Now run a strict 5-fold CV on train+val with best params to report mean/std
    best_params['auto_class_weights'] = best_params['auto_class_weights'] if best_params['auto_class_weights'] != 'None' else None
    cv_5 = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    accs, f1s = [], []
    for train_idx, val_idx in cv_5.split(X_temp, y_temp):
        X_tr, y_tr = X_temp.iloc[train_idx], y_temp.iloc[train_idx]
        X_v, y_v = X_temp.iloc[val_idx], y_temp.iloc[val_idx]
        model = CatBoostClassifier(**best_params, loss_function='Logloss', eval_metric='F1', random_seed=42, verbose=0)
        model.fit(X_tr, y_tr, cat_features=cat_features, eval_set=(X_v, y_v), early_stopping_rounds=50)
        preds = model.predict(X_v)
        accs.append(accuracy_score(y_v, preds))
        f1s.append(f1_score(y_v, preds, average='macro'))
        
    print(f"\n5-Fold CV Accuracy: {np.mean(accs):.4f} +/- {np.std(accs):.4f}")
    print(f"5-Fold CV Macro-F1: {np.mean(f1s):.4f} +/- {np.std(f1s):.4f}")

    # Final Evaluation on Held-Out Test Set
    print("\n=== FINAL LOCKED TEST EVALUATION ===")
    final_model = CatBoostClassifier(**best_params, loss_function='Logloss', eval_metric='F1', random_seed=42, verbose=0)
    final_model.fit(X_temp, y_temp, cat_features=cat_features)
    final_model.save_model('../trained_model/priority_catboost_model.cbm')
    
    y_pred_test = final_model.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred_test)
    test_f1 = f1_score(y_test, y_pred_test, average='macro')
    
    print(f"Test Accuracy: {test_acc:.4f}")
    print(f"Test Macro-F1: {test_f1:.4f}")
    print("\nFeature Importances:")
    importances = final_model.get_feature_importance()
    feat_imp = pd.Series(importances, index=features).sort_values(ascending=False)
    print(feat_imp)
    
if __name__ == '__main__':
    main()
