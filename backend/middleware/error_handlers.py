"""
middleware/error_handlers.py
Global Flask error handlers returning consistent JSON responses per SRS Section 11.3.
Register with: register_error_handlers(app)
"""

import logging
from flask import jsonify
from marshmallow import ValidationError as MarshmallowValidationError
from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError
from flask_limiter.errors import RateLimitExceeded
from sqlalchemy.exc import OperationalError, IntegrityError

logger = logging.getLogger(__name__)


def _error_response(error_code: str, message: str, details: dict = None, http_code: int = 500):
    return jsonify({
        "error": error_code,
        "message": message,
        "details": details or {},
    }), http_code


def register_error_handlers(app):
    """Register all global error handlers on the Flask app."""

    @app.errorhandler(400)
    def bad_request(e):
        return _error_response("VALIDATION_ERROR", str(e), {}, 400)

    @app.errorhandler(401)
    def unauthorized(e):
        return _error_response("UNAUTHORIZED", "Authentication required", {}, 401)

    @app.errorhandler(403)
    def forbidden(e):
        return _error_response("FORBIDDEN", "Insufficient permissions", {}, 403)

    @app.errorhandler(404)
    def not_found(e):
        return _error_response("NOT_FOUND", str(e), {}, 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return _error_response("METHOD_NOT_ALLOWED", str(e), {}, 405)

    @app.errorhandler(409)
    def conflict(e):
        return _error_response("CONFLICT", str(e), {}, 409)

    @app.errorhandler(429)
    def rate_limited(e):
        return _error_response("RATE_LIMITED", "Too many requests. Slow down.", {}, 429)

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("Unhandled server error")
        return _error_response("INTERNAL_ERROR", "An unexpected error occurred", {}, 500)

    @app.errorhandler(503)
    def service_unavailable(e):
        return _error_response("SERVICE_UNAVAILABLE", str(e), {}, 503)

    # Marshmallow validation errors
    @app.errorhandler(MarshmallowValidationError)
    def marshmallow_validation_error(e):
        return _error_response(
            "VALIDATION_ERROR",
            "Request body validation failed",
            e.messages,
            400,
        )

    # JWT errors
    @app.errorhandler(NoAuthorizationError)
    def no_auth(e):
        return _error_response("UNAUTHORIZED", "Missing or invalid Authorization header", {}, 401)

    @app.errorhandler(InvalidHeaderError)
    def invalid_header(e):
        return _error_response("UNAUTHORIZED", str(e), {}, 401)

    # Rate limit
    @app.errorhandler(RateLimitExceeded)
    def rate_limit_exceeded(e):
        return _error_response("RATE_LIMITED", f"Rate limit exceeded: {e.description}", {}, 429)

    # Database integrity errors
    @app.errorhandler(IntegrityError)
    def db_integrity_error(e):
        logger.error(f"DB integrity error: {e}")
        return _error_response("CONFLICT", "Database constraint violation", {}, 409)

    @app.errorhandler(OperationalError)
    def db_operational_error(e):
        logger.error(f"DB operational error: {e}")
        return _error_response("SERVICE_UNAVAILABLE", "Database connection error", {}, 503)
