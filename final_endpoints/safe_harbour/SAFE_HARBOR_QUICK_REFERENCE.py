"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                   SAFE HARBOR IDENTIFIER - QUICK REFERENCE                   ║
║                              API & Usage Guide                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════════
SECTION 1: IMPORTS & INITIALIZATION
═══════════════════════════════════════════════════════════════════════════════

from safe_harbor_identifier import (
    SafeHarborClusterer,
    SafeHarborStore,
    SafeHarborRecommender,
    SafeHarborVisualizer,
    GeoUtils,
)

from resource_recommendation_engine import (
    SafeHarborModule,
    ResourceRecommendationEngine,
    OperatorDashboard,
    MetricsCollector,
)


═══════════════════════════════════════════════════════════════════════════════
SECTION 2: CORE WORKFLOW
═══════════════════════════════════════════════════════════════════════════════

STEP 1: TRAIN (Offline, once per deployment)
─────────────────────────────────────────────

import pandas as pd

df = pd.read_csv('incidents.csv')

safe_harbor = SafeHarborModule(eps_meters=50.0, min_samples=3)
stats = safe_harbor.train(df)

print(f"Discovered {stats['total_harbors']} safe harbors")
print(f"Clustered {stats['total_incidents']} incidents")


STEP 2: DEPLOY (Online, one instance per system)
──────────────────────────────────────────────────

# In resource_agent.py or similar
engine = ResourceRecommendationEngine(safe_harbor)


STEP 3: INFER (Real-time, for each incident)
───────────────────────────────────────────────

incident = {
    'id': 'FKID000001',
    'event_type': 'unplanned',
    'latitude': 12.9218755,
    'longitude': 77.6451585,
    'event_cause': 'vehicle_breakdown',
    'veh_type_grouped': 'heavy_vehicle',
    'priority_numeric': 2,
    'zone': 'HSR Layout',
    'junction': '19th Main Road'
}

rec = engine.recommend(incident)

print(rec.operator_message)
# Output: "🚨 [MEDIUM] unplanned | 👥 Deploy: Traffic Police + Towing Crew | 
#          🛣️ Historical safe harbor: Push vehicle 85m East... | ⏱️ ETA: 15 min"


═══════════════════════════════════════════════════════════════════════════════
SECTION 3: SAFE HARBOR MODULE API
═══════════════════════════════════════════════════════════════════════════════

Class: SafeHarborModule
───────────────────────

Constructor:
  SafeHarborModule(eps_meters=50.0, min_samples=3)
    eps_meters: Cluster radius in meters (default 50m)
    min_samples: Min points per cluster (default 3)

Methods:

  1. train(df: pd.DataFrame) → Dict
     ──────────────────────────────
     Offline training on historical data.
     
     Args:
       df: DataFrame with event_cause, latitude, longitude,
           resolved_at_latitude, resolved_at_longitude columns
     
     Returns:
       Dictionary with keys:
         - total_harbors: Number of clusters found
         - total_incidents: Number of incidents clustered
         - avg_cluster_size: Mean incidents per cluster
         - avg_radius_meters: Mean cluster radius
     
     Example:
       stats = safe_harbor.train(historical_df)
       if stats['total_harbors'] > 0:
           print("Ready for inference")

  2. recommend(incident_id, incident_lat, incident_lon, zone=None, junction=None) → HarborRecommendation | None
     ────────────────────────────────────────────────────────────────────────────────────────────────────────
     Real-time recommendation for an incident.
     
     Args:
       incident_id (str): Unique incident ID
       incident_lat (float): Incident latitude
       incident_lon (float): Incident longitude
       zone (str, optional): Administrative zone
       junction (str, optional): Nearby junction/landmark
     
     Returns:
       HarborRecommendation object with:
         - nearest_harbor_id: Recommended harbor ID
         - nearest_harbor_lat: Harbor latitude
         - nearest_harbor_lon: Harbor longitude
         - distance_meters: Distance from incident to harbor
         - bearing: Compass bearing (0-360°)
         - confidence: Confidence score (0.0-1.0)
         - recommendation_text: Operator-friendly message
     
     Example:
       rec = safe_harbor.recommend(
           incident_id='FKID000001',
           incident_lat=12.9218755,
           incident_lon=77.6451585,
           zone='HSR Layout',
           junction='19th Main'
       )
       if rec:
           print(rec.recommendation_text)

  3. get_stats() → Dict
     ──────────────────
     Returns current model statistics.
     
     Returns:
       Dictionary with keys:
         - total_harbors: Number of discovered harbors
         - total_incidents: Total incidents clustered
         - avg_cluster_size: Average incidents per cluster
         - avg_radius_meters: Average cluster radius
     
     Example:
       stats = safe_harbor.get_stats()

  4. export_geojson(filepath: str) → None
     ─────────────────────────────────────
     Export harbors as GeoJSON for mapping tools.
     
     Args:
       filepath (str): Output file path (e.g., 'harbors.geojson')
     
     Example:
       safe_harbor.export_geojson('safe_harbors.geojson')


