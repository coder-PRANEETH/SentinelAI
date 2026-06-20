"""
services/risk_service.py
Emerging Risk Detector — identifies corridors with anomalous incident frequency.
Uses SciPy linear regression + std-dev thresholding.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmergingRiskDetector:
    """
    Algorithm:
    1. Pull last 90 days of incidents grouped by corridor.
    2. For corridors with >= 5 incidents:
       a. Build daily time-series of incident counts.
       b. Compute mean + std of incident rate.
       c. Flag hotspot if last-7-day rate > mean + 1.5 * std.
       d. Compute trend via linear regression slope:
          slope > 0.1 → "increasing", < -0.1 → "decreasing", else → "stable"
    3. Score = (rate_ratio × 0.6) + (severity_weight × 0.4)
    4. Return risk zones sorted by risk_score DESC.
    """

    MIN_INCIDENTS = 5
    HOTSPOT_MULTIPLIER = 1.5
    TREND_THRESHOLD = 0.1

    def detect_hotspots(self) -> list:
        """Detect emerging hotspots from incident data."""
        from models.base import db
        from sqlalchemy import text

        try:
            rows = db.session.execute(text("""
                SELECT
                    corridor,
                    DATE(created_at) AS day,
                    COUNT(*) AS daily_count,
                    SUM(CASE WHEN status IN ('IN_PROGRESS','RESOURCES_ASSIGNED') THEN 1 ELSE 0 END) AS active_count
                FROM incidents
                WHERE created_at >= NOW() - INTERVAL '90 days'
                  AND corridor IS NOT NULL
                  AND corridor != ''
                GROUP BY corridor, DATE(created_at)
                ORDER BY corridor, day
            """)).fetchall()
        except Exception as e:
            logger.error(f"[RiskService] DB query failed: {e}")
            return []

        # Group by corridor
        corridor_data: dict = {}
        for row in rows:
            corridor = row.corridor
            if corridor not in corridor_data:
                corridor_data[corridor] = []
            corridor_data[corridor].append({
                'day': row.day,
                'count': int(row.daily_count),
            })

        zones = []
        now_date = datetime.now(timezone.utc).date()
        seven_days_ago = now_date - timedelta(days=7)
        thirty_days_ago = now_date - timedelta(days=30)

        for corridor, daily_data in corridor_data.items():
            total = sum(d['count'] for d in daily_data)
            if total < self.MIN_INCIDENTS:
                continue

            counts = np.array([d['count'] for d in daily_data], dtype=float)
            mean_rate = float(np.mean(counts))
            std_rate = float(np.std(counts))

            # Last 7-day rate
            last7 = sum(d['count'] for d in daily_data if d['day'] >= seven_days_ago)
            last7_daily_rate = last7 / 7.0

            # Hotspot threshold
            threshold = mean_rate + self.HOTSPOT_MULTIPLIER * std_rate
            is_hotspot = last7_daily_rate > threshold
            if not is_hotspot:
                continue

            # Linear regression trend
            x = np.arange(len(counts))
            if len(x) > 1:
                slope = float(np.polyfit(x, counts, 1)[0])
            else:
                slope = 0.0

            trend = (
                "increasing" if slope > self.TREND_THRESHOLD else
                "decreasing" if slope < -self.TREND_THRESHOLD else
                "stable"
            )

            # Rate ratio
            rate_ratio = last7_daily_rate / max(mean_rate, 0.01)

            # Severity weight — P1+P2 fraction from last 30 days
            severity_weight = self._get_severity_weight(corridor, thirty_days_ago)

            risk_score = min(100.0, (rate_ratio * 0.6 + severity_weight * 0.4) * 50)

            # 30-day incident count
            count_30d = sum(d['count'] for d in daily_data if d['day'] >= thirty_days_ago)

            zones.append({
                'corridor': corridor,
                'risk_score': round(risk_score, 2),
                'trend': trend,
                'incident_count_30d': count_30d,
                'p1_p2_fraction': round(severity_weight, 4),
                'rate_ratio': round(rate_ratio, 3),
            })

        zones.sort(key=lambda z: z['risk_score'], reverse=True)
        return zones

    def _get_severity_weight(self, corridor: str, since_date) -> float:
        """Fraction of P1 + P2 incidents in corridor over last 30 days."""
        from models.base import db
        from sqlalchemy import text
        try:
            row = db.session.execute(text("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN predicted_priority IN ('P1','P2') THEN 1 ELSE 0 END) AS high_priority
                FROM incidents i
                LEFT JOIN predictions p ON p.incident_id = i.incident_id
                WHERE i.corridor = :corridor
                  AND i.created_at >= :since
            """), {'corridor': corridor, 'since': since_date}).fetchone()
            if row and row.total and row.total > 0:
                return float(row.high_priority or 0) / float(row.total)
        except Exception:
            pass
        return 0.0

    def save_risk_zones(self, zones: list):
        """Upsert results into risk_zones table."""
        from models.base import db
        from sqlalchemy import text
        from sqlalchemy.dialects.postgresql import insert

        try:
            from models.risk_zones import RiskZone
            for z in zones:
                existing = RiskZone.query.filter_by(corridor=z['corridor']).first()
                if existing:
                    existing.risk_score = z['risk_score']
                    existing.trend = z['trend']
                    existing.incident_count_30d = z['incident_count_30d']
                    existing.p1_p2_fraction = z['p1_p2_fraction']
                    existing.last_updated = datetime.now(timezone.utc)
                else:
                    db.session.add(RiskZone(**z))
            db.session.commit()
            logger.info(f"[RiskService] Saved {len(zones)} risk zones")
        except Exception as e:
            logger.error(f"[RiskService] save_risk_zones failed: {e}")
            db.session.rollback()

    def get_risk_zones(self) -> list:
        """Return current risk zones from DB for map heatmap rendering."""
        try:
            from models.risk_zones import RiskZone
            zones = RiskZone.query.order_by(RiskZone.risk_score.desc()).all()
            return [z.to_dict() for z in zones]
        except Exception as e:
            logger.error(f"[RiskService] get_risk_zones failed: {e}")
            return []

    def run_scheduled_analysis(self) -> dict:
        """Entry point for scheduled job. Call detect_hotspots() + save_risk_zones()."""
        logger.info("[RiskService] Starting scheduled risk analysis")
        zones = self.detect_hotspots()
        self.save_risk_zones(zones)
        high_risk = sum(1 for z in zones if z['risk_score'] > 70)
        return {
            'zones_updated': len(zones),
            'high_risk_zones': high_risk,
            'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
        }


risk_detector = EmergingRiskDetector()
