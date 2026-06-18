"""
resource_tracker.py
SentinelAI – Resource Tracker
Core CRUD logic for station resource allocation and release.
"""

import sqlite3
from typing import Optional
from resource_database import get_connection, init_db, log_action, DB_FILE


class ResourceTracker:
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        init_db(db_file)  # idempotent – safe to call each time

    # ── Internal helpers ─────────────────────────────────────────────────────
    def _get(self, station: str) -> Optional[dict]:
        conn = get_connection(self.db_file)
        row  = conn.execute(
            "SELECT officers, vehicles, tow_trucks, barricades FROM station_resources WHERE station=?",
            (station,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "station":    station,
            "officers":   row[0],
            "vehicles":   row[1],
            "tow_trucks": row[2],
            "barricades": row[3],
        }

    def _update(self, conn, station, officers, vehicles, tow_trucks, barricades):
        conn.execute(
            """UPDATE station_resources
               SET officers=?, vehicles=?, tow_trucks=?, barricades=?
               WHERE station=?""",
            (officers, vehicles, tow_trucks, barricades, station),
        )

    # ── Public API ───────────────────────────────────────────────────────────
    def get_available_resources(self, station: str) -> dict:
        """Return current resource snapshot for a station."""
        res = self._get(station)
        if not res:
            raise ValueError(f"Station '{station}' not found in database.")
        return res

    def allocate_resources(
        self,
        station: str,
        officers: int = 0,
        vehicles: int = 0,
        tow_trucks: int = 0,
        barricades: int = 0,
    ) -> dict:
        """
        Deduct resources for an active dispatch.
        Raises ValueError if station lacks sufficient resources.
        """
        conn = get_connection(self.db_file)
        try:
            row = conn.execute(
                "SELECT officers, vehicles, tow_trucks, barricades FROM station_resources WHERE station=?",
                (station,),
            ).fetchone()
            if not row:
                raise ValueError(f"Station '{station}' not found.")

            cur_o, cur_v, cur_t, cur_b = row

            # Validate sufficiency
            shortages = []
            if officers   > cur_o: shortages.append(f"officers (need {officers}, have {cur_o})")
            if vehicles   > cur_v: shortages.append(f"vehicles (need {vehicles}, have {cur_v})")
            if tow_trucks > cur_t: shortages.append(f"tow_trucks (need {tow_trucks}, have {cur_t})")
            if barricades > cur_b: shortages.append(f"barricades (need {barricades}, have {cur_b})")
            if shortages:
                raise ValueError(f"Insufficient resources at {station}: {', '.join(shortages)}")

            new_o = cur_o - officers
            new_v = cur_v - vehicles
            new_t = cur_t - tow_trucks
            new_b = cur_b - barricades

            self._update(conn, station, new_o, new_v, new_t, new_b)
            log_action(conn, station, "allocate", officers, vehicles, tow_trucks, barricades)
            conn.commit()
        finally:
            conn.close()

        result = {
            "station":    station,
            "action":     "allocated",
            "dispatched": {"officers": officers, "vehicles": vehicles,
                           "tow_trucks": tow_trucks, "barricades": barricades},
            "remaining":  self.get_available_resources(station),
        }
        return result

    def release_resources(
        self,
        station: str,
        officers: int = 0,
        vehicles: int = 0,
        tow_trucks: int = 0,
        barricades: int = 0,
    ) -> dict:
        """Return resources to station after incident resolution."""
        conn = get_connection(self.db_file)
        try:
            row = conn.execute(
                "SELECT officers, vehicles, tow_trucks, barricades FROM station_resources WHERE station=?",
                (station,),
            ).fetchone()
            if not row:
                raise ValueError(f"Station '{station}' not found.")

            from resource_database import DEFAULT_RESOURCES
            new_o = min(row[0] + officers,   DEFAULT_RESOURCES["officers"])
            new_v = min(row[1] + vehicles,   DEFAULT_RESOURCES["vehicles"])
            new_t = min(row[2] + tow_trucks, DEFAULT_RESOURCES["tow_trucks"])
            new_b = min(row[3] + barricades, DEFAULT_RESOURCES["barricades"])

            self._update(conn, station, new_o, new_v, new_t, new_b)
            log_action(conn, station, "release", officers, vehicles, tow_trucks, barricades)
            conn.commit()
        finally:
            conn.close()

        result = {
            "station":   station,
            "action":    "released",
            "returned":  {"officers": officers, "vehicles": vehicles,
                          "tow_trucks": tow_trucks, "barricades": barricades},
            "current":   self.get_available_resources(station),
        }
        return result

    def list_all_stations(self) -> list:
        conn = get_connection(self.db_file)
        rows = conn.execute(
            "SELECT station, officers, vehicles, tow_trucks, barricades FROM station_resources ORDER BY station"
        ).fetchall()
        conn.close()
        return [
            {"station": r[0], "officers": r[1], "vehicles": r[2],
             "tow_trucks": r[3], "barricades": r[4]}
            for r in rows
        ]


# ── Standalone demo ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    tracker = ResourceTracker()
    station = "Peenya"

    print("=== Before Dispatch ===")
    print(json.dumps(tracker.get_available_resources(station), indent=2))

    result = tracker.allocate_resources(station, officers=2, vehicles=1, tow_trucks=1)
    print("\n=== After Dispatch ===")
    print(json.dumps(result["remaining"], indent=2))

    result = tracker.release_resources(station, officers=2, vehicles=1, tow_trucks=1)
    print("\n=== After Release ===")
    print(json.dumps(result["current"], indent=2))
