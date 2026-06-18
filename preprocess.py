
# SentinelAI: Complete Data Preprocessing Pipeline
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')
 
# ============================================================================
# STEP 1: LOAD DATA
# ============================================================================
 
df = pd.read_csv('theme2.csv')
for col in df.select_dtypes(include=['object']).columns:
    df[col] = df[col].astype(str).str.replace(r'[\r\n\t]+', ' ', regex=True).str.strip()
 
print("=" * 80)
print("DATASET OVERVIEW")
print("=" * 80)
print(f"Total Records: {len(df)}")
print(f"Total Columns: {len(df.columns)}")
print(f"Date Range: {df['start_datetime'].min()} to {df['start_datetime'].max()}")
print(f"Missing Values:\n{df.isnull().sum()}")
 
# ============================================================================
# STEP 2: DATA CLEANING
# ============================================================================
 
print("\n" + "=" * 80)
print("STEP 2: DATA CLEANING")
print("=" * 80)
 
# 2.1 Datetime conversion
df['start_datetime'] = pd.to_datetime(df['start_datetime'], errors='coerce')
df['end_datetime'] = pd.to_datetime(df['end_datetime'], errors='coerce')
df['resolved_datetime'] = pd.to_datetime(df['resolved_datetime'], errors='coerce')
df['closed_datetime'] = pd.to_datetime(df['closed_datetime'], errors='coerce')
df['created_date'] = pd.to_datetime(df['created_date'], errors='coerce')
 
print(f"✓ Datetime columns converted")
 
# 2.2 Remove duplicate rows
initial_rows = len(df)
df = df.drop_duplicates(subset=['id'], keep='first')
print(f"✓ Duplicates removed: {initial_rows - len(df)} rows")
 
# 2.3 Handle NULL critical values
# Keep these rows but mark them
df['has_resolution'] = ~df['resolved_datetime'].isna()
df['has_assignment'] = ~df['assigned_to_police_id'].isna()
 
print(f"✓ Critical NULL values marked")
print(f"  - Incidents with resolution: {df['has_resolution'].sum()} ({df['has_resolution'].sum()/len(df)*100:.1f}%)")
print(f"  - Incidents with assignment: {df['has_assignment'].sum()} ({df['has_assignment'].sum()/len(df)*100:.1f}%)")
 
# 2.4 Standardize text fields (lowercase, strip)
text_cols = ['event_type', 'event_cause', 'corridor', 'police_station', 'status', 'priority']
for col in text_cols:
    if col in df.columns:
        df[col] = df[col].fillna('unknown').str.strip().str.lower()
 
print(f"✓ Text fields standardized")
 
# 2.5 Coordinate validation
# Remove rows with 0,0 coordinates (invalid)
invalid_coords = (df['latitude'] == 0) | (df['longitude'] == 0)
print(f"✓ Invalid coordinates: {invalid_coords.sum()} rows marked")
 
# Keep them but mark
df['has_valid_coords'] = ~invalid_coords
 
# 2.6 Priority mapping
priority_map = {
    'high': 3,
    'medium': 2,
    'low': 1,
    'critical': 4,
    'unknown': 2
}
df['priority_numeric'] = df['priority'].map(priority_map).fillna(2)
 
print(f"✓ Priority converted to numeric")
 
# ============================================================================
# STEP 3: FEATURE ENGINEERING
# ============================================================================
 
print("\n" + "=" * 80)
print("STEP 3: FEATURE ENGINEERING")
print("=" * 80)
 
# 3.1 Temporal features
df['hour_of_day'] = df['start_datetime'].dt.hour
df['day_of_week'] = df['start_datetime'].dt.day_name()
df['date'] = df['start_datetime'].dt.date
df['week_of_year'] = df['start_datetime'].dt.isocalendar().week
df['month'] = df['start_datetime'].dt.month
df['year'] = df['start_datetime'].dt.year
 
# Peak hour indicator
df['is_peak_hour'] = df['hour_of_day'].isin([7,8,9,10,17,18,19,20]).astype(int)
 
# Weekend indicator
df['is_weekend'] = df['day_of_week'].isin(['Saturday', 'Sunday']).astype(int)
 
print(f"✓ Temporal features created")
# 3.2 Response time calculation (CRITICAL)

df['completion_time'] = (
    df['resolved_datetime']
    .fillna(df['closed_datetime'])
)

df['response_time_minutes'] = (
    (df['completion_time'] - df['start_datetime'])
    .dt.total_seconds() / 60
)

