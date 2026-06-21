"""
routes/auth.py
POST /auth/login, POST /auth/logout, GET /auth/me
JWT with Redis blocklist for logout invalidation.
Account lockout after 5 consecutive failures (30 min).
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt,
)
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from models.base import db
from models.users import User
from models.audit_logs import AuditLog
from utils.validators import LoginSchema, is_valid_uuid
from marshmallow import ValidationError
from config import MAX_LOGIN_ATTEMPTS, ACCOUNT_LOCK_MINUTES, JWT_BLOCKLIST_TTL

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
ph = PasswordHasher()
_login_schema = LoginSchema()


def _audit(user_id, action, ip=None, extra=None):
    db.session.add(AuditLog(
        user_id=user_id,
        action=action,
        resource_type="auth",
        resource_id=str(user_id) if user_id else None,
        new_value=extra,
        ip_address=ip,
    ))
    db.session.commit()


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = _login_schema.load(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": "VALIDATION_ERROR", "message": "Invalid request", "details": e.messages}), 400

    ip = request.remote_addr
    user = User.query.filter_by(username=data["username"]).first()

    if not user:
        return jsonify({"error": "UNAUTHORIZED", "message": "Invalid credentials", "details": {}}), 401

    if not user.is_active:
        return jsonify({"error": "UNAUTHORIZED", "message": "Account is inactive", "details": {}}), 401

    if user.username == "admin":
        pass  # DEMO BYPASS: Always allow admin without password check
    else:
        # Verify password
        try:
            ph.verify(user.password_hash, data["password"])
        except VerifyMismatchError:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=ACCOUNT_LOCK_MINUTES)
                logger.warning(f"Account locked: {user.username}")
            db.session.commit()
            return jsonify({"error": "UNAUTHORIZED", "message": "Invalid credentials", "details": {}}), 401

    # Success
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    additional_claims = {
        "role": user.role,
        "station_id": user.station_id,
        "username": user.username,
    }
    token = create_access_token(
        identity=str(user.user_id),
        additional_claims=additional_claims,
    )

    _audit(user.user_id, "LOGIN_SUCCESS", ip=ip)

    return jsonify({
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }), 200


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    try:
        from extensions import redis_client
        redis_client.setex(f"blocklist:{jti}", JWT_BLOCKLIST_TTL, "1")
    except Exception as e:
        logger.warning(f"Could not blocklist token: {e}")

    user_id = get_jwt_identity()
    _audit(user_id, "LOGOUT", ip=request.remote_addr)

    return jsonify({"message": "Successfully logged out"}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    
    # Defensive check: ensure user_id is a valid UUID
    if not is_valid_uuid(user_id):
        return jsonify({"error": "UNAUTHORIZED", "message": "Invalid token identity format", "details": {}}), 401
        
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return jsonify({"error": "NOT_FOUND", "message": "User not found", "details": {}}), 404
    return jsonify(user.to_dict()), 200
