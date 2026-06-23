"""
app.py
SentinelAI Flask Application Factory
Creates the Flask app with all middleware, blueprints, JWT, Redis, and ML models.
"""

import os
import sys
import logging

# Ensure backend/ is on sys.path when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, current_app, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def create_app(config_override: dict = None) -> Flask:
    """
    Flask application factory.
    All components loaded here; no global state in individual modules.
    """
    app = Flask(__name__)

    # ── Load configuration ────────────────────────────────────────────────────
    import config as cfg
    app.config["SQLALCHEMY_DATABASE_URI"] = cfg.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET_KEY"] = cfg.JWT_SECRET_KEY
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = cfg.JWT_ACCESS_TOKEN_EXPIRES
    app.config["JWT_BLACKLIST_ENABLED"] = True
    app.config["JWT_BLACKLIST_TOKEN_CHECKS"] = ["access"]
    app.config["RATELIMIT_DEFAULT"] = cfg.RATELIMIT_DEFAULT
    app.config["RATELIMIT_STORAGE_URL"] = cfg.RATELIMIT_STORAGE_URL
    app.config["PROPAGATE_EXCEPTIONS"] = True

    if config_override:
        app.config.update(config_override)

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Keep Flask self-sufficient for mounted deployments.
    # Handle internal CORS preflight requests independently of the ASGI mount boundary.
    CORS(
        app,
        origins=cfg.CORS_ORIGINS,
        supports_credentials=True,
        vary_header=True,
    )

    @app.before_request
    def log_incoming_request():
        origin = request.headers.get("Origin")
        logger.info(
            "[Flask] -> %s %s origin=%s",
            request.method,
            request.path,
            origin,
        )
        if request.method == "OPTIONS":
            # Let Flask answer preflight directly so decorated views never need
            # to deal with anonymous OPTIONS requests.
            return current_app.make_default_options_response()

    @app.after_request
    def log_outgoing_response(response):
        origin = request.headers.get("Origin")
        logger.info(
            "[Flask] <- %s %s %s origin=%s",
            request.method,
            request.path,
            response.status_code,
            origin,
        )
        return response

    # ── SQLAlchemy ───────────────────────────────────────────────────────────
    from models.base import db
    db.init_app(app)

    # ── JWT ──────────────────────────────────────────────────────────────────
    import extensions
    extensions.jwt = JWTManager(app)

    @extensions.jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        """Check Redis blocklist for revoked tokens."""
        try:
            jti = jwt_payload["jti"]
            return extensions.redis_client.exists(f"blocklist:{jti}") == 1
        except Exception:
            return False  # Fail open if Redis is down

    @extensions.jwt.expired_token_loader
    def expired_token_cb(jwt_header, jwt_payload):
        from flask import jsonify
        return jsonify({"error": "UNAUTHORIZED", "message": "Token has expired", "details": {}}), 401

    @extensions.jwt.invalid_token_loader
    def invalid_token_cb(reason):
        from flask import jsonify
        return jsonify({"error": "UNAUTHORIZED", "message": f"Invalid token: {reason}", "details": {}}), 401

    @extensions.jwt.unauthorized_loader
    def missing_token_cb(reason):
        from flask import jsonify
        return jsonify({"error": "UNAUTHORIZED", "message": "Authorization required", "details": {}}), 401

    import redis as redis_lib
    try:
        extensions.redis_client = redis_lib.from_url(
            cfg.REDIS_URL, decode_responses=True, socket_connect_timeout=2
        )
        extensions.redis_client.ping()
        logger.info(f"[App] Redis connected: {cfg.REDIS_URL}")
        limiter_storage = cfg.REDIS_URL
    except Exception as e:
        logger.warning(f"[App] Redis unavailable ({e}) — caching disabled, blocklist disabled")
        extensions.redis_client = _MockRedis()
        limiter_storage = "memory://"

    # ── Rate limiter ─────────────────────────────────────────────────────────
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

    def _get_jwt_identity_or_ip():
        try:
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
            return identity or get_remote_address()
        except Exception:
            return get_remote_address()

    limiter = Limiter(
        key_func=_get_jwt_identity_or_ip,
        app=app,
        default_limits=[cfg.RATELIMIT_DEFAULT],
        storage_uri=limiter_storage,
        storage_options={"socket_connect_timeout": 2} if limiter_storage != "memory://" else {},
    )
    extensions.limiter = limiter

    # ── Error handlers ───────────────────────────────────────────────────────
    from middleware.error_handlers import register_error_handlers
    register_error_handlers(app)

    # ── ML Models ───────────────────────────────────────────────────────────
    from services.ml_service import ml_service
    with app.app_context():
        try:
            ml_service.load_models(
                model_dir=cfg.CATBOOST_MODEL_DIR,
                faiss_index_path=cfg.FAISS_INDEX_PATH,
            )
        except Exception as e:
            logger.error(f"[App] ML model load error: {e}")

    # ── Database tables ──────────────────────────────────────────────────────
    with app.app_context():
        try:
            db.create_all()
            from utils.id_generator import ensure_sequences
            ensure_sequences()
            logger.info("[App] Database tables ensured")
        except Exception as e:
            logger.warning(f"[App] DB setup warning: {e}")

    # ── Blueprints ────────────────────────────────────────────────────────────
    from routes.health import health_bp
    from routes.auth import auth_bp
    from routes.predict import predict_bp
    from routes.stations import stations_bp
    from routes.dispatch import dispatch_bp
    from routes.historical import historical_bp
    from routes.feedback import feedback_bp
    from routes.analytics import bp as analytics_bp
    from routes.risk import bp as risk_bp
    from routes.admin import bp as admin_bp
    from routes.incidents import incidents_bp
    from routes.extended_feedback import extended_feedback_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(predict_bp)
    app.register_blueprint(stations_bp)
    app.register_blueprint(dispatch_bp)
    app.register_blueprint(historical_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(risk_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(incidents_bp)
    app.register_blueprint(extended_feedback_bp)

    logger.info("[App] SentinelAI Flask API ready")
    return app





class _MockRedis:
    """No-op Redis client for environments without Redis."""
    def get(self, key): return None
    def set(self, key, val): pass
    def setex(self, key, ttl, val): pass
    def delete(self, key): pass
    def exists(self, key): return 0
    def ping(self): return True


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    flask_app = create_app()
    flask_app.run(host="0.0.0.0", port=5001, debug=True)
