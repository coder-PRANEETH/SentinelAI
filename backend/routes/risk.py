"""
routes/risk.py
REST API for risk zones.
Available to all authenticated roles for map rendering.
"""

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from services.risk_service import risk_detector

bp = Blueprint('risk', __name__, url_prefix='/risk-zones')

@bp.route('', methods=['GET'])
@jwt_required()
def get_risk_zones():
    """Get current risk zones for heatmap rendering."""
    return jsonify(risk_detector.get_risk_zones()), 200
