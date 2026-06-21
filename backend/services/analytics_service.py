"""
services/analytics_service.py
Analytics Engine — KPIs, trends, histograms, corridor stats, model accuracy.
"""

import logging
from datetime import datetime, timezone, timedelta

from models.base import db
from sqlalchemy import text

logger = logging.getLogger(__name__)


class AnalyticsEngine:

    # ── KPIs ──────────────────────────────────────────────────────────────────

    def get_dashboard_kpis(self) -> dict:
        """
        Returns 4 KPI values:
        - active_incidents: REPORTED + IN_PROGRESS count
        - avg_resolution_minutes: avg of RESOLVED incidents (last 30 days)
        - resources_deployed: SUM of officers_dispatched (active dispatches)
        - high_risk_zones: COUNT of risk_zones with risk_score > 70
        """
        try:
            active = db.session.execute(
                text("SELECT COUNT(*) FROM incidents WHERE status IN ('REPORTED', 'IN_PROGRESS')")
            ).scalar() or 0

            avg_res = db.session.execute(
                text("""
                    SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 60)
                    FROM incidents
                    WHERE status = 'RESOLVED'
                      AND resolved_at IS NOT NULL
                      AND created_at >= NOW() - INTERVAL '30 days'
                """)
            ).scalar()

            deployed = db.session.execute(
                text("""
                    SELECT COALESCE(SUM(d.officers_dispatched), 0)
                    FROM dispatches d
                    JOIN incidents i ON i.incident_id = d.incident_id
                    WHERE i.status IN ('IN_PROGRESS', 'RESOURCES_ASSIGNED')
                      AND d.released_at IS NULL
                """)
            ).scalar() or 0

            high_risk = 0
            try:
                high_risk = db.session.execute(
                    text("SELECT COUNT(*) FROM risk_zones WHERE risk_score > 70")
                ).scalar() or 0
            except Exception:
                pass  # Table may not exist yet

            return {
                'active_incidents': int(active),
                'avg_resolution_minutes': round(float(avg_res or 0), 1),
                'resources_deployed': int(deployed),
                'high_risk_zones': int(high_risk),
            }
        except Exception as e:
            logger.error(f"[Analytics] get_dashboard_kpis failed: {e}")
            return {
                'active_incidents': 0,
                'avg_resolution_minutes': 0.0,
                'resources_deployed': 0,
                'high_risk_zones': 0,
            }

    # ── Trends ────────────────────────────────────────────────────────────────

    def get_incident_trend(self, days: int = 30) -> list:
        """Daily incident count grouped by priority for trend chart."""
        try:
            rows = db.session.execute(
                text("""
                    SELECT
                        DATE(i.created_at) AS day,
                        p.predicted_priority AS priority,
                        COUNT(*) AS count
                    FROM incidents i
                    LEFT JOIN predictions p ON p.incident_id = i.incident_id
                    WHERE i.created_at >= NOW() - INTERVAL ':days days'
                    GROUP BY day, priority
                    ORDER BY day
                """).bindparams(days=days)
            ).fetchall()
        except Exception as e:
            logger.error(f"[Analytics] trend query failed: {e}")
            return []

        # Pivot by day
        from collections import defaultdict
        daily: dict = defaultdict(lambda: {'P1': 0, 'P2': 0, 'P3': 0, 'P4': 0})
        for row in rows:
            day_str = str(row.day)
            p = row.priority or 'P4'
            if p in daily[day_str]:
                daily[day_str][p] += int(row.count)

        return [{'date': d, **v} for d, v in sorted(daily.items())]

    # ── Resolution Histogram ──────────────────────────────────────────────────

    def get_resolution_time_histogram(self, days: int = 30) -> list:
        """Bucket resolution times into 15-min intervals."""
        try:
            rows = db.session.execute(
                text("""
                    SELECT
                        FLOOR(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 60 / 15) * 15 AS bucket_start,
                        COUNT(*) AS count
                    FROM incidents
                    WHERE status = 'RESOLVED'
                      AND resolved_at IS NOT NULL
                      AND created_at >= NOW() - INTERVAL ':days days'
                    GROUP BY bucket_start
                    ORDER BY bucket_start
                """).bindparams(days=days)
            ).fetchall()

            return [
                {
                    'bucket': f"{int(row.bucket_start)}–{int(row.bucket_start + 15)} min",
                    'count': int(row.count),
                }
                for row in rows if row.bucket_start is not None
            ]
        except Exception as e:
            logger.error(f"[Analytics] histogram query failed: {e}")
            return []

    # ── Corridor stats ────────────────────────────────────────────────────────

    def get_corridor_stats(self, corridor: str = None) -> list:
        """Per-corridor incident count, avg resolution, P1 rate, most common type."""
        try:
            filter_clause = "AND i.corridor = :corridor" if corridor else ""
            rows = db.session.execute(
                text(f"""
                        SELECT
                            i.corridor,
                            COUNT(*) AS incident_count,
                            AVG(EXTRACT(EPOCH FROM (i.resolved_at - i.created_at)) / 60) AS avg_resolution,
                            SUM(CASE WHEN p.predicted_priority = 'P1' THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS p1_rate,
                            MODE() WITHIN GROUP (ORDER BY i.incident_type) AS most_common_type
                        FROM incidents i
                        LEFT JOIN predictions p ON p.incident_id = i.incident_id
                        WHERE i.corridor IS NOT NULL
                          AND i.status = 'RESOLVED'
                        {filter_clause}
                        GROUP BY i.corridor
                        ORDER BY incident_count DESC
                """),
                {'corridor': corridor} if corridor else {}
            ).fetchall()

            return [
                {
                    'corridor': row.corridor,
                    'incident_count': int(row.incident_count),
                    'avg_resolution_minutes': round(float(row.avg_resolution or 0), 1),
                    'p1_rate': round(float(row.p1_rate or 0), 4),
                    'most_common_type': row.most_common_type or 'Unknown',
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"[Analytics] corridor_stats failed: {e}")
            return []

    # ── Model accuracy ────────────────────────────────────────────────────────

    def get_model_accuracy(self) -> dict:
        """
        From incident_feedback:
        - priority_accuracy: % where priority_accurate = TRUE
        - avg_resolution_error_minutes
        - road_closure_accuracy
        - feedback_count
        """
        try:
            row = db.session.execute(
                text("""
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN priority_accurate THEN 1 ELSE 0 END) AS priority_correct,
                        AVG(ABS(resolution_error_minutes)) AS avg_error,
                        SUM(CASE WHEN road_closure_occurred = p.road_closure_recommendation_bool THEN 1 ELSE 0 END)::float
                            / NULLIF(COUNT(*), 0) AS closure_accuracy
                    FROM incident_feedback f
                    LEFT JOIN (
                        SELECT incident_id,
                               (road_closure_recommendation = 'Yes') AS road_closure_recommendation_bool
                        FROM predictions
                    ) p ON p.incident_id = f.incident_id
                """)
            ).fetchone()

            if not row or not row.total:
                return {'priority_accuracy': 0, 'avg_resolution_error_minutes': 0, 'road_closure_accuracy': 0, 'feedback_count': 0}

            total = int(row.total)
            return {
                'priority_accuracy': round((float(row.priority_correct or 0) / total) * 100, 1),
                'avg_resolution_error_minutes': round(float(row.avg_error or 0), 1),
                'road_closure_accuracy': round((float(row.closure_accuracy or 0)) * 100, 1),
                'feedback_count': total,
            }
        except Exception as e:
            logger.error(f"[Analytics] model_accuracy failed: {e}")
            return {'priority_accuracy': 0, 'avg_resolution_error_minutes': 0, 'road_closure_accuracy': 0, 'feedback_count': 0}


analytics_engine = AnalyticsEngine()