═══════════════════════════════════════════════════════════════════════════════
SECTION 4: RESOURCE RECOMMENDATION ENGINE API
═══════════════════════════════════════════════════════════════════════════════

Class: ResourceRecommendationEngine
────────────────────────────────────

Constructor:
  ResourceRecommendationEngine(safe_harbor_module: SafeHarborModule)
    safe_harbor_module: Trained SafeHarborModule instance

Methods:

  1. recommend(incident: Dict) → ResourceRecommendation
     ──────────────────────────────────────────────────
     Generate full resource recommendation.
     
     Args:
       incident: Dictionary with fields:
         - id: Incident ID
         - event_type: 'unplanned', etc.
         - latitude: Incident latitude
         - longitude: Incident longitude
         - event_cause: 'vehicle_breakdown', 'accident', etc.
         - veh_type_grouped: Vehicle category
         - priority_numeric: 1 (low), 2 (medium), 3 (high)
         - zone: Administrative zone
         - junction: Nearby junction
     
     Returns:
       ResourceRecommendation object with:
         - incident_id, incident_type, timestamp
         - harbor_recommendation: HarborRecommendation or None
         - suggested_crew_type: e.g., "Traffic Police + Towing"
         - suggested_vehicle_type: e.g., "Tow Truck"
         - estimated_arrival_time_minutes: float
         - priority_numeric, priority_label
         - operator_message: Full formatted message
     
     Example:
       rec = engine.recommend(incident_dict)
       dashboard.display(rec.operator_message)

  2. get_metrics() → Dict
     ────────────────────
     Returns recommendation metrics.
     
     Returns:
       Dictionary with keys:
         - total_recommendations: Total recommendations issued
         - recommendations_with_harbor: Recommendations with safe harbor
         - recommendations_acted_upon: Recommendations operator accepted
     
     Example:
       metrics = engine.get_metrics()
       acceptance_rate = (metrics['recommendations_acted_upon'] / 
                         metrics['total_recommendations']) * 100


═══════════════════════════════════════════════════════════════════════════════
SECTION 5: OPERATOR DASHBOARD API
═══════════════════════════════════════════════════════════════════════════════

Class: OperatorDashboard
────────────────────────

Static Methods:

  1. format_recommendation_card(rec: ResourceRecommendation, location_text: str) → Dict
     ──────────────────────────────────────────────────────────────────────────────
     Format recommendation as dashboard card (JSON).
     
     Args:
       rec: ResourceRecommendation object
       location_text: Human-readable location (e.g., "HSR Layout - 19th Main")
     
     Returns:
       Dictionary with keys:
         - incident_id, priority, timestamp, location
         - message: Operator-friendly text
         - harbor_recommendation: Details object
         - suggested_crew, suggested_vehicle, eta_minutes
         - action_buttons: ["Acknowledge", "Dispatch", "More Info"]
     
     Example:
       card = OperatorDashboard.format_recommendation_card(
           rec, 
           "HSR Layout - 19th Main Road"
       )
       dashboard_ui.update_card(card)

  2. format_map_overlay(rec: ResourceRecommendation) → Dict
     ──────────────────────────────────────────────────────
     Format recommendation as map layers.
     
     Returns:
       Dictionary with key 'layers' containing:
         - incident (red marker)
         - safe_harbor (green marker)
         - line (blue route)
     
     Example:
       map_data = OperatorDashboard.format_map_overlay(rec)
       map_ui.add_layers(map_data['layers'])


═══════════════════════════════════════════════════════════════════════════════
SECTION 6: GEOSPATIAL UTILITIES
═══════════════════════════════════════════════════════════════════════════════

Class: GeoUtils
───────────────

Static Methods:

  1. haversine_distance(lat1, lon1, lat2, lon2) → float
     ──────────────────────────────────────────────────
     Calculate distance between two points.
     
     Returns: Distance in meters
     
     Example:
       dist = GeoUtils.haversine_distance(12.92, 77.64, 12.93, 77.65)
       print(f"Distance: {dist:.1f}m")

  2. bearing(lat1, lon1, lat2, lon2) → float
     ──────────────────────────────────────
     Calculate compass bearing from point 1 to point 2.
     
     Returns: Bearing in degrees (0-360, 0=North)
     
     Example:
       bearing = GeoUtils.bearing(12.92, 77.64, 12.93, 77.65)
       print(f"Bearing: {bearing:.0f}°")

  3. bearing_to_direction(bearing: float) → str
     ──────────────────────────────────────────
     Convert bearing to cardinal direction.
     
     Returns: "N", "NE", "E", "SE", "S", "SW", "W", "NW", etc.
     
     Example:
       direction = GeoUtils.bearing_to_direction(45.0)
       print(f"Direction: {direction}")  # "NE"


