"""
routes/analytics.py
REST API for the Analytics Engine.
Secured with RBAC (requires SUPERVISOR or ADMIN role).
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from middleware.rbac import require_role
from services.analytics_service import analytics_engine

bp = Blueprint('analytics', __name__, url_prefix='/analytics')

@bp.route('/kpis', methods=['GET'])
@jwt_required()
@require_role('SUPERVISOR', 'ADMIN')
def get_kpis():
    """Get high-level dashboard KPIs."""
    return jsonify(analytics_engine.get_dashboard_kpis()), 200

@bp.route('/trends', methods=['GET'])
@jwt_required()
@require_role('SUPERVISOR', 'ADMIN')
def get_trends():
    """Get incident trends over time (default 30 days)."""
    days = int(request.args.get('days', 30))
    return jsonify(analytics_engine.get_incident_trend(days=days)), 200

@bp.route('/resolution-histogram', methods=['GET'])
@jwt_required()
@require_role('SUPERVISOR', 'ADMIN')
def get_histogram():
    """Get resolution time distribution."""
    days = int(request.args.get('days', 30))
    return jsonify(analytics_engine.get_resolution_time_histogram(days=days)), 200

@bp.route('/corridors', methods=['GET'])
@jwt_required()
@require_role('SUPERVISOR', 'ADMIN')
def get_corridors():
    """Get corridor performance stats."""
    corridor = request.args.get('corridor')
    return jsonify(analytics_engine.get_corridor_stats(corridor=corridor)), 200

@bp.route('/model-accuracy', methods=['GET'])
@jwt_required()
@require_role('SUPERVISOR', 'ADMIN')
def get_model_accuracy():
    """Get model accuracy metrics from feedback."""
    return jsonify(analytics_engine.get_model_accuracy()), 200
