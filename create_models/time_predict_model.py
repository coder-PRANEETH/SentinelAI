import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from catboost import CatBoostRegressor, Pool


def train_resolution_model():
    print("=" * 80)
    print("TRAINING RESOLUTION TIME PREDICTION MODEL (IMPROVED)")
    print("=" * 80)

    # 1. Load data
    data_path = 'dataset_processed/astram_events_resolved.csv'
    print(f"\nLoading data from {data_path}...")
    df = pd.read_csv(data_path)

    print(f"Total resolved records loaded: {len(df)}")

    # 2. Filter for incidents resolved within 24 hours
    print("\nFiltering for incidents resolved within 24 hours...")
    
    # response_time_hours should be between 0 and 24
    df_filtered = df[(df['response_time_hours'] >= 0) & (df['response_time_hours'] <= 24)].copy()
    
    print(f"Records remaining after filtering: {len(df_filtered)}")
    
    # Show stats of target variable
    print("\nResolution time stats (minutes):")
    print(df_filtered['response_time_minutes'].describe())

    if len(df_filtered) < 50:
        print("⚠ Too few samples to train a model! Exiting.")
        return

    # 3. Select features available at the start of the incident
    cat_features = [
        'event_type_grouped',
        'event_cause',
        'corridor',
        'police_station_grouped',
        'veh_type_grouped',
        'day_of_week',
        'priority'  # Added priority as a feature since it is known at start
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
        df_filtered[col] = df_filtered[col].fillna('unknown').astype(str)

    for col in num_features:
        if df_filtered[col].isnull().any():
            median_val = df_filtered[col].median()
            df_filtered[col] = df_filtered[col].fillna(median_val)

    X = df_filtered[features]
    
    # Apply log transformation to the target variable to normalize its distribution
    # This prevents extreme outliers from biasing the model and resolves negative R2
    y_raw = df_filtered['response_time_minutes']
    y = np.log1p(y_raw)

    # 5. Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.20,
        random_state=42
    )

    # Also keep raw target values for final evaluation in minutes
    y_test_raw = np.expm1(y_test)

    print(f"\nDataset Split:")
    print(f"  Train Set: {X_train.shape[0]} samples")
    print(f"  Test Set:  {X_test.shape[0]} samples")

    # 6. Initialize CatBoost Pool
    cat_indices = [features.index(col) for col in cat_features]
    train_pool = Pool(X_train, y_train, cat_features=cat_indices)
    test_pool = Pool(X_test, y_test, cat_features=cat_indices)

    # 7. Configure and train CatBoost Regressor
    model = CatBoostRegressor(
        loss_function='RMSE',
        eval_metric='RMSE',
        iterations=1000,
        learning_rate=0.05,
        depth=6,
        l2_leaf_reg=4,
        random_seed=42,
        early_stopping_rounds=50,
        verbose=100
    )

    print("\nTraining CatBoost Regressor on log-scale resolution time...")
    model.fit(
        train_pool,
        eval_set=test_pool,
        use_best_model=True
    )

    # 8. Evaluate on original scale (minutes)
    print("\n" + "=" * 80)
    print("MODEL EVALUATION (IN MINUTES)")
    print("=" * 80)

    # Make predictions in log-scale
    y_pred_log = model.predict(X_test)
    
    # Transform back to minutes scale
    y_pred = np.expm1(y_pred_log)
    
    # Ensure no negative predictions
    y_pred = np.clip(y_pred, 0, None)

    mae = mean_absolute_error(y_test_raw, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test_raw, y_pred))
    r2 = r2_score(y_test_raw, y_pred)

    print(f"  Test MAE : {mae:.2f} minutes")
    print(f"  Test RMSE: {rmse:.2f} minutes")
    print(f"  Test R²  : {r2:.4f}")

    # Calculate log-scale metrics for reference
    r2_log = r2_score(y_test, y_pred_log)
    print(f"  Test R² (log-scale): {r2_log:.4f}")

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
    model_path = os.path.join(output_dir, 'resolution_time_model.cbm')

    print(f"\nSaving model to {model_path}...")
    model.save_model(model_path)
    print(f"✓ Model saved successfully! ({os.path.getsize(model_path) / 1024:.1f} KB)")

    # Save feature importances to CSV
    feat_imp_path = os.path.join(output_dir, 'resolution_feature_importance.csv')
    feat_imp.reset_index().rename(columns={'index': 'feature', 0: 'importance'}).to_csv(
        feat_imp_path, index=False
    )
    print(f"✓ Feature importance saved to {feat_imp_path}")

    print("\n" + "=" * 80)
    print("TRAINING COMPLETE ✓")
    print("=" * 80)

    return model


if __name__ == '__main__':
    train_resolution_model()
