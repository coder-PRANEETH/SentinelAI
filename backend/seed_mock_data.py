# backend/seed_mock_data.py
import random
from datetime import datetime, timezone, timedelta
from app import create_app
from models.base import db
from models.incidents import Incident
from models.predictions import Prediction
from models.dispatches import Dispatch
from models.stations import Station

app = create_app()

with app.app_context():
    print("Seeding mock data...")
    
    # 1. Create Stations
    if Station.query.count() == 0:
        stations = [
            Station(station_id="ST-001", station_name="Central Station", latitude=12.9716, longitude=77.5946, available_officers=15, available_vehicles=5),
            Station(station_id="ST-002", station_name="South Station", latitude=12.9121, longitude=77.6446, available_officers=10, available_vehicles=3),
            Station(station_id="ST-003", station_name="East Station", latitude=12.9915, longitude=77.7152, available_officers=12, available_vehicles=4),
        ]
        db.session.add_all(stations)
        db.session.commit()
    else:
        stations = Station.query.all()

    st_ids = [s.station_id for s in stations]
    
    # 2. Create Incidents
    if Incident.query.count() == 0:
        now = datetime.now(timezone.utc)
        
        for i in range(25):
            # Mix of statuses
            status = random.choice(["IN_PROGRESS", "CLOSED", "CLOSED", "RESOURCES_ASSIGNED"])
            created_at = now - timedelta(days=random.randint(0, 28), hours=random.randint(1, 23))
            resolved_at = created_at + timedelta(minutes=random.randint(15, 120)) if status == "CLOSED" else None
            
            inc = Incident(
                incident_id=f"INC-2026-{i+1:06d}",
                incident_type=random.choice(["Accident", "Vehicle Breakdown", "Signal Failure", "Waterlogging"]),
                status=status,
                location="Mock Location",
                latitude=12.9716 + random.uniform(-0.05, 0.05),
                longitude=77.5946 + random.uniform(-0.05, 0.05),
                corridor=random.choice(["ORR", "Hosur Road", "Tumkur Road", "Silk Board"]),
                created_at=created_at,
                resolved_at=resolved_at
            )
            db.session.add(inc)
            db.session.flush() # get id
            
            # Prediction
            pred = Prediction(
                incident_id=inc.incident_id,
                predicted_priority=random.choice(["P1", "P2", "P3", "P4"]),
                predicted_resolution_minutes=random.randint(20, 90),
                road_closure_recommendation=random.choice(["Yes", "No", "No", "No"]),
                priority_confidence=random.uniform(0.7, 0.99)
            )
            db.session.add(pred)
            
            # Dispatch
            if status in ["IN_PROGRESS", "RESOURCES_ASSIGNED", "CLOSED"]:
                disp = Dispatch(
                    dispatch_id=f"DIS-2026-{i+1:06d}",
                    incident_id=inc.incident_id,
                    station_id=random.choice(st_ids),
                    officers_dispatched=random.randint(1, 4),
                    vehicles_dispatched=1,
                    tow_trucks_dispatched=random.randint(0, 1),
                    dispatched_at=created_at + timedelta(minutes=random.randint(2, 5)),
                    released_at=resolved_at
                )
                db.session.add(disp)

        
        db.session.commit()
        print("Mock data seeded successfully!")
    else:
        print("Data already exists. Skipping.")
