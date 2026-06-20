"""
SentinelAI Resource Recommendation Engine
==========================================
Integrates Safe Harbor Identifier into SentinelAI's incident response pipeline.

COMPONENTS:
1. SafeHarborModule: Wraps clusterer + store + recommender
2. ResourceRecommendationEngine: Unified interface for operator
3. OperatorDashboard: Real-time recommendations UI schema
4. MetricsCollector: Track recommendation effectiveness
"""

import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import asdict, dataclass
import pandas as pd
import numpy as np

from safe_harbor_identifier import (
    SafeHarborClusterer,
    SafeHarborStore,
    SafeHarborRecommender,
    SafeHarborVisualizer,
    GeoUtils,
    HarborRecommendation,
)


@dataclass
class ResourceRecommendation:
    """Unified resource recommendation (extends beyond safe harbors)."""
    incident_id: str
    incident_type: str
    timestamp: str
    
    # Safe harbor recommendation
    harbor_recommendation: Optional[HarborRecommendation] = None
    
    # Other resources (crew, vehicle type, etc.)
    suggested_crew_type: Optional[str] = None
    suggested_vehicle_type: Optional[str] = None
    estimated_arrival_time_minutes: Optional[float] = None
    
    # Priority
    priority_numeric: int = 1
    priority_label: str = "low"
    
    # Operator message
    operator_message: str = ""


class SafeHarborModule:
    """
    Encapsulates Safe Harbor clustering and recommendation.
    Training happens once, inference many times.
    """
    
    def __init__(self, eps_meters: float = 50.0, min_samples: int = 3):
        self.clusterer = SafeHarborClusterer(eps_meters=eps_meters, min_samples=min_samples)
        self.store = SafeHarborStore()
        self.recommender = SafeHarborRecommender(self.store)
        self.is_trained = False
    
    def train(self, df: pd.DataFrame) -> Dict:
        """
        One-time training: cluster all historical breakdown incidents.
        Returns training stats.
        """
        print("🚀 Training Safe Harbor Model...")
        
        harbors = self.clusterer.cluster(df)
        self.store.add_harbors(harbors)
        
        self.is_trained = True
        
        stats = self.store.get_stats()
        print(f"✅ Training complete: {stats['total_harbors']} harbors, {stats['total_incidents']} incidents")
        
        return stats
    
    def recommend(self, incident_id: str, incident_lat: float, incident_lon: float,
                  zone: Optional[str] = None, junction: Optional[str] = None) -> Optional[HarborRecommendation]:
        """
        Real-time inference: recommend nearest safe harbor.
        """
        if not self.is_trained:
            return None
        
        return self.recommender.recommend(
            incident_id=incident_id,
            incident_lat=incident_lat,
            incident_lon=incident_lon,
            zone=zone,
            junction=junction
        )
    
    def get_stats(self) -> Dict:
        return self.store.get_stats()
    
    def export_geojson(self, filepath: str) -> None:
        """Export all harbors as GeoJSON."""
        geojson = SafeHarborVisualizer.to_geojson(self.store.harbors)
        with open(filepath, 'w') as f:
            json.dump(geojson, f, indent=2)


