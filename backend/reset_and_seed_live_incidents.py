import json
import random
import os
from datetime import datetime, timezone, timedelta
from app import create_app
from models.base import db
from models.incidents import Incident
from models.predictions import Prediction
from models.dispatches import Dispatch
from models.incident_feedback import IncidentFeedback
from models.stations import Station

try:
    app = create_app()
    with app.app_context():
        db.engine.connect()
    USE_MOCK = False
except Exception:
    print("Database connection failed. Running in MOCK mode to generate data files.")
    USE_MOCK = True

def backup_incidents():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_incidents_{timestamp}.json"
    
    if USE_MOCK:
        data = [{"incident_id": "INC-2026-000001", "status": "CLOSED"}]
    else:
        incidents = Incident.query.all()
        data = [inc.to_dict() for inc in incidents]
        
    with open(backup_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Backed up {len(data)} incidents to {backup_file}")
    return backup_file

def clear_incidents():
    if USE_MOCK:
        print("MOCK: Cleared 25 incidents (and related records).")
        return 25
        
    # Order matters due to foreign key constraints:
    # 1. dispatches (RESTRICT)
    # 2. predictions (CASCADE, but safe to delete)
    # 3. incident_feedback (CASCADE, but safe to delete)
    # 4. incidents
    
    Dispatch.query.delete()
    Prediction.query.delete()
    IncidentFeedback.query.delete()
    deleted = Incident.query.delete()
    db.session.commit()
    print(f"Cleared {deleted} incidents (and related records).")
    return deleted

def seed_incidents():
    if USE_MOCK:
        st_ids = ["ST-001", "ST-002", "ST-003"]
    else:
        stations = Station.query.all()
        if not stations:
            stations = [
                Station(station_id="ST-001", station_name="Central Station", latitude=12.9716, longitude=77.5946, available_officers=15, available_vehicles=5),
                Station(station_id="ST-002", station_name="South Station", latitude=12.9121, longitude=77.6446, available_officers=10, available_vehicles=3),
                Station(station_id="ST-003", station_name="East Station", latitude=12.9915, longitude=77.7152, available_officers=12, available_vehicles=4),
            ]
            db.session.add_all(stations)
            db.session.commit()
        st_ids = [s.station_id for s in stations]

    now = datetime.now(timezone.utc)
    
    planned_causes = ["public_event", "vip_movement", "construction"]
    unplanned_causes = ["vehicle_breakdown", "tree_fall", "accident", "water_logging", "pot_holes", "congestion", "fire", "medical_emergency"]
    
    corridors = ["Tumkur Road", "Hosur Road", "Outer Ring Road", "Bellary Road", "Old Madras Road", "Mysore Road", "Silk Board", "Peenya Metro Station"]
    
    statuses = ["REPORTED", "UNDER_ASSESSMENT", "RESOURCES_ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"]
    
    seeded_records = []
    
    for i in range(25):
        # 1-3 planned, rest unplanned
        if i < 3:
            event_cause = random.choice(planned_causes)
            incident_type = "planned_event"
            # Planned events usually high priority or at least needs closure
            req_closure = True if random.random() < 0.8 else False
            priority = "high" if req_closure else "low"
        else:
            event_cause = random.choice(unplanned_causes)
            incident_type = "unplanned_incident"
            priority = "high" if random.random() < 0.62 else "low" # ~62% high priority
            req_closure = True if event_cause in ["tree_fall", "accident"] and random.random() < 0.5 else False
            
        status = random.choice(statuses)
        # Weight towards active
        if random.random() < 0.7:
            status = random.choice(["REPORTED", "UNDER_ASSESSMENT", "RESOURCES_ASSIGNED", "IN_PROGRESS"])
            
        created_at = now - timedelta(days=random.randint(0, 2), hours=random.randint(1, 23))
        resolved_at = created_at + timedelta(minutes=random.randint(15, 120)) if status in ["RESOLVED", "CLOSED"] else None
        
        inc = Incident(
            incident_id=f"INC-2026-{i+1:06d}",
            incident_type=incident_type,
            event_cause=event_cause,
            vehicle_type=random.choice(["two_wheeler", "car", "bus", "truck", "heavy_vehicle"]),
            location="Bengaluru Junction",
            latitude=12.9716 + random.uniform(-0.1, 0.1),
            longitude=77.5946 + random.uniform(-0.1, 0.1),
            corridor=random.choice(corridors),
            status=status,
            created_at=created_at,
            reported_at=created_at,
            resolved_at=resolved_at,
            closed_at=resolved_at if status == "CLOSED" else None,
            priority_indicators=["high_traffic_impact"] if priority == "high" else []
        )
        if not USE_MOCK:
            db.session.add(inc)
            db.session.flush()
        
        # ML Prediction (to populate the dashboard queues correctly)
        pred = Prediction(
            incident_id=inc.incident_id,
            predicted_priority=priority,
            priority_confidence=random.uniform(0.7, 0.99),
            predicted_resolution_minutes=random.randint(20, 120),
            road_closure_probability=0.9 if req_closure else 0.1,
            road_closure_recommendation="Yes" if req_closure else "No",
        )
        if not USE_MOCK:
            db.session.add(pred)
        
        # Dispatch
        if status in ["RESOURCES_ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"]:
            disp = Dispatch(
                dispatch_id=f"DIS-2026-{i+1:06d}",
                incident_id=inc.incident_id,
                station_id=random.choice(st_ids),
                officers_dispatched=random.randint(1, 4),
                vehicles_dispatched=1,
                tow_trucks_dispatched=1 if event_cause in ["vehicle_breakdown", "accident"] else 0,
                dispatched_at=created_at + timedelta(minutes=random.randint(2, 5)),
                released_at=resolved_at
            )
            if not USE_MOCK:
                db.session.add(disp)
            
        seeded_records.append({"incident": inc, "prediction": pred})
            
    if not USE_MOCK:
        db.session.commit()
    print(f"Seeded 25 incidents successfully!")
    return seeded_records

if __name__ == "__main__":
    if USE_MOCK:
        backup_file = backup_incidents()
        deleted_count = clear_incidents()
        records = seed_incidents()
        
        print("\n--- SAMPLE SEEDED RECORDS ---")
        for rec in records[:5]:
            inc = rec["incident"]
            pred = rec["prediction"]
            print(f"[{inc.incident_id}] {inc.event_cause} at {inc.corridor} | Status: {inc.status} | Priority: {pred.predicted_priority}")
    else:
        with app.app_context():
            backup_file = backup_incidents()
            deleted_count = clear_incidents()
            records = seed_incidents()
            
            print("\n--- SAMPLE SEEDED RECORDS ---")
            for rec in records[:5]:
                inc = rec["incident"]
                pred = rec["prediction"]
                print(f"[{inc.incident_id}] {inc.event_cause} at {inc.corridor} | Status: {inc.status} | Priority: {pred.predicted_priority}")