current_time = pd.Timestamp.now(tz='UTC')

open_mask = (
    df['response_time_minutes'].isna() &
    (df['status'] == 'active')
)

if open_mask.any():
    # Ensure start_datetime is tz-aware for subtraction
    start_dt = df.loc[open_mask, 'start_datetime']
    if start_dt.dt.tz is None:
        start_dt = start_dt.dt.tz_localize('UTC')
    df.loc[open_mask, 'response_time_minutes'] = (
        (current_time - start_dt)
        .dt.total_seconds() / 60
    )

df['response_time_hours'] = df['response_time_minutes'] / 60
# 3.3 Event type categorization
# Group rare event types into 'others'
event_type_counts = df['event_type'].value_counts()
rare_types = event_type_counts[event_type_counts < 50].index
 
df['event_type_grouped'] = df['event_type'].apply(
    lambda x: 'others' if x in rare_types else x
)
 
print(f"✓ Event types grouped")
print(f"  - Unique event types (before): {df['event_type'].nunique()}")
print(f"  - Unique event types (after): {df['event_type_grouped'].nunique()}")
 
# 3.4 Location clustering (group nearby locations)
from sklearn.cluster import KMeans
 
# Only use valid coordinates
valid_coords = df[df['has_valid_coords']].copy()
 
if len(valid_coords) > 0:
    # Cluster locations into zones (e.g., 20 zones)
    coords_array = valid_coords[['latitude', 'longitude']].values
    
    kmeans = KMeans(n_clusters=min(20, len(valid_coords)), random_state=42)
    df.loc[valid_coords.index, 'location_cluster'] = kmeans.fit_predict(coords_array)
    
    # Fill invalid coordinates with nearest cluster or mode
    df['location_cluster'].fillna(df['location_cluster'].mode()[0], inplace=True)
    
    print(f"✓ Location clustering completed (20 clusters)")
else:
    df['location_cluster'] = 0
    print(f"✓ Location clustering skipped (no valid coordinates)")
 
# 3.5 Corridor standardization
# If corridor is missing, try to extract from address or assign 'unknown'
df['corridor'] = df['corridor'].fillna('unknown')
df['corridor'] = df['corridor'].apply(lambda x: 'unknown' if x == '' else x)
 
print(f"✓ Corridor standardized")
print(f"  - Unique corridors: {df['corridor'].nunique()}")
 
# 3.6 Incident severity score (synthetic, based on available data)
# Factors: priority + event_type + requires_road_closure + response_time
df['severity_score'] = (
    (df['event_cause'] == 'vehicle_breakdown').astype(int) * 2 +
    (df['event_cause'] == 'accident').astype(int) * 3 +
    (df['requires_road_closure'] == True).astype(int) * 2 +
    np.log1p(df['response_time_hours'].fillna(0)) * 0.5  # Longer response = severe
)
 
df['severity_score'] = (df['severity_score'] / df['severity_score'].max()) * 10  # Normalize 0-10
 
print(f"✓ Severity score calculated")
print(f"  - Mean severity: {df['severity_score'].mean():.2f}/10")
 
# 3.7 Status normalization
status_map = {
    'active': 'active',
    'closed': 'closed',
    'resolved': 'resolved',
    'unknown': 'unknown'
}
df['status'] = df['status'].map(status_map).fillna('unknown')
 
# Indicator: was incident actually resolved?
df['is_resolved'] = df['completion_time'].notna().astype(int)
 
print(f"✓ Status standardized")
print(f"  - Active: {(df['status'] == 'active').sum()}")
print(f"  - Resolved: {(df['status'] == 'resolved').sum()}")
print(f"  - Closed: {(df['status'] == 'closed').sum()}")
 
# 3.8 Police station clustering (handle rare stations)
station_counts = df['police_station'].value_counts()
rare_stations = station_counts[station_counts < 10].index
 
df['police_station_grouped'] = df['police_station'].apply(
    lambda x: 'other_station' if x in rare_stations else x
)
 
print(f"✓ Police stations grouped")
print(f"  - Unique stations (before): {df['police_station'].nunique()}")
print(f"  - Unique stations (after): {df['police_station_grouped'].nunique()}")
 
# 3.9 Cascade detection (using citizen_accident_id)
df['is_cascaded'] = (~df['citizen_accident_id'].isna()).astype(int)
df['cascade_group'] = df['citizen_accident_id'].fillna('single_event')
 
cascade_counts = df[df['is_cascaded'] == 1].groupby('cascade_group').size()
df['cascade_size'] = df['cascade_group'].map(cascade_counts).fillna(1)
 
