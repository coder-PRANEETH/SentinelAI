"""
extensions.py
Flask extension instances shared across the application.
Initialized without app context here; bound to app in create_app().
"""

from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis as redis_lib

# SQLAlchemy — imported from models.base for consistency
from models.base import db

# JWT
jwt = JWTManager()

# Rate limiter — storage configured in create_app()
limiter = Limiter(key_func=get_remote_address)

# Redis client — initialized in create_app()
redis_client: redis_lib.Redis = None  # type: ignore
