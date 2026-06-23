import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from catboost import CatBoostClassifier, Pool


def train_priority_model():
    print("=" * 80)
    print("TRAINING PRIORITY PREDICTION MODEL USING CATBOOST")
    print("=" * 80)

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Load data
    # ──────────────────────────────────────────────────────────────────────────
    data_path = 'dataset_processed/astram_events_processed.csv'
    print(f"\nLoading data from {data_path}...")
    df = pd.read_csv(data_path)

    # Strip column names whitespace just in case
    df.columns = df.columns.str.strip()

    print(f"  Total records loaded: {len(df)}")
    print(f"  Columns: {len(df.columns)}")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Prepare target variable
    # ──────────────────────────────────────────────────────────────────────────
    print("\nPreparing target variable...")

    # Only keep rows with known priority (high / low)
    # Drop 'unknown' or NaN priorities since they can't be used for training
    valid_priorities = ['high', 'low']
    df = df[df['priority'].isin(valid_priorities)].copy()
    print(f"  Records with valid priority: {len(df)}")

    # Map high -> 1, low -> 0
    df['priority_target'] = df['priority'].map({'high': 1, 'low': 0})

    print(f"  Target distribution:")
    print(f"    High (1): {(df['priority_target'] == 1).sum()} ({(df['priority_target'] == 1).mean()*100:.1f}%)")
    print(f"    Low  (0): {(df['priority_target'] == 0).sum()} ({(df['priority_target'] == 0).mean()*100:.1f}%)")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Select features
    # ──────────────────────────────────────────────────────────────────────────
    print("\nSelecting features...")

    cat_features = [
        'event_type_grouped',
        'event_cause',
        'requires_road_closure',
        'veh_type_grouped',
        'day_of_week',
    ]

    num_features = [
        'hour_of_day',
        'month',
        'is_peak_hour',
        'is_weekend',
        'is_cascaded',
        'cascade_size',
    ]

    features = cat_features + num_features

    # Verify all feature columns exist
    missing_cols = [c for c in features if c not in df.columns]
    if missing_cols:
        print(f"  ⚠ Missing columns (will be dropped): {missing_cols}")
        features = [c for c in features if c in df.columns]
        cat_features = [c for c in cat_features if c in df.columns]
        num_features = [c for c in num_features if c in df.columns]

    print(f"  Categorical features ({len(cat_features)}): {cat_features}")
    print(f"  Numeric features ({len(num_features)}): {num_features}")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Handle missing values
    # ──────────────────────────────────────────────────────────────────────────
    print("\nHandling missing values...")

    for col in cat_features:
        n_null = df[col].isnull().sum()
        df[col] = df[col].fillna('unknown').astype(str)
        if n_null > 0:
            print(f"  {col}: filled {n_null} nulls with 'unknown'")

    for col in num_features:
        n_null = df[col].isnull().sum()
        if n_null > 0:
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            print(f"  {col}: filled {n_null} nulls with median ({median_val:.2f})")

    X = df[features]
    y = df['priority_target']

    # ──────────────────────────────────────────────────────────────────────────
    # 5. Train-Test Split (80/20)
    # ──────────────────────────────────────────────────────────────────────────
    print("\nSplitting data 80/20...")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.20,
        random_state=42,
        stratify=y
    )

    print(f"  Train set: {X_train.shape[0]} samples")
    print(f"  Test set:  {X_test.shape[0]} samples")

    # ──────────────────────────────────────────────────────────────────────────
    # 6. Build CatBoost pools
    # ──────────────────────────────────────────────────────────────────────────
    cat_indices = [features.index(col) for col in cat_features]

    train_pool = Pool(X_train, y_train, cat_features=cat_indices)
    test_pool = Pool(X_test, y_test, cat_features=cat_indices)

    # ──────────────────────────────────────────────────────────────────────────
    # 7. Configure and train model
    # ──────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("TRAINING CATBOOST CLASSIFIER")
    print("=" * 80)

    model = CatBoostClassifier(
        loss_function='Logloss',
        eval_metric='F1',
        auto_class_weights='Balanced',
        iterations=1500,
        learning_rate=0.03,
        depth=8,
        l2_leaf_reg=5,
        random_strength=2,
        early_stopping_rounds=100,
        random_seed=42,
        verbose=200,
    )

    model.fit(
        train_pool,
        eval_set=test_pool,
        use_best_model=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 8. Evaluate
    # ──────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("MODEL EVALUATION")
    print("=" * 80)

    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    print(f"\n  Test Accuracy: {accuracy:.4f}")

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Low', 'High']))

    print("Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"  {'':>12} Pred Low  Pred High")
    print(f"  {'Actual Low':>12}   {cm[0][0]:>5}      {cm[0][1]:>5}")
    print(f"  {'Actual High':>12}   {cm[1][0]:>5}      {cm[1][1]:>5}")

    # ──────────────────────────────────────────────────────────────────────────
    # 9. Feature importance
    # ──────────────────────────────────────────────────────────────────────────
    print("\n" + "-" * 40)
    print("Feature Importances:")
    print("-" * 40)
    importances = model.get_feature_importance()
    feat_imp = pd.Series(importances, index=features).sort_values(ascending=False)
    for feat, imp in feat_imp.items():
        bar = '█' * int(imp / feat_imp.max() * 30)
        print(f"  {feat:<28} {imp:>6.2f}  {bar}")

    # ──────────────────────────────────────────────────────────────────────────
    # 10. Save model
    # ──────────────────────────────────────────────────────────────────────────
    output_dir = 'trained_model'
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, 'priority_catboost_model.cbm')

    print(f"\nSaving model to {model_path}...")
    model.save_model(model_path)
    print(f"✓ Model saved successfully! ({os.path.getsize(model_path) / 1024:.1f} KB)")

    # Also save feature list for inference
    feature_info_path = os.path.join(output_dir, 'feature_info.csv')
    feat_imp.reset_index().rename(columns={'index': 'feature', 0: 'importance'}).to_csv(
        feature_info_path, index=False
    )
    print(f"✓ Feature info saved to {feature_info_path}")

    print("\n" + "=" * 80)
    print("TRAINING COMPLETE ✓")
    print("=" * 80)

    return model


if __name__ == '__main__':
    train_priority_model()