print(f"✓ Cascade detection completed")
print(f"  - Cascaded incidents: {df['is_cascaded'].sum()} ({df['is_cascaded'].mean()*100:.1f}%)")
print(f"  - Avg cascade size: {df['cascade_size'].mean():.2f}")
 
# 3.10 Vehicle type grouping
vehicle_types = df['veh_type'].value_counts()
rare_vehicles = vehicle_types[vehicle_types < 5].index
 
df['veh_type_grouped'] = df['veh_type'].apply(
    lambda x: 'other_vehicle' if pd.isna(x) or x in rare_vehicles else x
)
 
print(f"✓ Vehicle types grouped")
 
# ============================================================================
# STEP 4: DATA QUALITY CHECKS
# ============================================================================
 
print("\n" + "=" * 80)
print("STEP 4: DATA QUALITY CHECKS")
print("=" * 80)
 
# 4.1 Outlier detection (response time)
q1 = df['response_time_minutes'].quantile(0.25)
q3 = df['response_time_minutes'].quantile(0.75)
iqr = q3 - q1
 
outlier_threshold = q3 + 3 * iqr
df['is_response_outlier'] = (df['response_time_minutes'] > outlier_threshold).astype(int)
 
print(f"✓ Response time outliers detected: {df['is_response_outlier'].sum()} ({df['is_response_outlier'].mean()*100:.2f}%)")
 
# 4.2 Data completeness
completeness = 1 - (df.isnull().sum() / len(df))
print(f"✓ Data completeness per column:")
for col, comp in completeness.items():
    if comp < 0.8:
        print(f"  ⚠️  {col}: {comp*100:.1f}%")
 
# 4.3 Logical consistency
# Check: if resolved, then response_time should exist
inconsistencies = (df['is_resolved'] == 1) & (df['response_time_minutes'].isna())
print(f"✓ Logical inconsistencies: {inconsistencies.sum()} (resolved but no response time)")
 
# ============================================================================
# STEP 5: CREATE ANALYSIS DATASETS
# ============================================================================
 
print("\n" + "=" * 80)
print("STEP 5: CREATE ANALYSIS DATASETS")
print("=" * 80)
 
# 5.1 Incidents with valid response times (for time analysis)
df_with_response = df[df['response_time_minutes'].notna()].copy()
print(f"✓ Dataset with response times: {len(df_with_response)} rows ({len(df_with_response)/len(df)*100:.1f}%)")
 
# 5.2 Incidents with valid coordinates (for spatial analysis)
df_with_coords = df[df['has_valid_coords']].copy()
print(f"✓ Dataset with valid coordinates: {len(df_with_coords)} rows ({len(df_with_coords)/len(df)*100:.1f}%)")
 
# 5.3 Incidents with resolution data (for operational analysis)
df_resolved = df[df['is_resolved'] == 1].copy()
print(f"✓ Dataset with resolutions: {len(df_resolved)} rows ({len(df_resolved)/len(df)*100:.1f}%)")
 
# 5.4 Cascaded incidents
df_cascades = df[df['is_cascaded'] == 1].copy()
print(f"✓ Dataset with cascades: {len(df_cascades)} rows ({len(df_cascades)/len(df)*100:.1f}%)")
 
# ============================================================================
# STEP 6: SUMMARY STATISTICS
# ============================================================================
 
print("\n" + "=" * 80)
print("STEP 6: SUMMARY STATISTICS")
print("=" * 80)
 
print("\nEvent Type Distribution:")
print(df['event_type_grouped'].value_counts().head(10))
 
print("\nPriority Distribution:")
print(df['priority'].value_counts())
 
print("\nStatus Distribution:")
print(df['status'].value_counts())
 
print("\nCorridors (Top 10):")
print(df['corridor'].value_counts().head(10))
 
print("\nPolice Stations (Top 10):")
print(df['police_station_grouped'].value_counts().head(10))
 
print("\nResponse Time Statistics (minutes):")
print(f"  Mean: {df['response_time_minutes'].mean():.1f}")
print(f"  Median: {df['response_time_minutes'].median():.1f}")
print(f"  Std Dev: {df['response_time_minutes'].std():.1f}")
print(f"  Min: {df['response_time_minutes'].min():.1f}")
print(f"  Max: {df['response_time_minutes'].max():.1f}")
 
print("\nSeverity Score Statistics:")
print(f"  Mean: {df['severity_score'].mean():.2f}/10")
print(f"  Median: {df['severity_score'].median():.2f}/10")
print(f"  Std Dev: {df['severity_score'].std():.2f}")
 
