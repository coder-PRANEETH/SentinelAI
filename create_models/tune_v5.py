import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from catboost import CatBoostClassifier, Pool

def feature_engineering(df):
    df = df.copy()
    
    # Interaction Features
    df['cause_x_peak'] = df['event_cause'].astype(str) + "_" + df['is_peak_hour'].astype(str)
    df['cause_x_zone'] = df['event_cause'].astype(str) + "_" + df['zone'].astype(str)
    df['veh_x_zone'] = df['veh_type_grouped'].astype(str) + "_" + df['zone'].astype(str)
    
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
    
    # Text Embeddings (TF-IDF reduced)
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
    
    # Exact V4 Split
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.20, random_state=42, stratify=y_temp)
    
    print(f"Data Split: Train ({len(X_train)}), Val ({len(X_val)}), Test ({len(X_test)})")
    
    # Catboost model
    best_params = {'iterations': 500, 'learning_rate': 0.1, 'depth': 4, 'l2_leaf_reg': 5, 'auto_class_weights': 'Balanced'}
    model = CatBoostClassifier(**best_params, loss_function='Logloss', eval_metric='F1', random_seed=42, verbose=0)
    model.fit(X_train, y_train, cat_features=cat_features, eval_set=(X_val, y_val), early_stopping_rounds=50)
    
    # 5-Fold CV on Train+Val to check stability
    cv_5 = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    accs, f1s = [], []
    for train_idx, val_idx in cv_5.split(X_temp, y_temp):
        X_tr, y_tr = X_temp.iloc[train_idx], y_temp.iloc[train_idx]
        X_v, y_v = X_temp.iloc[val_idx], y_temp.iloc[val_idx]
        m = CatBoostClassifier(**best_params, loss_function='Logloss', eval_metric='F1', random_seed=42, verbose=0)
        m.fit(X_tr, y_tr, cat_features=cat_features, eval_set=(X_v, y_v), early_stopping_rounds=50)
        preds = m.predict(X_v)
        accs.append(accuracy_score(y_v, preds))
        f1s.append(f1_score(y_v, preds, average='macro'))
        
    print(f"\n5-Fold CV Accuracy: {np.mean(accs):.4f} +/- {np.std(accs):.4f}")
    print(f"5-Fold CV Macro-F1: {np.mean(f1s):.4f} +/- {np.std(f1s):.4f}")
    
    # Calibrated Threshold Tuning on Validation Set
    val_probs = model.predict_proba(X_val)[:, 1]
    best_thresh = 0.5
    best_val_f1 = -1
    for thresh in np.arange(0.3, 0.7, 0.02):
        preds = (val_probs >= thresh).astype(int)
        f1 = f1_score(y_val, preds, average='macro')
        if f1 > best_val_f1:
            best_val_f1 = f1
            best_thresh = thresh
            
    print(f"\nBest tuned threshold on validation set: {best_thresh:.2f} (Val F1: {best_val_f1:.4f})")
    
    final_model = CatBoostClassifier(**best_params, loss_function='Logloss', eval_metric='F1', random_seed=42, verbose=0)
    final_model.fit(X_temp, y_temp, cat_features=cat_features)
    final_model.save_model('../trained_model/priority_catboost_model.cbm')
    
    # Final Locked Evaluation
    print("\n=== FINAL LOCKED TEST EVALUATION ===")
    test_probs = final_model.predict_proba(X_test)[:, 1]
    y_pred_test = (test_probs >= best_thresh).astype(int)
    
    test_acc = accuracy_score(y_test, y_pred_test)
    test_f1 = f1_score(y_test, y_pred_test, average='macro')
    
    print(f"Test Accuracy: {test_acc:.4f}")
    print(f"Test Macro-F1: {test_f1:.4f}")
    
    print(classification_report(y_test, y_pred_test))
    print(confusion_matrix(y_test, y_pred_test))
    
    importances = final_model.get_feature_importance()
    feat_imp = pd.Series(importances, index=features).sort_values(ascending=False).head(15)
    print("\nTop 15 Features:")
    print(feat_imp)
    
    # Analyze misclassifications
    print("\n=== MISCLASSIFICATION ANALYSIS ===")
    test_df = df.loc[X_test.index].copy()
    test_df['predicted'] = y_pred_test
    test_df['pred_prob'] = test_probs
    test_df['actual'] = y_test
    misclassified = test_df[test_df['actual'] != test_df['predicted']]
    sample = misclassified.sample(min(10, len(misclassified)), random_state=42)
    for _, row in sample.iterrows():
        print("="*60)
        print(f"ACTUAL: {'HIGH' if row['actual']==1 else 'LOW'} | PRED: {'HIGH' if row['predicted']==1 else 'LOW'} (Prob: {row['pred_prob']:.2f})")
        print(f"Cause: {row['event_cause']} | Vehicle: {row['veh_type']} | Zone: {row['zone']}")
        print(f"Desc: {row['description']}")
        print(f"Hour: {row['hour_of_day']} | Peak: {row['is_peak_hour']} | Historical Zone Risk: {row['zone_historical_risk']:.2f}")

if __name__ == '__main__':
    main()
