"""
middleware/rbac.py
Role-Based Access Control decorator.
Usage:
    @jwt_required()
    @require_role("OPERATOR", "SUPERVISOR")
    def my_endpoint():
        ...
"""

import functools
from flask import jsonify
from flask_jwt_extended import get_jwt

ROLE_PERMISSIONS = {
    "OPERATOR": [
        "submit_incident", "dispatch", "read_resources", "submit_feedback",
    ],
    "STATION_OFFICER": [
        "read_resources", "update_inventory",
    ],
    "SUPERVISOR": [
        "read_all", "dispatch", "override", "cancel_incident",
        "submit_incident", "read_resources", "submit_feedback",
    ],
    "ADMIN": ["*"],
}

# Role hierarchy for simplified access checks
ROLE_HIERARCHY = {
    "ADMIN": 4,
    "SUPERVISOR": 3,
    "OPERATOR": 2,
    "STATION_OFFICER": 1,
}


def require_role(*roles):
    """
    Decorator that checks the JWT 'role' claim against allowed roles.
    Must be used AFTER @jwt_required().

    Example:
        @require_role("OPERATOR", "SUPERVISOR")
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_role = claims.get("role", "")

            # ADMIN bypasses all restrictions
            if user_role == "ADMIN":
                return fn(*args, **kwargs)

            if user_role not in roles:
                return jsonify({
                    "error": "FORBIDDEN",
                    "message": f"Role '{user_role}' is not permitted. Required: {list(roles)}",
                    "details": {},
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def has_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific named permission."""
    perms = ROLE_PERMISSIONS.get(role, [])
    return "*" in perms or permission in perms
