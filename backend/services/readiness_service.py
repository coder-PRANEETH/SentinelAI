"""
services/readiness_service.py
Station readiness calculation, candidate ranking, atomic allocation/release.
Uses SRS-defined weights (stored in config, not hardcoded).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from flask import current_app
from sqlalchemy import text

from models.base import db
from models.stations import Station
from models.resource_inventory_log import ResourceInventoryLog
from models.audit_logs import AuditLog

logger = logging.getLogger(__name__)


class ReadinessService:

    @property
    def weights(self) -> dict:
        """Read weights from app config so admin can update without redeployment."""
        from config import READINESS_WEIGHTS
        return READINESS_WEIGHTS

    # ─────────────────────────────────────────────────────────────────────────
    # READINESS CALCULATION
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_readiness(self, station: Station) -> float:
        """
        Readiness Score (0–100) per SRS Section:
          (0.35 × officers_ratio)
        + (0.30 × vehicles_ratio)
        + (0.15 × tow_ratio)
        + (0.10 × barricade_ratio)
        - (0.10 × min(1.0, active_incidents/5))

        Division by zero handled gracefully (0 total → 0 ratio).
        """
        w = self.weights

        def ratio(available, total):
            if not total:
                return 0.0
            return min(1.0, available / total)

        score = (
            w["officer"]   * ratio(station.available_officers, station.total_officers)
            + w["vehicle"] * ratio(station.available_vehicles, station.total_vehicles)
            + w["tow"]     * ratio(station.available_tow_trucks, station.total_tow_trucks)
            + w["barricade"] * ratio(station.available_barricades, station.total_barricades)
            - w["penalty"] * min(1.0, station.active_incidents / 5.0)
        )

        return round(max(0.0, score) * 100, 2)

    # ─────────────────────────────────────────────────────────────────────────
    # CANDIDATE RANKING
    # ─────────────────────────────────────────────────────────────────────────

    def rank_candidates(
        self,
        required_resources: dict,
        incident_lat: Optional[float] = None,
        incident_lon: Optional[float] = None,
    ) -> list:
        """
        1. Fetch all stations.
        2. Filter to those with sufficient resources.
        3. Sort by readiness_score DESC.
        4. Return top 3 with explainability reasons.
        """
        stations = Station.query.all()
        need_o = required_resources.get("officers", 0)
        need_v = required_resources.get("vehicles", required_resources.get("patrol_vehicles", 0))
        need_t = required_resources.get("tow_trucks", 0)
        need_b = required_resources.get("barricades", 0)

        eligible = [
            s for s in stations
            if s.available_officers >= need_o
            and s.available_vehicles >= need_v
            and s.available_tow_trucks >= need_t
            and s.available_barricades >= need_b
        ]

        if not eligible:
            # Relax constraint if all stations are stretched
            eligible = stations

        # Sort by readiness score
        eligible.sort(key=lambda s: float(s.readiness_score), reverse=True)
        top3 = eligible[:3]

        if not top3:
            return []

        max_score = float(top3[0].readiness_score)
        min_active = min(s.active_incidents for s in top3)

        results = []
        for rank, station in enumerate(top3):
            reasons = []
            if rank == 0:
                reasons.append("Highest readiness score among candidates")
            if station.active_incidents == min_active:
                reasons.append("Lowest active incident load")
            if (station.available_officers >= need_o
                    and station.available_vehicles >= need_v
                    and station.available_tow_trucks >= need_t
                    and station.available_barricades >= need_b):
                reasons.append("Sufficient resources available for recommended package")
            if incident_lat and incident_lon and station.latitude and station.longitude:
                reasons.append("Geographic proximity to incident location")

            results.append({
                **station.to_summary_dict(),
                "rank": rank + 1,
                "reasons": reasons,
            })

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # ALLOCATION (atomic)
    # ─────────────────────────────────────────────────────────────────────────

    def allocate_resources(
        self,
        station_id: str,
        resources: dict,
        incident_id: str,
        operator_id,
    ) -> dict:
        """
        Atomic resource deduction with SELECT FOR UPDATE.
        Raises ValueError (409) if insufficient resources.
        """
        officers = resources.get("officers", 0)
        vehicles = resources.get("vehicles", resources.get("patrol_vehicles", 0))
        tow_trucks = resources.get("tow_trucks", 0)
        barricades = resources.get("barricades", 0)

        # Lock row
        station = (
            Station.query
            .with_for_update()
            .filter_by(station_id=station_id)
            .first()
        )
        if not station:
            raise ValueError(f"Station '{station_id}' not found")

        # Validate
        shortages = []
        if officers > station.available_officers:
            shortages.append(f"officers (need {officers}, have {station.available_officers})")
        if vehicles > station.available_vehicles:
            shortages.append(f"vehicles (need {vehicles}, have {station.available_vehicles})")
        if tow_trucks > station.available_tow_trucks:
            shortages.append(f"tow_trucks (need {tow_trucks}, have {station.available_tow_trucks})")
        if barricades > station.available_barricades:
            shortages.append(f"barricades (need {barricades}, have {station.available_barricades})")

        if shortages:
            raise ValueError(f"Insufficient resources at {station_id}: {', '.join(shortages)}")

        # Deduct
        station.available_officers -= officers
        station.available_vehicles -= vehicles
        station.available_tow_trucks -= tow_trucks
        station.available_barricades -= barricades
        station.active_incidents += 1
        station.readiness_score = self.calculate_readiness(station)
        station.updated_at = datetime.now(timezone.utc)

        # Log each resource type
        for rtype, qty in [
            ("officers", officers),
            ("vehicles", vehicles),
            ("tow_trucks", tow_trucks),
            ("barricades", barricades),
        ]:
            if qty > 0:
                db.session.add(ResourceInventoryLog(
                    station_id=station_id,
                    resource_type=rtype,
                    change_type="allocate",
                    quantity_change=-qty,
                    reason=f"Dispatch for incident {incident_id}",
                    changed_by=operator_id,
                ))

        # Audit log
        db.session.add(AuditLog(
            user_id=operator_id,
            action="ALLOCATE_RESOURCES",
            resource_type="station",
            resource_id=station_id,
            new_value={
                "incident_id": incident_id,
                "officers": officers,
                "vehicles": vehicles,
                "tow_trucks": tow_trucks,
                "barricades": barricades,
            },
        ))

        db.session.commit()

        # Invalidate Redis cache
        self._invalidate_readiness_cache(station_id)

        return station.to_dict()

    # ─────────────────────────────────────────────────────────────────────────
    # RELEASE (atomic)
    # ─────────────────────────────────────────────────────────────────────────

    def release_resources(self, station_id: str, dispatch_id: str, operator_id) -> dict:
        """
        Restore resources from dispatch record atomically.
        """
        from models.dispatches import Dispatch

        dispatch = Dispatch.query.filter_by(dispatch_id=dispatch_id).first()
        if not dispatch:
            raise ValueError(f"Dispatch '{dispatch_id}' not found")

        station = (
            Station.query
            .with_for_update()
            .filter_by(station_id=station_id)
            .first()
        )
        if not station:
            raise ValueError(f"Station '{station_id}' not found")

        # Restore (cap at total capacity)
        station.available_officers = min(
            station.available_officers + dispatch.officers_dispatched,
            station.total_officers,
        )
        station.available_vehicles = min(
            station.available_vehicles + dispatch.vehicles_dispatched,
            station.total_vehicles,
        )
        station.available_tow_trucks = min(
            station.available_tow_trucks + dispatch.tow_trucks_dispatched,
            station.total_tow_trucks,
        )
        station.available_barricades = min(
            station.available_barricades + dispatch.barricades_dispatched,
            station.total_barricades,
        )
        station.active_incidents = max(0, station.active_incidents - 1)
        station.readiness_score = self.calculate_readiness(station)
        station.updated_at = datetime.now(timezone.utc)

        dispatch.released_at = datetime.now(timezone.utc)

        # Log
        for rtype, qty in [
            ("officers", dispatch.officers_dispatched),
            ("vehicles", dispatch.vehicles_dispatched),
            ("tow_trucks", dispatch.tow_trucks_dispatched),
            ("barricades", dispatch.barricades_dispatched),
        ]:
            if qty > 0:
                db.session.add(ResourceInventoryLog(
                    station_id=station_id,
                    resource_type=rtype,
                    change_type="release",
                    quantity_change=qty,
                    reason=f"Release for dispatch {dispatch_id}",
                    changed_by=operator_id,
                ))

        db.session.add(AuditLog(
            user_id=operator_id,
            action="RELEASE_RESOURCES",
            resource_type="station",
            resource_id=station_id,
            new_value={"dispatch_id": dispatch_id},
        ))

        db.session.commit()
        self._invalidate_readiness_cache(station_id)

        return station.to_dict()

    # ─────────────────────────────────────────────────────────────────────────
    # CACHE HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def recalculate_and_cache(self, station_id: str):
        """Recalculate readiness, save to DB, write to Redis with 60s TTL."""
        import json
        from extensions import redis_client
        from config import READINESS_CACHE_TTL

        station = Station.query.filter_by(station_id=station_id).first()
        if not station:
            return

        station.readiness_score = self.calculate_readiness(station)
        db.session.commit()

        cache_key = f"readiness:{station_id}"
        redis_client.setex(cache_key, READINESS_CACHE_TTL, json.dumps(station.to_summary_dict()))

    def _invalidate_readiness_cache(self, station_id: str):
        """Delete readiness cache entry after allocation/release."""
        try:
            from extensions import redis_client
            redis_client.delete(f"readiness:{station_id}")
        except Exception as e:
            logger.warning(f"Redis cache invalidation failed: {e}")


# Module-level singleton
readiness_service = ReadinessService()
