# backend/seed_haris.py
from app import create_app
from models.base import db
from models.users import User
from argon2 import PasswordHasher

ph = PasswordHasher()
app = create_app()

with app.app_context():
    # Make sure tables exist
    db.create_all()
    
    # Check if user already exists
    haris = User.query.filter_by(username="haris").first()
    if haris:
        print("User 'haris' already exists! Updating password...")
        haris.password_hash = ph.hash("Harish@5206")
        db.session.commit()
        print("Password updated successfully.")
    else:
        # Create a new user
        haris = User(
            username="haris",
            email="haris@sentinelai.local",
            role="ADMIN",
            station_id=None
        )
        haris.password_hash = ph.hash("Harish@5206")
        
        db.session.add(haris)
        db.session.commit()
        print("Successfully created 'haris' user.")
        print("Username: haris")
        print("Password: Harish@5206")
