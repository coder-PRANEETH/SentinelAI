"""
resource_database.py
SentinelAI – Resource Database
Initialises and persists station resource inventory derived from the dataset.
Uses SQLite for persistence so the tracker survives restarts.
"""

import sqlite3
import os
from typing import List, Tuple

DB_FILE = "resources.db"

# ── Default resource pool per station ────────────────────────────────────────
# Derived proportionally from ~54 stations; configurable.
DEFAULT_RESOURCES = {
    "officers":   15,
    "vehicles":    4,
    "tow_trucks":  2,
    "barricades": 20,
}

# Stations list pulled directly from the Astram dataset
STATIONS: List[str] = [
    "Peenya", "HSR Layout", "Wilson Garden", "Sadashivanagar", "Hebbala",
    "Kengeri", "Cubbon Park", "Hennuru", "K.R. Pura", "Byatarayanapura",
    "Mahadevapura", "Halasur", "Kodigehalli", "Jayanagara", "Madiwala",
    "Jeevanbheemanagar", "Whitefield", "Shivajinagar", "Mico Layout",
    "HAL Old Airport", "J.P. Nagar", "Magadi Road", "Electronic City",
    "High ground", "Chikkabanavara", "K.G. Halli", "Yeshwanthpura",
    "Bellandur", "Malleshwaram", "Devanahalli Airport", "Jnanabharathi",
    "Vijayanagara", "Chamarajpet", "Kamakshipalya", "V.V.Puram (C.Pet)",
    "Rajajinagar", "Pulikeshinagar(F.Town)", "Adugodi", "Ashok Nagar",
    "Banaswadi", "Halasuru Gate", "R.T. Nagar", "Banashankari",
    "City Market", "Basavanagudi", "Yelahanka", "K.S. Layout",
    "Chikkajala", "Sheshadripuram", "Hulimavu", "Jalahalli",
    "Thalagattapura", "Upparpet",
]


def get_connection(db_file=DB_FILE) -> sqlite3.Connection:
    return sqlite3.connect(db_file, check_same_thread=False)


def init_db(db_file=DB_FILE, force=False):
    """Create tables and seed default resources. Safe to call multiple times."""
    conn = get_connection(db_file)
    c    = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS station_resources (
            station     TEXT PRIMARY KEY,
            officers    INTEGER NOT NULL,
            vehicles    INTEGER NOT NULL,
            tow_trucks  INTEGER NOT NULL,
            barricades  INTEGER NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS resource_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            station     TEXT,
            action      TEXT,
            officers    INTEGER,
            vehicles    INTEGER,
            tow_trucks  INTEGER,
            barricades  INTEGER,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    if force:
        c.execute("DELETE FROM station_resources")

    # Seed only missing stations
    for station in STATIONS:
        c.execute(
            "INSERT OR IGNORE INTO station_resources VALUES (?,?,?,?,?)",
            (
                station,
                DEFAULT_RESOURCES["officers"],
                DEFAULT_RESOURCES["vehicles"],
                DEFAULT_RESOURCES["tow_trucks"],
                DEFAULT_RESOURCES["barricades"],
            ),
        )

    conn.commit()
    conn.close()
    print(f"[ResourceDB] Initialised with {len(STATIONS)} stations -> {db_file}")


def get_all_stations(db_file=DB_FILE) -> List[Tuple]:
    conn = get_connection(db_file)
    rows = conn.execute(
        "SELECT station, officers, vehicles, tow_trucks, barricades FROM station_resources ORDER BY station"
    ).fetchall()
    conn.close()
    return rows


def log_action(conn, station, action, officers, vehicles, tow_trucks, barricades):
    conn.execute(
        "INSERT INTO resource_log (station,action,officers,vehicles,tow_trucks,barricades) VALUES (?,?,?,?,?,?)",
        (station, action, officers, vehicles, tow_trucks, barricades),
    )


if __name__ == "__main__":
    init_db(force=True)
    rows = get_all_stations()
    print(f"{'Station':<30} {'Officers':>8} {'Vehicles':>8} {'TowTrucks':>9} {'Barricades':>10}")
    print("-" * 70)
    for r in rows:
        print(f"{r[0]:<30} {r[1]:>8} {r[2]:>8} {r[3]:>9} {r[4]:>10}")
