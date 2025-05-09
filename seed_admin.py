from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash
from app import create_app

def seed_admin():
    #Seed the database with an admin user.
    #This script is intended to be run once to set up the initial admin user.
    
    # Create the Flask app context
    app = create_app()
    with app.app_context():
        # Optional: clear old users if you want a clean slate
        User.query.delete()

        # Create admin user with a supported hash algorithm
        admin = User(
            username='admin',
            password=generate_password_hash('admin123', method='pbkdf2:sha256'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created with pbkdf2:sha256 password hash.")
