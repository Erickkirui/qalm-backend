import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS  # Import CORS

# Create the SQLAlchemy db instance
db = SQLAlchemy()
jwt = JWTManager()


def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config_name)

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # JWT configuration
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY")

    if not app.config["JWT_SECRET_KEY"]:
        raise RuntimeError(
            "JWT_SECRET_KEY must be set in your environment variables."
        )

    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 3600  # 1 hour

    # --- CORS CONFIGURATION ---
    # This allows your Vite React app to communicate with Flask.
    CORS(
        app,
        resources={
            r"/*": {
                "origins": [
                    "http://localhost:5173", 
                    "http://127.0.0.1:5173"
                ]
            }
        },
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    )

    # Initialize the database
    db.init_app(app)

    # Initialize Flask-Migrate
    migrate = Migrate(app, db)

    # Initialize JWT
    jwt.init_app(app)

    with app.app_context():
        # Import all models so SQLAlchemy registers them
        from Server.Models.Users import Users
        from Server.Models.Therapists import Therapist
        from Server.Models.TherapistMatchPreference import TherapistMatchPreference
        from Server.Models.Journal import Journal
        from Server.Models.Appointment import Appointment

        # Create tables that do not already exist
        db.create_all()

    # Register blueprints
    from Server.Views import Version_one
    app.register_blueprint(Version_one)

    return app