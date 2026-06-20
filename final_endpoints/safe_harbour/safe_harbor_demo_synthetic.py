#!/usr/bin/env python3
"""
Safe Harbor Identifier - Demo with Synthetic Data
==================================================

Generates realistic breakdown incident patterns to demonstrate:
1. DBSCAN clustering of vehicle resolution locations
2. Safe harbor discovery
3. Operator recommendations with contextual info
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

import sys
sys.path.insert(0, '/')

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
)


def generate_synthetic_breakdowns():
    """
    Generate realistic breakdown data for Bengaluru.
    
    Creates several clusters where vehicles are commonly pushed:
    - HSR Layout corridor (cluster 1)
    - Wilson Garden junction area (cluster 2)
    - Sankey Road area (cluster 3)
    """
    
    np.random.seed(42)
    
    records = []
    incident_id_counter = 1
    
    # Cluster 1: HSR Layout (19th Main Road)
    # Incidents: 12.9218755, 77.6451585
    # Resolved to: Left shoulder nearby
    cluster1_incidents = 8
    for i in range(cluster1_incidents):
        incident_lat = 12.9218755 + np.random.normal(0, 0.0005)
        incident_lon = 77.6451585 + np.random.normal(0, 0.0005)
        
        # Vehicles pushed to safe shoulder ~80m away
        angle = np.random.uniform(0, 2*np.pi)
        distance = np.random.uniform(30, 120)
        
        resolved_lat = incident_lat + (distance / 111000) * np.cos(angle)
        resolved_lon = incident_lon + (distance / 111000) * np.sin(angle) / np.cos(np.radians(incident_lat))
        
        records.append({
            'id': f'FKID{incident_id_counter:06d}',
            'event_type': 'unplanned',
            'latitude': incident_lat,
            'longitude': incident_lon,
            'resolved_at_latitude': resolved_lat,
            'resolved_at_longitude': resolved_lon,
            'address': "19th Main Road, HSR Layout, Bengaluru",
            'event_cause': 'vehicle_breakdown',
            'veh_type_grouped': np.random.choice(['heavy_vehicle', 'private_bus', 'two_wheeler']),
            'status': 'resolved',
            'zone': 'South East Zone',
            'junction': 'HSR Layout',
            'priority_numeric': np.random.choice([1, 2, 3]),
            'response_time_minutes': np.random.uniform(5, 20),
            'resolved_at_address': "19th Main Road, Safe shoulder, HSR Layout",
            'resolved_datetime': (datetime.now() - timedelta(days=np.random.randint(1, 90))).isoformat(),
        })
        incident_id_counter += 1
    
    # Cluster 2: Wilson Garden / Lalbagh junction
    # Incidents: 12.955622, 77.5857083
    # Resolved to: Junction safe zone
    cluster2_incidents = 10
    for i in range(cluster2_incidents):
        incident_lat = 12.955622 + np.random.normal(0, 0.0006)
        incident_lon = 77.5857083 + np.random.normal(0, 0.0006)
        
        # Vehicles pushed to junction safe area ~70m away
        angle = np.random.uniform(0, 2*np.pi)
        distance = np.random.uniform(40, 100)
        
        resolved_lat = incident_lat + (distance / 111000) * np.cos(angle)
        resolved_lon = incident_lon + (distance / 111000) * np.sin(angle) / np.cos(np.radians(incident_lat))
        
        records.append({
            'id': f'FKID{incident_id_counter:06d}',
            'event_type': 'unplanned',
            'latitude': incident_lat,
            'longitude': incident_lon,
            'resolved_at_latitude': resolved_lat,
            'resolved_at_longitude': resolved_lon,
            'address': "Lalbagh Fort Road, Wilson Garden, Bengaluru",
            'event_cause': 'vehicle_breakdown',
            'veh_type_grouped': np.random.choice(['heavy_vehicle', 'private_bus', 'auto_rickshaw']),
            'status': 'resolved',
            'zone': 'Central Zone',
            'junction': 'Lalbagh Main Gate',
            'priority_numeric': np.random.choice([1, 2, 3]),
            'response_time_minutes': np.random.uniform(10, 25),
            'resolved_at_address': "Safe shoulder, Lalbagh Fort Road",
            'resolved_datetime': (datetime.now() - timedelta(days=np.random.randint(1, 90))).isoformat(),
        })
        incident_id_counter += 1
    
    # Cluster 3: Sankey Road / Bashyam Circle
    # Incidents: 13.0061469, 77.5794348
    # Resolved to: Side road safe zone
    cluster3_incidents = 7
    for i in range(cluster3_incidents):
        incident_lat = 13.0061469 + np.random.normal(0, 0.0005)
        incident_lon = 77.5794348 + np.random.normal(0, 0.0005)
        
        # Vehicles pushed to side road ~60m away
        angle = np.random.uniform(0, 2*np.pi)
        distance = np.random.uniform(35, 90)
        
        resolved_lat = incident_lat + (distance / 111000) * np.cos(angle)
        resolved_lon = incident_lon + (distance / 111000) * np.sin(angle) / np.cos(np.radians(incident_lat))
        
        records.append({
            'id': f'FKID{incident_id_counter:06d}',
            'event_type': 'unplanned',
            'latitude': incident_lat,
            'longitude': incident_lon,
            'resolved_at_latitude': resolved_lat,
            'resolved_at_longitude': resolved_lon,
            'address': "Sankey Road, Sadashiva Nagar, Bengaluru",
            'event_cause': 'vehicle_breakdown',
            'veh_type_grouped': np.random.choice(['heavy_vehicle', 'two_wheeler', 'car']),
            'status': 'resolved',
            'zone': 'North East Zone',
            'junction': 'Bashyam Circle',
            'priority_numeric': np.random.choice([1, 2, 3]),
            'response_time_minutes': np.random.uniform(8, 18),
            'resolved_at_address': "Sankey Road, Safe shoulder",
            'resolved_datetime': (datetime.now() - timedelta(days=np.random.randint(1, 90))).isoformat(),
        })
        incident_id_counter += 1
    
    # Add some noise incidents (not close to clusters)
    noise_incidents = 3
    for i in range(noise_incidents):
        incident_lat = np.random.uniform(12.85, 13.10)
        incident_lon = np.random.uniform(77.50, 77.65)
        
        # Large random push distance
        distance = np.random.uniform(200, 500)
        angle = np.random.uniform(0, 2*np.pi)
        
        resolved_lat = incident_lat + (distance / 111000) * np.cos(angle)
        resolved_lon = incident_lon + (distance / 111000) * np.sin(angle) / np.cos(np.radians(incident_lat))
        
        records.append({
            'id': f'FKID{incident_id_counter:06d}',
            'event_type': 'unplanned',
            'latitude': incident_lat,
            'longitude': incident_lon,
            'resolved_at_latitude': resolved_lat,
            'resolved_at_longitude': resolved_lon,
            'address': "Random location, Bengaluru",
            'event_cause': 'vehicle_breakdown',
            'veh_type_grouped': 'other_vehicle',
            'status': 'resolved',
            'zone': 'Unknown',
            'junction': 'Unknown',
            'priority_numeric': 1,
            'response_time_minutes': np.random.uniform(15, 40),
            'resolved_at_address': "Random safe location",
            'resolved_datetime': (datetime.now() - timedelta(days=np.random.randint(1, 90))).isoformat(),
        })
        incident_id_counter += 1
    
    return pd.DataFrame(records)


def print_section(title):
    print("\n" + "=" * 90)
    print(f"  {title}")
    print("=" * 90 + "\n")


def main():
    print("\n")
    print("╔" + "=" * 88 + "╗")
    print("║" + " " * 25 + "🛣️  SAFE HARBOR IDENTIFIER - LIVE DEMO  🛣️ " + " " * 20 + "║")
    print("╚" + "=" * 88 + "╝")
    
    # ========================================================================
    # GENERATE SYNTHETIC DATA
    # ========================================================================
    
    print_section("STEP 1: GENERATING SYNTHETIC BREAKDOWN DATA")
    
    df = generate_synthetic_breakdowns()
    
    print(f"✅ Generated {len(df)} synthetic breakdown incidents\n")
    print(f"   Incidents by zone:")
    print(df.groupby('zone').size().to_string().replace('\n', '\n   '))
    print()
    
    # Show sample data
    print(f"   Sample incident:")
    sample = df.iloc[0]
    print(f"      ID: {sample['id']}")
    print(f"      Location: {sample['address']}")
    print(f"      Incident coords: ({sample['latitude']:.6f}, {sample['longitude']:.6f})")
    print(f"      Resolved at: ({sample['resolved_at_latitude']:.6f}, {sample['resolved_at_longitude']:.6f})")
    
    delta = GeoUtils.haversine_distance(
        sample['latitude'], sample['longitude'],
        sample['resolved_at_latitude'], sample['resolved_at_longitude']
    )
    print(f"      Push distance: {delta:.1f}m")
    
    # ========================================================================
    # CLUSTER RESOLUTION LOCATIONS
    # ========================================================================
    
    print_section("STEP 2: DBSCAN CLUSTERING (eps=50m, min_samples=3)")
    
    clusterer = SafeHarborClusterer(eps_meters=50.0, min_samples=3)
    
    valid = clusterer.prepare_incidents(df)
    print(f"✅ Valid incidents (with resolution coords): {len(valid)}")
    print(f"   Push distance range: {valid['delta_meters'].min():.1f}m to {valid['delta_meters'].max():.1f}m")
    print(f"   Median push: {valid['delta_meters'].median():.1f}m")
    print(f"   Mean push: {valid['delta_meters'].mean():.1f}m")
    
    harbors = clusterer.cluster(df)
    
    print(f"\n✅ DBSCAN discovered {len(harbors)} safe harbors!\n")
    
    # ========================================================================
    # ANALYZE SAFE HARBORS
    # ========================================================================
    
    print_section("STEP 3: SAFE HARBOR ANALYSIS")
    
    for idx, (label, harbor) in enumerate(sorted(harbors.items(), key=lambda x: -x[1].num_incidents), 1):
        print(f"\n🛣️  SAFE HARBOR #{idx}: {harbor.harbor_id}")
        print(f"   ═" * 43)
        print(f"   Location: ({harbor.center_lat:.6f}, {harbor.center_lon:.6f})")
        print(f"   Radius: {harbor.radius_meters:.1f}m")
        print(f"   Incidents clustered: {harbor.num_incidents}")
        print(f"   Confidence: {harbor.confidence_score:.1%}")
        print(f"   Zone: {harbor.zone}")
        print(f"   Junction: {harbor.junction}")
        print(f"   Vehicle types resolved: {', '.join(harbor.vehicle_types)}")
        print(f"   Avg resolution time: {harbor.avg_resolution_time_minutes:.1f} min")
        
        # Show all resolution points
        print(f"\n   Resolution points in this harbor:")
        for i, loc in enumerate(harbor.resolution_locations[:3], 1):
            print(f"      {i}. ({loc['latitude']:.6f}, {loc['longitude']:.6f}) - {loc['incident_id']}")
        if len(harbor.resolution_locations) > 3:
            print(f"      ... and {len(harbor.resolution_locations) - 3} more")
    
    # ========================================================================
    # REAL-TIME RECOMMENDATIONS
    # ========================================================================
    
    print_section("STEP 4: REAL-TIME OPERATOR RECOMMENDATIONS")
    
    store = SafeHarborStore()
    store.add_harbors(harbors)
    recommender = SafeHarborRecommender(store)
    
    # Pick a few incidents for demo
    demo_incidents = df.sample(min(5, len(df)), random_state=123)
    
    for _, incident in demo_incidents.iterrows():
        rec = recommender.recommend(
            incident_id=incident['id'],
            incident_lat=incident['latitude'],
            incident_lon=incident['longitude'],
            zone=incident['zone'],
            junction=incident['junction']
        )
        
        print(f"\n📍 Incident: {incident['id']}")
        print(f"   Location: {incident['address']}")
        print(f"   Coords: ({incident['latitude']:.6f}, {incident['longitude']:.6f})")
        
        if rec:
            print(f"\n   ✅ RECOMMENDATION:")
            print(f"      🎯 {rec.recommendation_text}")
            print(f"      📏 Distance: {rec.distance_meters:.0f}m")
            print(f"      🧭 Bearing: {rec.bearing:.0f}° ({GeoUtils.bearing_to_direction(rec.bearing)})")
            print(f"      💪 Confidence: {rec.confidence:.1%}")
        else:
            print(f"\n   ⚠️  No nearby safe harbor found (isolated incident)")
    
    # ========================================================================
    # RESOURCE RECOMMENDATION ENGINE
    # ========================================================================
    
    print_section("STEP 5: SENTINELAI RESOURCE RECOMMENDATION ENGINE")
    
    safe_harbor_module = SafeHarborModule(eps_meters=50.0, min_samples=3)
    safe_harbor_module.train(df)
    
    engine = ResourceRecommendationEngine(safe_harbor_module)
    
    # Generate full recommendations
    demo_incidents_full = df.sample(min(3, len(df)), random_state=456)
    
    for _, incident in demo_incidents_full.iterrows():
        incident_dict = incident.to_dict()
        
        rec = engine.recommend(incident_dict)
        
        print(f"\n🚨 INCIDENT: {rec.incident_id}")
        print(f"   Type: {rec.incident_type} | Priority: {rec.priority_label.upper()}")
        print(f"\n   OPERATOR MESSAGE:")
        print(f"   ┌" + "─" * 85 + "┐")
        print(f"   │ {rec.operator_message:<84}│")
        print(f"   └" + "─" * 85 + "┘")
        print(f"\n   RESOURCE ALLOCATION:")
        print(f"      👥 Crew: {rec.suggested_crew_type}")
        print(f"      🚗 Vehicle: {rec.suggested_vehicle_type}")
        print(f"      ⏱️  ETA: {rec.estimated_arrival_time_minutes:.0f} minutes")
    
    # ========================================================================
    # EXPORT GEOJSON FOR MAPPING
    # ========================================================================
    
    print_section("STEP 6: EXPORTING GEOJSON FOR MAPPING")
    
    geojson = SafeHarborVisualizer.to_geojson(store.harbors)
    
    filepath = 'safe_harbors_final.geojson'
    with open(filepath, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"✅ Exported {len(geojson['features'])} safe harbors to GeoJSON\n")
    print(f"   File: {filepath}")
    print(f"   Size: {len(json.dumps(geojson))} bytes")
    
    print(f"\n   Sample feature (first safe harbor):")
    if geojson['features']:
        feat = geojson['features'][0]
        print(f"      ID: {feat['id']}")
        print(f"      Coords: {feat['geometry']['coordinates']}")
        print(f"      Incidents: {feat['properties']['num_incidents']}")
        print(f"      Radius: {feat['properties']['radius_meters']:.0f}m")
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    
    print_section("OPERATIONAL IMPACT SUMMARY")
    
    stats = store.get_stats()
    
    print(f"""