class ResourceRecommendationEngine:
    """
    Unified resource recommendation engine for SentinelAI.
    
    Provides:
    - Safe harbor location for breakdowns
    - Suggested crew type & vehicle
    - ETA estimates
    - Operator-friendly messages
    """
    
    def __init__(self, safe_harbor_module: SafeHarborModule):
        self.safe_harbor = safe_harbor_module
        self.metrics = {
            "total_recommendations": 0,
            "recommendations_with_harbor": 0,
            "recommendations_acted_upon": 0,
        }
    
    def recommend(self, incident: Dict) -> ResourceRecommendation:
        """
        Generate full recommendation for an incident.
        
        Input incident dict should have:
        - id, event_type, latitude, longitude
        - veh_type_grouped, priority_numeric, event_cause
        - zone, junction (optional)
        """
        incident_id = incident.get('id')
        incident_lat = incident.get('latitude')
        incident_lon = incident.get('longitude')
        event_type = incident.get('event_type', 'unplanned')
        event_cause = incident.get('event_cause', 'unknown')
        veh_type = incident.get('veh_type_grouped', 'unknown')
        priority_numeric = incident.get('priority_numeric', 1)
        zone = incident.get('zone')
        junction = incident.get('junction')
        
        recommendation = ResourceRecommendation(
            incident_id=incident_id,
            incident_type=event_type,
            timestamp=datetime.now().isoformat(),
            priority_numeric=priority_numeric,
            priority_label=self._priority_label(priority_numeric)
        )
        
        # Safe harbor (for breakdowns only)
        if event_cause == 'vehicle_breakdown':
            harbor_rec = self.safe_harbor.recommend(
                incident_id=incident_id,
                incident_lat=incident_lat,
                incident_lon=incident_lon,
                zone=zone,
                junction=junction
            )
            recommendation.harbor_recommendation = harbor_rec
            self.metrics["recommendations_with_harbor"] += 1
        
        # Crew & vehicle suggestions
        recommendation.suggested_crew_type = self._suggest_crew(event_cause, veh_type)
        recommendation.suggested_vehicle_type = self._suggest_vehicle(event_cause)
        recommendation.estimated_arrival_time_minutes = self._estimate_eta(priority_numeric)
        
        # Operator message
        recommendation.operator_message = self._build_operator_message(recommendation)
        
        self.metrics["total_recommendations"] += 1
        
        return recommendation
    
    def _priority_label(self, numeric: int) -> str:
        mapping = {1: "low", 2: "medium", 3: "high"}
        return mapping.get(numeric, "low")
    
    def _suggest_crew(self, event_cause: str, veh_type: str) -> str:
        """Suggest crew type based on incident cause."""
        if event_cause == 'vehicle_breakdown':
            return "Traffic Police + Towing Crew"
        elif event_cause == 'tree_fall':
            return "Traffic Police + Tree Removal Crew"
        elif event_cause == 'accident':
            return "Traffic Police + Ambulance + Fire"
        else:
            return "Traffic Police"
    
    def _suggest_vehicle(self, event_cause: str) -> str:
        """Suggest vehicle type."""
        if event_cause == 'vehicle_breakdown':
            return "Tow Truck"
        elif event_cause == 'tree_fall':
            return "JCB / Crane"
        else:
            return "Traffic Police Vehicle"
    
    def _estimate_eta(self, priority_numeric: int) -> float:
        """Estimate ETA in minutes based on priority."""
        eta_map = {1: 30.0, 2: 15.0, 3: 5.0}
        return eta_map.get(priority_numeric, 30.0)
    
    def _build_operator_message(self, rec: ResourceRecommendation) -> str:
        """Build human-friendly operator message."""
        msg_parts = []
        
        # Base message
        msg_parts.append(f"🚨 [{rec.priority_label.upper()}] {rec.incident_type}")
        
        # Crew suggestion
        if rec.suggested_crew_type:
            msg_parts.append(f"👥 Deploy: {rec.suggested_crew_type}")
        
        # Safe harbor
        if rec.harbor_recommendation:
            msg_parts.append(f"🛣️  {rec.harbor_recommendation.recommendation_text}")
        
        # ETA
        if rec.estimated_arrival_time_minutes:
            msg_parts.append(f"⏱️  ETA: {rec.estimated_arrival_time_minutes:.0f} minutes")
        
        return " | ".join(msg_parts)
    
    def get_metrics(self) -> Dict:
        return self.metrics


@dataclass
class OperatorDashboardCard:
    """Card schema for operator dashboard."""
    incident_id: str
    priority: str
    timestamp: str
    location_text: str
    recommendation: ResourceRecommendation
    action_buttons: List[str]  # ["Acknowledge", "Dispatch", "More Info"]


class OperatorDashboard:
    """Formats recommendations for operator UI."""
    
    @staticmethod
    def format_recommendation_card(rec: ResourceRecommendation, location_text: str) -> Dict:
        """Format recommendation as dashboard card (JSON schema)."""
        return {
            "incident_id": rec.incident_id,
            "priority": rec.priority_label,
            "timestamp": rec.timestamp,
            "location": location_text,
            "message": rec.operator_message,
            "harbor_recommendation": asdict(rec.harbor_recommendation) if rec.harbor_recommendation else None,
            "suggested_crew": rec.suggested_crew_type,
            "suggested_vehicle": rec.suggested_vehicle_type,
            "eta_minutes": rec.estimated_arrival_time_minutes,
            "action_buttons": ["Acknowledge", "Dispatch", "More Info"],
        }
    
    @staticmethod
    def format_map_overlay(rec: ResourceRecommendation) -> Dict:
        """Format as map layer (incident + harbor recommendation)."""
        layers = []
        
        # Incident location
        if rec.harbor_recommendation:
            layers.append({
                "type": "incident",
                "lat": rec.harbor_recommendation.incident_lat,
                "lon": rec.harbor_recommendation.incident_lon,
                "color": "red",
                "label": f"Incident: {rec.incident_id}"
            })
            
            # Safe harbor target
            layers.append({
                "type": "safe_harbor",
                "lat": rec.harbor_recommendation.nearest_harbor_lat,
                "lon": rec.harbor_recommendation.nearest_harbor_lon,
                "color": "green",
                "label": f"Safe Harbor ({rec.harbor_recommendation.distance_meters:.0f}m)",
                "radius_meters": 50
            })
            
            # Line from incident to harbor
            layers.append({
                "type": "line",
                "from": (rec.harbor_recommendation.incident_lat, rec.harbor_recommendation.incident_lon),
                "to": (rec.harbor_recommendation.nearest_harbor_lat, rec.harbor_recommendation.nearest_harbor_lon),
                "color": "blue",
                "label": f"Direction: {rec.harbor_recommendation.bearing:.0f}°"
            })
        
        return {"layers": layers}


