import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from datetime import datetime
from app.extensions import db
from app.models import User
from app.routes import main as main_blueprint  # Use alias once and only once

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.secret_key = 'your-secret-key'

    # Dynamically resolve SQLite path regardless of environment
    base_dir = os.path.abspath(os.path.dirname(__file__))  # app/
    db_path = os.path.join(base_dir, '..', 'database', 'pms.sqlite')
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.jinja_env.globals.update(now=datetime.now)
    app.jinja_env.globals['now'] = datetime.utcnow

    @app.context_processor
    def inject_datetime():
        return {'datetime': datetime}

    db.init_app(app)
    Migrate(app, db)

    # Flask-Login setup
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = "Please log in to access this page."

    # Register blueprint
    app.register_blueprint(main_blueprint)

    return app

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
