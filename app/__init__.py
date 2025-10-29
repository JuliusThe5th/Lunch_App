import os
from flask import Flask, jsonify
from dotenv import load_dotenv
from pyngrok import conf

from app.extensions import db, migrate, jwt, cors, socketio
from app.config import config
from app.routes import auth_bp, lunch_bp, admin_bp, students_bp


def create_app(config_name=None):
    """Application factory pattern"""
    # Load environment variables
    load_dotenv()

    # Determine config
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    # Create Flask app
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(config[config_name])

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # Configure CORS
    cors.init_app(app, resources={r"/*": {
        "origins": [app.config['FRONTEND_URL']],
        "supports_credentials": True,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Authorization"],
    }})

    # Initialize SocketIO
    socketio.init_app(app,
                     cors_allowed_origins=[app.config['FRONTEND_URL']],
                     async_mode='threading',
                     logger=False,
                     engineio_logger=False)

    # Set ngrok authtoken if available
    if app.config.get('NGROK_AUTH_TOKEN'):
        conf.get_default().auth_token = app.config['NGROK_AUTH_TOKEN']

    # Register JWT error handlers
    register_jwt_handlers(app)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(lunch_bp, url_prefix='/api')
    app.register_blueprint(admin_bp)
    app.register_blueprint(students_bp, url_prefix='/api')

    # Import Socket.IO handlers to register them (must be after socketio.init_app)
    from . import socketio_handlers

    # Import models to ensure they're registered
    from .models import Student, AvailableLunch, TodayLunch, GivenLunch

    return app


def register_jwt_handlers(app):
    """Register JWT error handlers"""
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        print("JWT ERROR: Token expired")
        return jsonify({"error": "Token has expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        print(f"JWT ERROR: Invalid JWT token: {error}")
        return jsonify({"error": "Invalid token"}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        print(f"JWT ERROR: Missing JWT token: {error}")
        return jsonify({"error": "Authorization token required"}), 401

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return False

