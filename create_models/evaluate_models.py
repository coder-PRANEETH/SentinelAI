import os
import pandas as pd
import numpy as np
import sys
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, roc_auc_score, mean_absolute_error, mean_squared_error, r2_score
from catboost import CatBoostClassifier, CatBoostRegressor

def evaluate_models():
    data_path = 'dataset_processed/astram_events_processed.csv'
    df = pd.read_csv(data_path)
    df.columns = df.columns.str.strip()

    print("=== OVERALL DATA ===")
    print(f"Total rows: {len(df)}")
    planned_df = df[df['event_type_grouped'] == 'planned']
    print(f"Planned events: {len(planned_df)}")

    # 1. PRIORITY MODEL
    print("\n\n=== PRIORITY MODEL ===")
    valid_priorities = ['high', 'low']
    pdf = df[df['priority'].isin(valid_priorities)].copy()
    pdf['priority_target'] = pdf['priority'].map({'high': 1, 'low': 0})
    cat_features_p = [
        'event_type_grouped',
        'event_cause',
        'requires_road_closure',
        'veh_type_grouped',
        'day_of_week',
        'zone',
    ]

    num_features_p = [
        'hour_of_day',
        'month',
        'is_peak_hour',
        'is_weekend',
    ]
    features_p = cat_features_p + num_features_p

    for col in cat_features_p:
        pdf[col] = pdf[col].fillna('unknown').astype(str)
    for col in num_features_p:
        if pdf[col].isnull().any():
            pdf[col] = pdf[col].fillna(pdf[col].median())

    X_p = pdf[features_p]
    y_p = pdf['priority_target']
    
    _, X_test_p, y_train_p, y_test_p = train_test_split(X_p, y_p, test_size=0.20, random_state=42, stratify=y_p)

    model_p = CatBoostClassifier()
    model_p.load_model('../trained_model/priority_catboost_model.cbm')
    y_pred_p = model_p.predict(X_test_p)
    y_pred_p = np.array([int(p) for p in y_pred_p])

    print("\n\n=== PRIORITY MODEL ===")
    print("ALL TEST DATA (Priority)")
    
    # --- Baseline calculation ---
    # Most frequent class in train
    from collections import Counter
    majority_class_p = Counter(y_train_p).most_common(1)[0][0]
    baseline_pred_p = [majority_class_p] * len(y_test_p)
    
    from sklearn.metrics import accuracy_score, f1_score
    b_acc_p = accuracy_score(y_test_p, baseline_pred_p)
    b_f1_p = f1_score(y_test_p, baseline_pred_p, average='macro')
    print(f"BASELINE: Accuracy={b_acc_p:.4f}, Macro-F1={b_f1_p:.4f}")
    
    m_acc_p = accuracy_score(y_test_p, y_pred_p)
    m_f1_p = f1_score(y_test_p, y_pred_p, average='macro')
    print(f"MODEL: Accuracy={m_acc_p:.4f}, Macro-F1={m_f1_p:.4f}")
    
    print(classification_report(y_test_p, y_pred_p))
    print(confusion_matrix(y_test_p, y_pred_p))
    
    planned_idx = X_test_p['event_type_grouped'] == 'planned'
    if planned_idx.sum() > 0:
        print("\nPLANNED EVENTS ONLY (Priority)")
        print(classification_report(y_test_p[planned_idx], y_pred_p[planned_idx]))
        print(confusion_matrix(y_test_p[planned_idx], y_pred_p[planned_idx]))
    else:
        print("No planned events in test set.")

    # 2. CLOSURE MODEL
    print("\n\n=== CLOSURE MODEL ===")
    cdf = df.copy()
    cdf['target'] = cdf['requires_road_closure'].astype(int)
    cat_features_c = ['event_type_grouped', 'event_cause', 'corridor', 'police_station_grouped', 'veh_type_grouped', 'day_of_week', 'priority']
    num_features_c = ['latitude', 'longitude', 'location_cluster', 'hour_of_day', 'month', 'is_peak_hour', 'is_weekend', 'is_cascaded', 'cascade_size']
    features_c = cat_features_c + num_features_c

    for col in cat_features_c:
        cdf[col] = cdf[col].fillna('unknown').astype(str)
    for col in num_features_c:
        cdf[col] = cdf[col].fillna(cdf[col].median())

    X_c = cdf[features_c]
    y_c = cdf['target']
    _, X_test_c, y_train_c, y_test_c = train_test_split(X_c, y_c, test_size=0.20, random_state=42, stratify=y_c)

    model_c = CatBoostClassifier()
    model_c.load_model('../trained_model/road_closure_catboost_model.cbm')
    y_pred_c = model_c.predict(X_test_c)
    y_pred_proba_c = model_c.predict_proba(X_test_c)[:, 1]

    print("\n\n=== CLOSURE MODEL ===")
    print("ALL TEST DATA (Closure)")
    
    # --- Baseline calculation ---
    from collections import Counter
    majority_class_c = Counter(y_train_c).most_common(1)[0][0]
    baseline_pred_c = [majority_class_c] * len(y_test_c)
    
    b_acc_c = accuracy_score(y_test_c, baseline_pred_c)
    b_f1_c = f1_score(y_test_c, baseline_pred_c, average='macro')
    print(f"BASELINE: Accuracy={b_acc_c:.4f}, Macro-F1={b_f1_c:.4f}")
    
    m_acc_c = accuracy_score(y_test_c, y_pred_c)
    m_f1_c = f1_score(y_test_c, y_pred_c, average='macro')
    print(f"MODEL: Accuracy={m_acc_c:.4f}, Macro-F1={m_f1_c:.4f}")

    roc_auc = roc_auc_score(y_test_c, y_pred_proba_c)
    print(f"ROC-AUC: {roc_auc:.4f}")
    print(classification_report(y_test_c, y_pred_c))
    
    planned_idx_c = X_test_c['event_type_grouped'] == 'planned'
    if planned_idx_c.sum() > 0:
        print("\nPLANNED EVENTS ONLY (Closure)")
        print(classification_report(y_test_c[planned_idx_c], y_pred_c[planned_idx_c]))
        try:
            print(f"ROC-AUC: {roc_auc_score(y_test_c[planned_idx_c], y_proba_c[planned_idx_c]):.4f}")
        except:
            print("ROC-AUC not defined for single class in planned events")

    # 3. RESOLUTION TIME MODEL
    print("\n\n=== RESOLUTION TIME MODEL ===")
    tdf = pd.read_csv('dataset_processed/astram_events_resolved.csv')
    tdf = tdf[(tdf['response_time_hours'] >= 0) & (tdf['response_time_hours'] <= 24)].copy()
    
    cat_features_t = ['event_type_grouped', 'event_cause', 'corridor', 'police_station_grouped', 'veh_type_grouped', 'day_of_week', 'priority']
    num_features_t = ['latitude', 'longitude', 'location_cluster', 'hour_of_day', 'month', 'is_peak_hour', 'is_weekend', 'is_cascaded', 'cascade_size']
    features_t = cat_features_t + num_features_t

    for col in cat_features_t:
        tdf[col] = tdf[col].fillna('unknown').astype(str)
    for col in num_features_t:
        if tdf[col].isnull().any():
            tdf[col] = tdf[col].fillna(tdf[col].median())

    X_t = tdf[features_t]
    y_raw = tdf['response_time_minutes']
    y_t = np.log1p(y_raw)
    
    _, X_test_t, _, y_test_log = train_test_split(X_t, y_t, test_size=0.20, random_state=42)
    y_test_t = np.expm1(y_test_log)

    model_t = CatBoostRegressor()
    model_t.load_model('../trained_model/resolution_time_model.cbm')
    y_pred_log = model_t.predict(X_test_t)
    y_pred_t = np.expm1(y_pred_log)
    y_pred_t = np.clip(y_pred_t, 0, None)

    mae = mean_absolute_error(y_test_t, y_pred_t)
    rmse = np.sqrt(mean_squared_error(y_test_t, y_pred_t))
    r2 = r2_score(y_test_t, y_pred_t)
    med_ae = np.median(np.abs(y_test_t - y_pred_t))

    print("ALL TEST DATA (Time)")
    print(f"MAE: {mae:.2f}")
    print(f"RMSE: {rmse:.2f}")
    print(f"R2: {r2:.4f}")
    print(f"Median AE: {med_ae:.2f}")
    
    errors = np.abs(y_test_t - y_pred_t)
    print(f"50th percentile error: {np.percentile(errors, 50):.2f}")
    print(f"80th percentile error: {np.percentile(errors, 80):.2f}")
    print(f"95th percentile error: {np.percentile(errors, 95):.2f}")

    planned_idx_t = X_test_t['event_type_grouped'] == 'planned'
    if planned_idx_t.sum() > 0:
        y_test_pt = y_test_t[planned_idx_t]
        y_pred_pt = y_pred_t[planned_idx_t]
        print("\nPLANNED EVENTS ONLY (Time)")
        print(f"Count: {len(y_test_pt)}")
        print(f"MAE: {mean_absolute_error(y_test_pt, y_pred_pt):.2f}")
        print(f"Median AE: {np.median(np.abs(y_test_pt - y_pred_pt)):.2f}")

    # 4. TF-IDF Quality
    print("\n\n=== TF-IDF SEARCH QUALITY ===")
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'final_endpoints')))
    from models import search_similar_incidents
    
    test_queries = [
        "huge political rally expected at hosur road",
        "CM convoy passing orr east 1",
        "two wheeler collision accident at silk board",
        "demonstration near majestic",
        "roadwork digging at mg road"
    ]
    
    for q in test_queries:
        print(f"Query: {q}")
        res = search_similar_incidents(q, top_k=3)
        print(f"  Exact Cause Match: {res.get('exact_cause_match')}")
        for i, r in enumerate(res['similar_cases']):
            print(f"  Match {i+1}: Score={r['similarity_score']:.4f}, cause={r.get('event_cause')}, corridor={r.get('corridor')}")
            

if __name__ == '__main__':
    evaluate_models()
