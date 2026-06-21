import requests
import json
import sqlite3
import psycopg2
import time
import uuid

BACKEND_DATABASE_URL = "postgresql://sentinel:sentinel@localhost:5432/sentinelai"

def check_db_for_incident(incident_id):
    res = requests.get("http://127.0.0.1:5001/incidents")
    incidents = res.json()
    
    print("\n--- Latest Incidents via API ---")
    found = None
    for r in incidents[:5]:
        print(f"{r.get('incident_id')} - {r.get('incident_type')} - {r.get('status')}")
        if r.get('incident_id') == incident_id:
            found = r
    return found

def test_manual_form():
    print("\n[1] Submitting Manual Incident to final_endpoints/predict...")
    payload = {
        "incident_type": "vehicle_breakdown",
        "event_type_grouped": "vehicle_breakdown",
        "event_cause": "tyre_puncture",
        "corridor": "Tumkur Road",
        "location": "Tumkur Road",
        "police_station_grouped": "Peenya",
        "vehicle_type": "car",
        "veh_type_grouped": "light",
        "raw_transcript": "E2E Manual Form Test: Flat tire on Tumkur road",
        "day_of_week": "Monday",
        "latitude": 13.02,
        "longitude": 77.56,
        "location_cluster": 3,
        "hour_of_day": 14,
        "month": 6,
        "is_peak_hour": 0,
        "is_weekend": 0,
        "is_cascaded": 0,
        "cascade_size": 1
    }
    
    res = requests.post("http://127.0.0.1:5000/predict", json=payload)
    print("Response Status:", res.status_code)
    try:
        data = res.json()
        print("Predictions:", data.get("predictions"))
        incident_id = data.get("incident_id")
        print("Incident ID:", incident_id)
        return incident_id
    except:
        print(res.text)
        return None

def test_voice_turn():
    print("\n[2] Submitting Voice Incident to backend/interactive-voice-audio-turn...")
    with open("test_incident.mp3", "rb") as f:
        files = {"audio": ("test_incident.mp3", f, "audio/mpeg")}
        data = {"session_id": str(uuid.uuid4())}
        res = requests.post("http://127.0.0.1:8000/interactive-voice-audio-turn", files=files, data=data)
    
    print("Response Status:", res.status_code)
    try:
        body = res.json()
        print("Voice Turn Result:", body.get("transcript"))
        print("Is Complete:", body.get("complete"))
        print("Incident Object:", body.get("incident"))
        if body.get("complete") and body.get("incident"):
            # Post the completed incident to predict to finish the flow, just like frontend does
            # wait, frontend submits to /predict when complete!
            print("Simulating frontend submit for voice report...")
            # We skip this here since we just want to trace the voice loop.
    except:
        print(res.text)

if __name__ == "__main__":
    with open("test_e2e_output.txt", "w", encoding="utf-8") as f:
        f.write("Starting E2E Test...\n")
        
        # We capture stdout temporarily
        import sys, io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            inc_id = test_manual_form()
            time.sleep(2)
            if inc_id:
                db_result_manual = check_db_for_incident(inc_id)
                if db_result_manual:
                    print("=> Manual incident found in DB!")
                else:
                    print("=> WARNING: Manual incident NOT found in DB!")
                
                # Test dispatch logic for this incident
                print("\n[3] Testing Dispatch Recommendation...")
                dispatch_payload = {
                    "incident_location": "Tumkur Road",
                    "corridor": "Tumkur Road",
                    "min_officers": 2,
                    "min_vehicles": 1
                }
                res = requests.post("http://127.0.0.1:5000/dispatch", json=dispatch_payload)
                print("Dispatch Response Status:", res.status_code)
                dispatch_data = res.json()
                print("Dispatch Response:", dispatch_data)
                
                if res.status_code == 200 and dispatch_data.get("station"):
                    station_name = dispatch_data["station"]
                    print(f"\n[4] Testing Allocation to {station_name}...")
                    
                    # Fetch current resources
                    res = requests.get("http://127.0.0.1:5000/stations")
                    stations = res.json().get("stations", [])
                    station_before = next((s for s in stations if s["station"] == station_name), None)
                    print("Station Before:", station_before)
                    
                    allocate_payload = {
                        "officers": 2,
                        "vehicles": 1,
                        "tow_trucks": 0,
                        "barricades": 0
                    }
                    res = requests.post(f"http://127.0.0.1:5000/stations/{station_name}/allocate", json=allocate_payload)
                    print("Allocate Response Status:", res.status_code)
                    print("Allocate Response:", res.json())
                    
                    res = requests.get("http://127.0.0.1:5000/stations")
                    stations = res.json().get("stations", [])
                    station_after = next((s for s in stations if s["station"] == station_name), None)
                    print("Station After:", station_after)
            
            test_voice_turn()
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            f.write(output)
