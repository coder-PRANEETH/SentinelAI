import pandas as pd
import os
import shutil
import subprocess
from datetime import datetime

print("=" * 80)
print("POST EVENT LEARNING ENGINE")
print("=" * 80)

# ==========================================================
# PATHS
# ==========================================================

MASTER_DATASET = "dataset_processed/astram_events_processed.csv"

PREDICTION_LOGS = "logs/predictions.csv"
FEEDBACK_LOGS = "logs/officer_feedback.csv"

ARCHIVE_DIR = "logs/archive"

os.makedirs(ARCHIVE_DIR, exist_ok=True)

# ==========================================================
# LOAD DATA
# ==========================================================

print("\nLoading master dataset...")
master_df = pd.read_csv(MASTER_DATASET)

print(f"Master dataset size: {len(master_df)}")

print("\nLoading prediction logs...")
pred_df = pd.read_csv(PREDICTION_LOGS)

print(f"Prediction records: {len(pred_df)}")

print("\nLoading officer feedback...")
feedback_df = pd.read_csv(FEEDBACK_LOGS)

print(f"Feedback records: {len(feedback_df)}")

# ==========================================================
# MERGE
# ==========================================================

print("\nMerging predictions with feedback...")

merged = pred_df.merge(
    feedback_df,
    on="incident_id",
    how="inner"
)

print(f"Merged records: {len(merged)}")

if len(merged) == 0:
    print("\nNo completed incidents found.")
    exit()

# ==========================================================
# CREATE NEW TRAINING ROWS
# ==========================================================

print("\nCreating new training samples...")

new_rows = pd.DataFrame()

# ----------------------------
# FEATURES FROM PREDICTION LOG
# ----------------------------

feature_columns = [
    'event_type_grouped',
    'event_cause',
    'corridor',
    'police_station_grouped',
    'veh_type_grouped',
    'latitude',
    'longitude',
    'location_cluster',
    'hour_of_day',
    'month',
    'day_of_week',
    'is_peak_hour',
    'is_weekend',
    'is_cascaded',
    'cascade_size'
]

for col in feature_columns:
    if col in merged.columns:
        new_rows[col] = merged[col]

# ----------------------------
# TARGETS FROM FEEDBACK
# ----------------------------

new_rows["priority"] = merged["actual_priority"]
new_rows["requires_road_closure"] = merged["actual_closure"]

new_rows["response_time_minutes"] = (
    merged["actual_resolution_time"]
)

# ==========================================================
# APPEND TO MASTER DATASET
# ==========================================================

print("\nUpdating dataset...")

old_size = len(master_df)

updated_df = pd.concat(
    [master_df, new_rows],
    ignore_index=True
)

updated_df.to_csv(
    MASTER_DATASET,
    index=False
)

print(f"Before: {old_size}")
print(f"After : {len(updated_df)}")

# ==========================================================
# RETRAIN MODELS
# ==========================================================

print("\n" + "=" * 80)
print("RETRAINING MODELS")
print("=" * 80)

models = [
    "risk_model.py",
    "road_closure_model.py",
    "resolution_time_model.py"
]

for script in models:

    print(f"\nRunning {script}")

    try:

        result = subprocess.run(
            ["python", script],
            capture_output=True,
            text=True,
            check=True
        )

        print("SUCCESS")

    except subprocess.CalledProcessError as e:

        print(f"FAILED: {script}")
        print(e.stderr)

# ==========================================================
# ARCHIVE LOGS
# ==========================================================

print("\nArchiving logs...")

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

shutil.move(
    PREDICTION_LOGS,
    f"{ARCHIVE_DIR}/predictions_{timestamp}.csv"
)

shutil.move(
    FEEDBACK_LOGS,
    f"{ARCHIVE_DIR}/feedback_{timestamp}.csv"
)

# Create fresh empty files

pd.DataFrame().to_csv(
    PREDICTION_LOGS,
    index=False
)

pd.DataFrame().to_csv(
    FEEDBACK_LOGS,
    index=False
)

# ==========================================================
# REPORT
# ==========================================================

print("\n" + "=" * 80)
print("LEARNING REPORT")
print("=" * 80)

print(f"New Incidents Learned : {len(new_rows)}")
print(f"Dataset Size          : {len(updated_df)}")
print(f"Retraining Time       : {datetime.now()}")

print("\nPOST EVENT LEARNING COMPLETE")
print("=" * 80)