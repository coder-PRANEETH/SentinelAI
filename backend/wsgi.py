"""
wsgi.py — Gunicorn entry point for the SentinelAI Flask backend.
Also seeds the demo admin user on first boot.
"""
from app import create_app
from models.base import db
from models.users import User
from argon2 import PasswordHasher

flask_app = create_app()

# ── Auto-seed demo admin on first boot ──────────────────────────────────────
with flask_app.app_context():
    try:
        ph = PasswordHasher()
        admin = User.query.filter_by(username="admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@sentinelai.local",
                role="ADMIN",
                station_id=None,
            )
            admin.password_hash = ph.hash("admin123")
            db.session.add(admin)
            db.session.commit()
            print("[WSGI] Demo admin user created: admin / admin123")
        else:
            print("[WSGI] Demo admin user already exists.")
    except Exception as e:
        print(f"[WSGI] Warning: could not seed admin user: {e}")

# Expose as 'app' so gunicorn can find it: gunicorn wsgi:app
app = flask_app
