import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score, roc_auc_score, confusion_matrix
from catboost import CatBoostClassifier, Pool


def train_road_closure_model():
    print("=" * 80)
    print("TRAINING ROAD CLOSURE PREDICTION MODEL USING CATBOOST")
    print("=" * 80)

    # 1. Load data
    data_path = 'dataset_processed/astram_events_processed.csv'
    print(f"\nLoading data from {data_path}...")
    df = pd.read_csv(data_path)

    print(f"Total records loaded: {len(df)}")

    # 2. Prepare target variable
    df['target'] = df['requires_road_closure'].astype(int)

    print(f"Target distribution:")
    print(f"  Requires Closure (1): {(df['target'] == 1).sum()} ({(df['target'] == 1).mean()*100:.1f}%)")
    print(f"  No Closure (0):       {(df['target'] == 0).sum()} ({(df['target'] == 0).mean()*100:.1f}%)")

    # 3. Restrict features to pre-dispatch knowledge to prevent data leakage.
    cat_features = [
        'event_type_grouped',
        'event_cause',
        'corridor',
        'police_station_grouped',
        'veh_type_grouped',
        'day_of_week',
        'priority'
    ]

    num_features = [
        'latitude',
        'longitude',
        'location_cluster',
        'hour_of_day',
        'month',
        'is_peak_hour',
        'is_weekend',
        'is_cascaded',
        'cascade_size'
    ]

    features = cat_features + num_features
    print(f"\nSelected features ({len(features)}):")
    print(f"  Categorical: {cat_features}")
    print(f"  Numeric:     {num_features}")

    # 4. Handle missing values
    for col in cat_features:
        df[col] = df[col].fillna('unknown').astype(str)
    for col in num_features:
        if df[col].isnull().any():
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)

    X = df[features]
    y = df['target']

    # 5. Split data 80/20 stratified by target due to class imbalance
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.20,
        random_state=42,
        stratify=y
    )

    print(f"\nDataset Split:")
    print(f"  Train Set: {X_train.shape[0]} samples")
    print(f"  Test Set:  {X_test.shape[0]} samples")

    # 6. Initialize CatBoost Pool
    cat_indices = [features.index(col) for col in cat_features]
    train_pool = Pool(X_train, y_train, cat_features=cat_indices)
    test_pool = Pool(X_test, y_test, cat_features=cat_indices)

    # 7. Configure and train CatBoost Classifier
    # Balanced class weights compensate for severe target imbalance.
    model = CatBoostClassifier(
        loss_function='Logloss',
        eval_metric='F1',
        auto_class_weights='Balanced',
        iterations=1000,
        learning_rate=0.05,
        depth=6,
        l2_leaf_reg=4,
        random_seed=42,
        early_stopping_rounds=50,
        verbose=100
    )

    print("\nTraining CatBoost Classifier...")
    model.fit(
        train_pool,
        eval_set=test_pool,
        use_best_model=True
    )

    # 8. Evaluate
    print("\n" + "=" * 80)
    print("MODEL EVALUATION")
    print("=" * 80)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_proba)

    print(f"  Test Accuracy: {accuracy:.4f}")
    print(f"  Test F1-Score: {f1:.4f}")
    print(f"  Test ROC-AUC : {auc:.4f}")

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['No Closure', 'Requires Closure']))

    print("Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"  {'':>16} Pred No  Pred Yes")
    print(f"  {'Actual No':>16}   {cm[0][0]:>5}      {cm[0][1]:>5}")
    print(f"  {'Actual Yes':>16}   {cm[1][0]:>5}      {cm[1][1]:>5}")

    # 9. Feature Importance
    print("\nFeature Importances:")
    importances = model.get_feature_importance()
    feat_imp = pd.Series(importances, index=features).sort_values(ascending=False)
    for feat, imp in feat_imp.items():
        bar = '█' * int(imp / (feat_imp.max() if feat_imp.max() > 0 else 1) * 30)
        print(f"  {feat:<28} {imp:>6.2f}  {bar}")

    # 10. Save Model
    output_dir = 'trained_model'
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, 'road_closure_catboost_model.cbm')

    print(f"\nSaving model to {model_path}...")
    model.save_model(model_path)
    print(f"✓ Model saved successfully! ({os.path.getsize(model_path) / 1024:.1f} KB)")

    # Save feature list for inference
    feature_info_path = os.path.join(output_dir, 'road_closure_feature_importance.csv')
    feat_imp.reset_index().rename(columns={'index': 'feature', 0: 'importance'}).to_csv(
        feature_info_path, index=False
    )
    print(f"✓ Feature importances saved to {feature_info_path}")

    print("\n" + "=" * 80)
    print("TRAINING COMPLETE ✓")
    print("=" * 80)

    return model


if __name__ == '__main__':
    train_road_closure_model()