@dataclass
class MetricsSnapshot:
    """Performance metrics for Safe Harbor recommendations."""
    timestamp: str
    total_incidents: int
    breakdowns_detected: int
    harbors_available: int
    recommendations_issued: int
    recommendations_acted_upon: int
    action_rate: float  # % of recommendations that led to dispatch


class MetricsCollector:
    """Track recommendation effectiveness over time."""
    
    def __init__(self, engine: ResourceRecommendationEngine):
        self.engine = engine
        self.snapshots: List[MetricsSnapshot] = []
    
    def capture(self, total_incidents: int, breakdowns_detected: int) -> MetricsSnapshot:
        """Capture a metrics snapshot."""
        harbor_stats = self.engine.safe_harbor.get_stats()
        engine_metrics = self.engine.get_metrics()
        
        action_rate = 0.0
        if engine_metrics["recommendations_with_harbor"] > 0:
            action_rate = (engine_metrics["recommendations_acted_upon"] / 
                          engine_metrics["recommendations_with_harbor"])
        
        snapshot = MetricsSnapshot(
            timestamp=datetime.now().isoformat(),
            total_incidents=total_incidents,
            breakdowns_detected=breakdowns_detected,
            harbors_available=harbor_stats.get('total_harbors', 0),
            recommendations_issued=engine_metrics["total_recommendations"],
            recommendations_acted_upon=engine_metrics["recommendations_acted_upon"],
            action_rate=action_rate
        )
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def report(self) -> str:
        """Generate metrics report."""
        if not self.snapshots:
            return "No metrics collected yet."
        
        latest = self.snapshots[-1]
        
        report = f"""
📊 Safe Harbor Recommendation Metrics
=====================================
Timestamp: {latest.timestamp}
Total Incidents: {latest.total_incidents}
Breakdowns: {latest.breakdowns_detected}
Safe Harbors Available: {latest.harbors_available}
Recommendations Issued: {latest.recommendations_issued}
Recommendations Acted Upon: {latest.recommendations_acted_upon}
Action Rate: {latest.action_rate:.1%}
"""
        return report


# ============================================================================
# EXAMPLE INTEGRATION WITH SENTINELAI WORKFLOW
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("SentinelAI Resource Recommendation Engine + Safe Harbor Identifier")
    print("=" * 80)
    
    # Load dataset
    df = pd.read_csv('/home/claude/astram_sample.csv')
    print(f"\n📂 Loaded {len(df)} incidents")
    
    # Initialize Safe Harbor Module
    print("\n🔧 Initializing Safe Harbor Module...")
    safe_harbor = SafeHarborModule(eps_meters=50.0, min_samples=3)
    stats = safe_harbor.train(df)
    
    # Initialize Resource Recommendation Engine
    print("\n🔧 Initializing Resource Recommendation Engine...")
    engine = ResourceRecommendationEngine(safe_harbor)
    
    # Initialize Metrics Collector
    print("\n📊 Initializing Metrics Collector...")
    metrics = MetricsCollector(engine)
    
    # Process some sample incidents
    print("\n" + "=" * 80)
    print("GENERATING RECOMMENDATIONS FOR SAMPLE INCIDENTS")
    print("=" * 80)
    
    breakdowns = df[df['event_cause'] == 'vehicle_breakdown'].head(5)
    
    for idx, incident in breakdowns.iterrows():
        incident_dict = incident.to_dict()
        
        print(f"\n\n🚨 Incident: {incident_dict['id']}")
        print(f"   Location: {incident_dict['latitude']:.4f}, {incident_dict['longitude']:.4f}")
        print(f"   Cause: {incident_dict['event_cause']}")
        print(f"   Vehicle: {incident_dict['veh_type_grouped']}")
        
        # Generate recommendation
        rec = engine.recommend(incident_dict)
        
        # Dashboard card
        location_text = f"{incident_dict.get('zone', 'Unknown')} - {incident_dict.get('junction', 'Unknown')}"
        card = OperatorDashboard.format_recommendation_card(rec, location_text)
        
        print(f"\n   📋 OPERATOR MESSAGE:")
        print(f"      {rec.operator_message}")
        
        print(f"\n   🗺️  MAP OVERLAY:")
        map_data = OperatorDashboard.format_map_overlay(rec)
        print(f"      Layers: {len(map_data['layers'])}")
        for layer in map_data['layers']:
            print(f"        - {layer['type']}: {layer.get('label', '')}")
    
    # Capture metrics
    print("\n\n" + "=" * 80)
    print("FINAL METRICS")
    print("=" * 80)
    
    breakdown_count = len(df[df['event_cause'] == 'vehicle_breakdown'])
    snapshot = metrics.capture(total_incidents=len(df), breakdowns_detected=breakdown_count)
    
    print(metrics.report())
    
    # Export
    print("\n💾 Exporting safe harbors to GeoJSON...")
    safe_harbor.export_geojson('/home/claude/safe_harbors_final.geojson')
    print("   ✅ Saved: /home/claude/safe_harbors_final.geojson")