═══════════════════════════════════════════════════════════════════════════════
SECTION 7: DATA CLASSES
═══════════════════════════════════════════════════════════════════════════════

DataClass: HarborRecommendation
────────────────────────────────

Fields:
  incident_id: str                    # Incident unique ID
  incident_lat: float                 # Incident latitude
  incident_lon: float                 # Incident longitude
  nearest_harbor_id: str              # Recommended harbor ID
  nearest_harbor_lat: float           # Harbor latitude
  nearest_harbor_lon: float           # Harbor longitude
  distance_meters: float              # Distance from incident to harbor
  bearing: float                      # Compass bearing (0-360°)
  confidence: float                   # Confidence score (0.0-1.0)
  recommendation_text: str            # Operator-friendly message
  zone: str | None                    # Administrative zone
  junction: str | None                # Nearby junction


DataClass: SafeHarbor
──────────────────────

Fields:
  harbor_id: str                      # Unique harbor ID (e.g., "SH0001")
  center_lat: float                   # Harbor center latitude
  center_lon: float                   # Harbor center longitude
  radius_meters: float                # Cluster radius in meters
  num_incidents: int                  # Number of incidents clustered
  cluster_label: int                  # DBSCAN label
  vehicle_types: List[str]            # Vehicles resolved here
  causes: List[str]                   # Event causes resolved here
  avg_resolution_time_minutes: float  # Average resolution duration
  resolution_locations: List[Dict]    # All resolution points
  zone: str | None                    # Administrative zone
  junction: str | None                # Nearby junction
  confidence_score: float             # Confidence (0.0-1.0)


═══════════════════════════════════════════════════════════════════════════════
SECTION 8: EXAMPLE: END-TO-END WORKFLOW
═══════════════════════════════════════════════════════════════════════════════

#!/usr/bin/env python3

import pandas as pd
from safe_harbor_identifier import (
    SafeHarborClusterer,
    SafeHarborStore,
    SafeHarborRecommender,
)
from resource_recommendation_engine import (
    SafeHarborModule,
    ResourceRecommendationEngine,
    OperatorDashboard,
)

# ============================================================
# PHASE 1: TRAINING (Run once, offline)
# ============================================================

print("Training phase...")

df = pd.read_csv('incidents_6_months.csv')

safe_harbor = SafeHarborModule(eps_meters=50.0, min_samples=3)
stats = safe_harbor.train(df)

print(f"✅ Trained on {stats['total_incidents']} incidents")
print(f"   Discovered {stats['total_harbors']} safe harbors")

# Save model
import pickle
with open('safe_harbor_model.pkl', 'wb') as f:
    pickle.dump(safe_harbor, f)

# Export for visualization
safe_harbor.export_geojson('safe_harbors.geojson')

# ============================================================
# PHASE 2: DEPLOYMENT (Run at startup)
# ============================================================

print("Deploying inference engine...")

# Load trained model
with open('safe_harbor_model.pkl', 'rb') as f:
    safe_harbor = pickle.load(f)

engine = ResourceRecommendationEngine(safe_harbor)

# ============================================================
# PHASE 3: OPERATION (Run per incident)
# ============================================================

def handle_breakdown_incident(incident_raw):
    """Process a new vehicle breakdown incident."""
    
    # Convert raw incident to standard format
    incident = {
        'id': incident_raw['incident_id'],
        'event_type': 'unplanned',
        'latitude': incident_raw['lat'],
        'longitude': incident_raw['lon'],
        'event_cause': 'vehicle_breakdown',
        'veh_type_grouped': incident_raw['vehicle_type'],
        'priority_numeric': incident_raw['priority'],
        'zone': incident_raw['zone'],
        'junction': incident_raw['junction'],
    }
    
    # Get recommendation
    rec = engine.recommend(incident)
    
    # Format for dashboard
    location_text = f"{incident['zone']} - {incident['junction']}"
    card = OperatorDashboard.format_recommendation_card(rec, location_text)
    
    # Format for map
    map_data = OperatorDashboard.format_map_overlay(rec)
    
    # Send to UI
    dashboard_ui.display_card(card)
    dashboard_ui.update_map(map_data)
    
    # Log recommendation
    logger.info(f"Recommended: {rec.operator_message}")
    
    return rec

