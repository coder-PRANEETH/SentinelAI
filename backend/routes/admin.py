"""
routes/admin.py
Administrative and system operations.
Secured with RBAC (requires ADMIN role).
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from middleware.rbac import require_role
from services.risk_service import risk_detector
from services.ml_service import ml_service
from services.readiness_service import readiness_service
import time

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/run-risk-analysis', methods=['POST'])
@jwt_required()
@require_role('ADMIN')
def run_risk_analysis():
    """Manually trigger the scheduled risk analysis job."""
    result = risk_detector.run_scheduled_analysis()
    return jsonify(result), 200

@bp.route('/rebuild-index', methods=['POST'])
@jwt_required()
@require_role('ADMIN')
def rebuild_faiss_index():
    """Force rebuild of the FAISS historical search index."""
    start_time = time.time()
    try:
        from services.ml_service import ml_service
        ml_service._load_models()  # This will recreate FAISS if files are missing, 
                                   # but true rebuild requires accessing the DB.
        
        # Mock FAISS rebuild response (closed incidents sourced from final_endpoints).
        
        duration = time.time() - start_time
        return jsonify({
            "success": True,
            "message": "Index rebuilt (simulated)",
            "rebuild_duration_seconds": round(duration, 2)
        }), 200
    except Exception as e:
        return jsonify({"error": "REBUILD_FAILED", "message": str(e)}), 500

@bp.route('/model-status', methods=['GET'])
@jwt_required()
@require_role('ADMIN')
def get_model_status():
    """Query status of loaded ML models from the inference service."""
    import requests
    import os
    
    fastapi_url = os.getenv("NEXT_PUBLIC_FASTAPI_URL", "http://localhost:8000")
    try:
        # Live network request to ML inference service
        resp = requests.get(f"{fastapi_url}/")
        is_up = resp.status_code == 200
        message = resp.json().get("message", "OK") if is_up else "DOWN"
    except Exception:
        is_up = False
        message = "UNREACHABLE"

    status = ml_service.get_health_status()
    return jsonify({
        "status": "OK" if is_up else "DOWN",
        "uptime": "live" if is_up else "offline",
        "model_version": "1.0",
        "ml_message": message,
        "priority_model": "loaded" if status["priority_model"] else "missing",
        "resolution_model": "loaded" if status["resolution_model"] else "missing",
        "closure_model": "loaded" if status["closure_model"] else "missing",
        "faiss_index": "loaded" if status["faiss_index"] else "missing",
        "sentence_transformer": "loaded" if status["sentence_transformer"] else "missing"
    }), 200

@bp.route('/readiness-weights', methods=['PUT'])
@jwt_required()
@require_role('ADMIN')
def update_readiness_weights():
    """Update weights for the station readiness scoring algorithm."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "INVALID_PAYLOAD", "message": "Missing JSON body."}), 400
        
    try:
        readiness_service.update_weights(
            officer_weight=float(data.get('officer', 1.0)),
            vehicle_weight=float(data.get('vehicle', 1.5)),
            tow_weight=float(data.get('tow', 2.0)),
            barricade_weight=float(data.get('barricade', 0.5)),
            penalty_weight=float(data.get('penalty', 2.0))
        )
        return jsonify({"success": True, "message": "Readiness weights updated."}), 200
    except ValueError as e:
        return jsonify({"error": "INVALID_WEIGHTS", "message": str(e)}), 400