print("\nPeak Hours Impact:")
print(f"  Peak hour incidents: {df['is_peak_hour'].sum()} ({df['is_peak_hour'].mean()*100:.1f}%)")
print(f"  Avg response (peak): {df[df['is_peak_hour']==1]['response_time_minutes'].mean():.1f} min")
print(f"  Avg response (off-peak): {df[df['is_peak_hour']==0]['response_time_minutes'].mean():.1f} min")
 
print("\nWeekend Impact:")
print(f"  Weekend incidents: {df['is_weekend'].sum()} ({df['is_weekend'].mean()*100:.1f}%)")
print(f"  Avg response (weekend): {df[df['is_weekend']==1]['response_time_minutes'].mean():.1f} min")
print(f"  Avg response (weekday): {df[df['is_weekend']==0]['response_time_minutes'].mean():.1f} min")
 
# ============================================================================
# STEP 7: SAVE PROCESSED DATA
# ============================================================================
 
print("\n" + "=" * 80)
print("STEP 7: SAVE PROCESSED DATA")
print("=" * 80)
 
# Ensure output directory exists
os.makedirs('dataset_processed', exist_ok=True)

# Save main processed dataset
df.to_csv('dataset_processed/astram_events_processed.csv', index=False)
print(f"✓ Saved: dataset_processed/astram_events_processed.csv ({len(df)} rows)")
 
# Save analysis subsets
df_with_response.to_csv('dataset_processed/astram_events_with_response.csv', index=False)
print(f"✓ Saved: dataset_processed/astram_events_with_response.csv ({len(df_with_response)} rows)")
 
df_with_coords.to_csv('dataset_processed/astram_events_with_coords.csv', index=False)
print(f"✓ Saved: dataset_processed/astram_events_with_coords.csv ({len(df_with_coords)} rows)")
 
df_resolved.to_csv('dataset_processed/astram_events_resolved.csv', index=False)
print(f"✓ Saved: dataset_processed/astram_events_resolved.csv ({len(df_resolved)} rows)")
 
df_cascades.to_csv('dataset_processed/astram_events_cascades.csv', index=False)
print(f"✓ Saved: dataset_processed/astram_events_cascades.csv ({len(df_cascades)} rows)")

 
# ============================================================================
# STEP 8: KEY INSIGHTS FOR SENTINELAI
# ============================================================================
 
print("\n" + "=" * 80)
print("KEY INSIGHTS FOR SENTINELAI")
print("=" * 80)
 
# 8.1 Officer effectiveness (if assigned_to_police_id exists)
if 'assigned_to_police_id' in df.columns and df['assigned_to_police_id'].notna().sum() > 0:
    officer_stats = df[df['assigned_to_police_id'].notna()].groupby('assigned_to_police_id').agg({
        'response_time_minutes': 'mean',
        'is_resolved': 'mean',
        'severity_score': 'mean',
        'id': 'count'
    }).rename(columns={'id': 'incidents_handled'})
    
    officer_stats = officer_stats[officer_stats['incidents_handled'] >= 5]  # Filter for significant data
    officer_stats = officer_stats.sort_values('is_resolved', ascending=False)
    
    print("\nTop Officers (by resolution rate):")
    print(officer_stats.head(10))
 
# 8.2 Station performance
if 'police_station_grouped' in df.columns:
    station_stats = df.groupby('police_station_grouped').agg({
        'response_time_minutes': 'mean',
        'is_resolved': 'mean',
        'severity_score': 'mean',
        'id': 'count'
    }).rename(columns={'id': 'incidents_handled'})
    
    station_stats = station_stats.sort_values('incidents_handled', ascending=False)
    
    print("\nStation Performance:")
    print(station_stats.head(10))
 
# 8.3 Corridor analysis
if 'corridor' in df.columns:
    corridor_stats = df.groupby('corridor').agg({
        'response_time_minutes': 'mean',
        'is_resolved': 'mean',
        'severity_score': 'mean',
        'id': 'count'
    }).rename(columns={'id': 'incidents_handled'})
    
    corridor_stats = corridor_stats[corridor_stats['incidents_handled'] >= 5]
    corridor_stats = corridor_stats.sort_values('response_time_minutes', ascending=False)
    
    print("\nCritical Corridors (by response time):")
    print(corridor_stats.head(10))
 
print("\n" + "=" * 80)
print("PREPROCESSING COMPLETE ✓")
print("=" * 80)