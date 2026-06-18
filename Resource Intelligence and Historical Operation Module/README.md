# 🚨 SentinelAI — Resource Intelligence & Historical Operations Module

> A smart traffic incident management system for Bengaluru.
> Built using real Astram traffic event data (8,173 incidents).

---

## 🧠 What Does This System Do?

Imagine you are a **traffic control officer** sitting in a command center.

A call comes in:

> *"There's a heavy vehicle breakdown on Tumkur Road!"*

You need to answer **three questions — fast:**

1. **Have we handled something like this before?** *(History)*
2. **Which police station should respond?** *(Selection)*
3. **Do they actually have officers and vehicles available?** *(Resources)*

This system answers all three questions **automatically**.

---

## 📁 What's In This Folder?

```
SentinelAI/
│
├── 📊 Data
│   └── Astram event data_anonymized...csv   ← The real incident dataset (8,173 rows)
│
├── 🗃️ faiss_index/                          ← Pre-built search index (auto-generated)
│   ├── incidents.index                      ← Fast search database
│   ├── incidents.pkl                        ← Saved incident records
│   └── embeddings.npy                       ← AI number representations of incidents
│
├── 🗄️ resources.db                          ← SQLite database tracking station resources
│
├── MODULE 1 — Historical Search
│   ├── embedding_pipeline.py
│   └── historical_search.py
│
├── MODULE 2 — Resource Tracker
│   ├── resource_database.py
│   ├── resource_tracker.py
│   └── inventory_api.py
│
└── MODULE 3 — Station Load Balancer
    ├── station_readiness.py
    ├── load_balancer.py
    └── station_selector.py                  ← ⭐ Main entry point (start here)
```

---

## 🔍 Module 1 — Historical Incident Search

### What is it?

Think of it like **Google Search, but for past traffic incidents**.

When a new incident comes in, this module searches through all 8,173 past incidents
and finds the ones most similar to what just happened.

### How does it work? (Step by step)

```
New Incident Text
"Vehicle Breakdown | Tumkur Road | Heavy Vehicle"
        ↓
   AI converts text into numbers (called an "embedding")
   [0.23, -0.11, 0.87, ... 384 numbers total]
        ↓
   FAISS searches for the closest matching incidents
   (Like finding the nearest neighbor in space)
        ↓
   Returns the top 20 most similar past incidents
        ↓
   Summarizes: Avg Resolution Time, Priority, Outcome
```

### What is an "embedding"?

An embedding is just a way of converting words into numbers so a computer can
compare them mathematically. Words with similar meaning get similar numbers.

- "vehicle breakdown" and "truck stopped" → numbers that are close together
- "vehicle breakdown" and "public event" → numbers that are far apart

### What is FAISS?

FAISS is a library made by Meta (Facebook) that can search through millions of
number vectors **extremely fast**. We use it to find similar past incidents
in milliseconds.

### Files

