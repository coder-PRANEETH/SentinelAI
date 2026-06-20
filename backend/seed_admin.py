# backend/seed_admin.py
from app import create_app
from models.base import db
from models.users import User
from argon2 import PasswordHasher

ph = PasswordHasher()

app = create_app()

with app.app_context():
    # Make sure tables exist
    db.create_all()
    
    # Check if admin already exists
    admin = User.query.filter_by(username="admin").first()
    if admin:
        print("Admin user already exists!")
    else:
        # Create a new admin user
        admin = User(
            username="admin",
            email="admin@sentinelai.local",
            role="ADMIN",
            station_id=None
        )
        admin.password_hash = ph.hash("admin123")
        
        db.session.add(admin)
        db.session.commit()
        print("Successfully created ADMIN user.")
        print("Username: admin")
        print("Password: admin123")