✅ SAFE HARBOR IDENTIFIER DEPLOYED

COVERAGE METRICS:
  • Total safe harbors discovered: {stats['total_harbors']}
  • Total breakdown incidents analyzed: {stats['total_incidents']}
  • Average cluster size: {stats['avg_cluster_size']:.1f} incidents per harbor
  • Average safe zone radius: {stats['avg_radius_meters']:.0f}m

OPERATIONAL BENEFITS:
  ✅ Operators get real-time location recommendations
  ✅ "Push vehicle to safe harbor 85m East" (specific + actionable)
  ✅ Historical confidence scores (0.0-1.0)
  ✅ Zone & junction context automatically provided
  ✅ Vehicle types & zones clustered intelligently

DEPLOYMENT:
  • Dashboard integration: Ready for operator UI
  • Map visualization: GeoJSON exported and ready
  • Recommendation engine: Integrated with SentinelAI
  • Metrics tracking: Action rates, recommendation acceptance
  
NEXT STEPS:
  1. Deploy to SentinelAI dashboard
  2. Connect to live incident stream
  3. Monitor recommendation acceptance rate
  4. A/B test eps_meters (30m vs 50m vs 100m)
  5. Fine-tune min_samples based on traffic patterns
""")
    
    print("=" * 90)
    print()


if __name__ == "__main__":
    main()