| File | What it does in plain English |
|------|-------------------------------|
| `embedding_pipeline.py` | Reads the CSV, converts every incident into numbers, saves the search index |
| `historical_search.py` | Takes your query, searches the index, returns similar cases |
| `faiss_index/` | The saved search database (don't delete this!) |

### Sample Output

```
Similar Cases Found : 128
Average Resolution Time : 42 mins
Most Common Priority : High
Most Common Outcome : Vehicle Breakdown
```

---

## 🏗️ Module 2 — Resource Tracking System

### What is it?

Think of it like an **inventory management system for a warehouse** —
except the "warehouse" is each police station, and the "inventory" is:

- 👮 Traffic Officers
- 🚗 Patrol Vehicles
- 🚛 Tow Trucks
- 🚧 Barricades

### How does it work?

Every station starts with a default supply of resources:

```
Peenya Station (Default)
  Officers  : 15
  Vehicles  :  4
  Tow Trucks:  2
  Barricades: 20
```

When an incident is dispatched, resources are **deducted**:

```python
# Dispatch 2 officers + 1 vehicle + 1 tow truck to the incident
allocate_resources("Peenya", officers=2, vehicles=1, tow_trucks=1)

# Peenya Now:
  Officers  : 13  ← was 15
  Vehicles  :  3  ← was 4
  Tow Trucks:  1  ← was 2
```

When the incident is resolved, resources are **returned**:

```python
release_resources("Peenya", officers=2, vehicles=1, tow_trucks=1)
# Resources go back to 15, 4, 2
```

All changes are **saved to a database** (`resources.db`) so nothing is lost
even if you restart the program.

### The REST API (inventory_api.py)

This file lets **other programs talk to our resource tracker** over the internet.
It works like a website but for programs.

```
Start the server:
  python inventory_api.py
  → Runs at http://localhost:5001

Available endpoints:
  GET  /stations                     → List all 53 stations
  GET  /stations/Peenya              → Check Peenya's resources
  POST /stations/Peenya/allocate     → Dispatch resources
  POST /stations/Peenya/release      → Return resources
```

### Files

| File | What it does in plain English |
|------|-------------------------------|
| `resource_database.py` | Creates the SQLite database, seeds all 53 stations |
| `resource_tracker.py` | The logic — allocate, release, check resources |
| `inventory_api.py` | A web server so other apps can use the tracker |

---

## ⚖️ Module 3 — Station Load Balancer

### What is it?

Think of it like **Uber's driver assignment algorithm** — but for police stations.

Instead of always sending the **nearest** station, it sends the station that is
**most capable of responding right now**.

A station that is nearby but has 20 active incidents and only 2 officers left
is **worse** than a station slightly farther away with 5 active incidents and
15 officers ready.

### The "Readiness Score"

Every station gets a **Readiness Score from 0 to 100**.

Higher score = better able to handle a new incident right now.

It is calculated using two things:

**1. Resource Availability** (How much do they have left?)
```
Resource Score = (Officers left / 15) × 50%
              + (Vehicles left /  4) × 30%
              + (Tow Trucks left/ 2) × 20%
```

**2. Current Load** (How busy are they already?)
```
Load Factor = (Active Incidents + 0.5 × High Priority Incidents) / 10
```

**Combined:**
```
Readiness = Resource Score / (1 + Load Factor) × 100
```

**Example:**
- Station has full resources but 10 active incidents → Load Factor = 1.0 → Readiness = 50%
- Station has full resources and 0 incidents → Load Factor = 0.0 → Readiness = 100%
- Station has half resources and 5 incidents → Lower readiness

### Example Decision

```
Incident: Vehicle Breakdown on Tumkur Road

Station Scores:
  Jnanabharathi   ############  66.7%   ← WINNER
  Peenya          ############  62.5%
  Malleshwaram    #########     48.8%
  Yeshwanthpura   #########     45.5%

Recommendation:
  → Assign Jnanabharathi Station
  Reason: Highest readiness, lowest load, sufficient resources
```

### Files

| File | What it does in plain English |
|------|-------------------------------|
| `station_readiness.py` | Calculates the readiness score for one station |
| `load_balancer.py` | Calculates scores for ALL stations and ranks them |
| `station_selector.py` | The main controller — combines historical search + load balancer |

---

## ▶️ How To Run

### Step 1 — Install requirements (one time only)
```bash
pip install sentence-transformers faiss-cpu flask pandas numpy
```

### Step 2 — Build the search index (one time only)
```bash
python embedding_pipeline.py
```
This will take about **2-3 minutes**. It reads all 8,173 incidents and builds
the search database. You only need to do this once.

### Step 3 — Run the full system
```bash
python station_selector.py "Vehicle Breakdown Tumkur Road Heavy Vehicle"
```

You'll see:
```
DISPATCH RECOMMENDATION
  Station   : Jnanabharathi
  Readiness : 66.7%
  Reasons   : Highest readiness score, Sufficient resources available

HISTORICAL CONTEXT
  Similar Cases       : 128
  Avg Resolution Time : 42 mins
  Historical Priority : High
  Most Common Outcome : Vehicle Breakdown
```

### Step 4 (Optional) — Start the Resource API server
```bash
python inventory_api.py
# Runs at http://localhost:5001
```

---

## 🔄 How All 3 Modules Work Together

```
You type: "Vehicle Breakdown Tumkur Road Heavy Vehicle"
                          │
                          ▼
            ┌─────────────────────────┐
            │    station_selector.py  │  ← The brain
            └────────┬────────────────┘
                     │
          ┌──────────┴───────────┐
          ▼                      ▼
  ┌───────────────┐    ┌──────────────────┐
  │ Historical    │    │  Load Balancer   │
  │ Search        │    │                  │
  │               │    │  - Checks all    │
  │ "128 similar  │    │    53 stations   │
  │  cases found" │    │  - Scores each   │
  │ "Avg 42 mins" │    │  - Picks best    │
  └───────────────┘    └──────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Resource Tracker    │
                    │                       │
                    │  "Jnanabharathi has   │
                    │   15 officers ready"  │
                    └───────────────────────┘
                                │
                                ▼
                   ✅ Final Answer: Send Jnanabharathi
```

---

## 🗄️ The Dataset

The system uses **real anonymized traffic incident data** from Bengaluru's
Astram platform — 8,173 incidents with details like:

| Column | What it means |
|--------|---------------|
| `event_cause` | What caused the incident (breakdown, accident, tree fall...) |
| `corridor` | Which road/zone (Tumkur Road, ORR East, CBD...) |
| `junction` | Specific junction name |
| `priority` | High or Low |
| `veh_type` | Type of vehicle involved |
| `police_station` | Which station handled it |
| `status` | active / resolved / closed |
| `start_datetime` | When it started |
| `resolved_datetime` | When it was resolved |

---

## ⚠️ Common Questions

**Q: I see a warning about `embeddings.position_ids UNEXPECTED`. Is something broken?**
> No. This is a harmless message from the AI model library. It can be safely ignored.

**Q: The index says "already exists — skipping build". Is that okay?**
> Yes! This is by design. The system reuses the pre-built index so you don't
> have to wait 3 minutes every time you run it.

**Q: What is `resources.db`?**
> It's a small database file (SQLite) that stores the resource counts for all
> 53 stations. It's like an Excel file but for programs.

**Q: Can I add a new station?**
> Yes. Open `resource_database.py` and add the station name to the `STATIONS`
> list, then run `python resource_database.py`.

---

## 📦 All Files At A Glance

| File | Module | Purpose |
|------|--------|---------|
| `embedding_pipeline.py` | 1 | Build AI search index from dataset |
| `historical_search.py` | 1 | Search similar past incidents |
| `faiss_index/` | 1 | Saved search database (folder) |
| `resource_database.py` | 2 | Setup SQLite database for resources |
| `resource_tracker.py` | 2 | Allocate / release resources |
| `inventory_api.py` | 2 | Web API for resource management |
| `station_readiness.py` | 3 | Calculate readiness score per station |
| `load_balancer.py` | 3 | Rank stations by readiness |
| `station_selector.py` | 3 | ⭐ Main entry point — full dispatch |
