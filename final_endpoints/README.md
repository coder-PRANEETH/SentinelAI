# SentinelAI Unified API

This folder contains the unified Flask server representing the prediction models, resource tracker, load balancer, and historical incident semantic search capabilities of SentinelAI.

---

## 🚀 How to Run the Server

Using the project's pyenv Python environment, run:

```bash
/home/soul/.pyenv/versions/3.11.9/bin/python models.py
```

By default, the server runs on port **5000** (`http://localhost:5000`).

---

## 📡 Endpoint Documentation

### 1. Health Check
*   **Endpoint:** `GET /health`
*   **Response:**
    ```json
    {
      "service": "SentinelAI Unified API",
      "status": "healthy"
    }
    ```

### 2. CatBoost Priority & Resolution Prediction
*   **Endpoint:** `POST /predict`
*   **Payload (JSON):**
    ```json
    {
      "event_type_grouped": "vehicle_breakdown",
      "event_cause": "mechanical_failure",
      "corridor": "Tumkur Road",
      "police_station_grouped": "Peenya",
      "veh_type_grouped": "heavy",
      "day_of_week": "Monday",
      "latitude": 13.02,
      "longitude": 77.56,
      "location_cluster": 3,
      "hour_of_day": 14,
      "month": 6,
      "is_peak_hour": 1,
      "is_weekend": 0,
      "is_cascaded": 0,
      "cascade_size": 1
    }
    ```
*   **Response:**
    ```json
    {
      "incident": {
        "corridor": "Tumkur Road",
        "event_cause": "mechanical_failure",
        "event_type": "vehicle_breakdown"
      },
      "predictions": {
        "expected_resolution_minutes": 48.99,
        "priority": "high",
        "priority_confidence": 51.55,
        "road_closure_probability": 25.64,
        "road_closure_required": false
      }
    }
    ```

### 3. List All Stations & Resources
*   **Endpoint:** `GET /stations`
*   **Response:** List of all 53 stations and their resource configurations.
    ```json
    [
      {
        "barricades": 20,
        "officers": 15,
        "station": "Peenya",
        "tow_trucks": 2,
        "vehicles": 4
      }
      // ... 52 more stations
    ]
    ```

### 4. Get Single Station Resource Snapshot
*   **Endpoint:** `GET /stations/<station_name>`
*   **Example:** `GET /stations/Peenya`
*   **Response:**
    ```json
    {
      "barricades": 20,
      "officers": 15,
      "station": "Peenya",
      "tow_trucks": 2,
      "vehicles": 4
    }
    ```

### 5. Allocate Resources to Dispatch
*   **Endpoint:** `POST /stations/<station_name>/allocate`
*   **Payload (JSON):**
    ```json
    {
      "officers": 2,
      "vehicles": 1,
      "tow_trucks": 1,
      "barricades": 0
    }
    ```
*   **Response:**
    ```json
    {
      "action": "allocated",
      "dispatched": {
        "barricades": 0,
        "officers": 2,
        "tow_trucks": 1,
        "vehicles": 1
      },
      "remaining": {
        "barricades": 20,
        "officers": 13,
        "station": "Peenya",
        "tow_trucks": 1,
        "vehicles": 3
      },
      "station": "Peenya"
    }
    ```

### 6. Release Resources
*   **Endpoint:** `POST /stations/<station_name>/release`
*   **Payload (JSON):**
    ```json
    {
      "officers": 2,
      "vehicles": 1,
      "tow_trucks": 1,
      "barricades": 0
    }
    ```
*   **Response:**
    ```json
    {
      "action": "released",
      "current": {
        "barricades": 20,
        "officers": 15,
        "station": "Peenya",
        "tow_trucks": 2,
        "vehicles": 4
      },
      "returned": {
        "barricades": 0,
        "officers": 2,
        "tow_trucks": 1,
        "vehicles": 1
      },
      "station": "Peenya"
    }
    ```

### 7. Historical Similar Incident Search (FAISS + Semantic Search)
*   **Endpoint:** `POST /historical-search`
*   *Note: Loads FAISS index and SentenceTransformer model lazily on first call.*
*   **Payload (JSON):**
    ```json
    {
      "query": "Vehicle Breakdown Tumkur Road Heavy Vehicle",
      "top_k": 3
    }
    ```
*   **Response:**
    ```json
    {
      "average_resolution_time": 42.0,
      "historical_priority": "High",
      "most_common_outcome": "Vehicle Breakdown",
      "similar_cases": [
        {
          "corridor": "Tumkur Road",
          "event_cause": "vehicle_breakdown",
          "junction": "Goraguntepalya",
          "police_station": "Peenya",
          "priority": "High",
          "resolution_mins": 42.0,
          "similarity_score": 0.8953,
          "status": "resolved",
          "veh_type": "heavy"
        }
        // ... up to top_k cases
      ],
      "total_similar": 128
    }
    ```

### 8. Full Dispatch Pipeline
*   **Endpoint:** `POST /dispatch`
*   **Payload (JSON):**
    ```json
    {
      "incident_text": "Vehicle Breakdown Tumkur Road Heavy Vehicle",
      "corridor": "Tumkur Road",
      "min_officers": 2,
      "min_vehicles": 1,
      "search_top_k": 20
    }
    ```
*   **Response:**
    ```json
    {
      "dispatch": {
        "incident": "Vehicle Breakdown Tumkur Road Heavy Vehicle",
        "readiness_score": 66.7,
        "recommended_station": "Peenya",
        "reasons": [
          "Highest readiness score",
          "Sufficient resources available"
        ],
        "top_candidates": [
          {
            "active": 2,
            "officers": 15,
            "readiness_pct": 66.7,
            "station": "Peenya",
            "vehicles": 4
          }
          // ... top candidates ranked by readiness
        ]
      },
      "historical_context": {
        "average_resolution_time": 42.0,
        "historical_priority": "High",
        "most_common_outcome": "Vehicle Breakdown",
        "similar_cases": 128
      }
    }
    ```

### 9. Station Readiness Info
*   **Endpoint:** `GET /station-readiness` (Optional query parameter: `?station=Peenya`)
*   **Response (single station):**
    ```json
    {
      "active_incidents": 2,
      "available_officers": 15,
      "available_tow_trucks": 2,
      "available_vehicles": 4,
      "avg_resolution_mins": 42.0,
      "high_priority_incidents": 1,
      "historical_priority": "High",
      "readiness_score": 66.7,
      "resource_ratio_pct": 100.0,
      "station": "Peenya"
    }
    ```
