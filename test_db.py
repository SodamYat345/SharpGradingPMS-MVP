from app import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    users = User.query.all()
    print("✅ USERS IN DB:", users)