# Example incident
raw_incident = {
    'incident_id': 'FKID000001',
    'lat': 12.9218755,
    'lon': 77.6451585,
    'vehicle_type': 'heavy_vehicle',
    'priority': 2,
    'zone': 'HSR Layout',
    'junction': '19th Main Road',
}

recommendation = handle_breakdown_incident(raw_incident)

print(f"Recommendation: {recommendation.operator_message}")
print(f"Confidence: {recommendation.confidence:.1%}")


═══════════════════════════════════════════════════════════════════════════════
SECTION 9: COMMON PATTERNS
═══════════════════════════════════════════════════════════════════════════════

PATTERN 1: Filter recommendations by confidence
────────────────────────────────────────────────

rec = engine.recommend(incident)

if rec and rec.harbor_recommendation:
    harbor_rec = rec.harbor_recommendation
    
    if harbor_rec.confidence >= 0.6:
        print("✅ High confidence - show recommendation")
        show_recommendation(rec)
    elif harbor_rec.confidence >= 0.3:
        print("⚠️  Medium confidence - show as secondary")
        show_secondary_option(rec)
    else:
        print("❌ Low confidence - skip recommendation")


PATTERN 2: Multiple recommendation options
──────────────────────────────────────────

from safe_harbor_identifier import GeoUtils

incident_lat = 12.9218755
incident_lon = 77.6451585

nearby_harbors = safe_harbor.store.harbors_near(
    incident_lat, 
    incident_lon, 
    radius=2000.0
)

options = []
for harbor in nearby_harbors[:3]:
    dist = GeoUtils.haversine_distance(
        incident_lat, incident_lon,
        harbor.center_lat, harbor.center_lon
    )
    options.append({
        'harbor_id': harbor.harbor_id,
        'distance': dist,
        'confidence': harbor.confidence_score,
    })

dashboard.show_options(options)


PATTERN 3: Track recommendation effectiveness
──────────────────────────────────────────────

from resource_recommendation_engine import MetricsCollector

metrics = MetricsCollector(engine)

# Periodically capture metrics
snapshot = metrics.capture(
    total_incidents=28500,
    breakdowns_detected=11400
)

print(f"Acceptance rate: {snapshot.action_rate:.1%}")

# Log to monitoring system
monitoring.log_metric('recommendation_acceptance', snapshot.action_rate)


PATTERN 4: A/B test parameter tuning
────────────────────────────────────

variants = [
    SafeHarborModule(eps_meters=30.0, min_samples=4),   # Tight clustering
    SafeHarborModule(eps_meters=50.0, min_samples=3),   # Current
    SafeHarborModule(eps_meters=100.0, min_samples=2),  # Loose clustering
]

results = {}

for variant in variants:
    variant.train(historical_df)
    engine = ResourceRecommendationEngine(variant)
    
    # Run test incidents
    coverage = test_coverage(engine, test_incidents)
    acceptance = test_acceptance(engine, test_incidents)
    
    results[str(variant)] = {
        'coverage': coverage,
        'acceptance': acceptance,
    }

# Compare results
best = max(results.items(), key=lambda x: x[1]['acceptance'])
print(f"Best variant: {best[0]} with acceptance {best[1]['acceptance']:.1%}")


═══════════════════════════════════════════════════════════════════════════════
SECTION 10: TROUBLESHOOTING QUICK FIXES
═══════════════════════════════════════════════════════════════════════════════

Problem: No harbors discovered
Fix 1: Check data - need at least 30 valid breakdowns
       valid = len(df[(df['event_cause']=='vehicle_breakdown') & 
                      (df['resolved_at_latitude'].notna())])
Fix 2: Loosen eps_meters - try 80 or 100 instead of 50
Fix 3: Lower min_samples - try 2 instead of 3

Problem: Recommendations too far away (>2km)
Fix 1: Increase max_distance in recommend()
Fix 2: Show multiple options instead of single harbor
Fix 3: Accept areas without nearby harbors as "isolated incidents"

Problem: Confidence scores very low (<0.3)
Fix 1: More training data (extend date range)
Fix 2: Adjust confidence formula (currently: min(1.0, incidents/10))
Fix 3: Filter low-confidence recommendations entirely

Problem: Too many singleton harbors
Fix 1: Increase min_samples (from 3 to 4-5)
Fix 2: Increase eps_meters (from 50 to 70-80)
Fix 3: More training data

═══════════════════════════════════════════════════════════════════════════════
END OF QUICK REFERENCE
"""
