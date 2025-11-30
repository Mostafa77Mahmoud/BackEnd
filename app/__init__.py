"""
Flask Application Factory

This module provides the Flask application factory pattern for the Shariaa Contract Analyzer.
"""

import os
import logging
from flask import Flask, request
from flask_cors import CORS


def create_app(config_name='default'):
    """
    Create and configure Flask application instance.

    Args:
        config_name (str): Configuration environment name

    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)

    # Load configuration
    if config_name == 'testing':
        app.config.from_object('config.testing.TestingConfig')
    elif config_name == 'production':
        app.config.from_object('config.production.ProductionConfig')
    else:
        app.config.from_object('config.default.DefaultConfig')

    # Validate critical configuration
    if not app.config.get('SECRET_KEY'):
        error_msg = "FLASK_SECRET_KEY environment variable is required"
        logging.error(error_msg)
        if config_name == 'production':
            raise ValueError(error_msg)
        else:
            logging.warning("Running with insecure default SECRET_KEY for development")

    # Configure CORS - Simple and effective for development
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Set maximum content length (16MB)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # Configure logging
    configure_logging(app)

    # Initialize services
    from app.services.database import init_db
    init_db(app)

    from app.services.cloudinary_service import init_cloudinary
    init_cloudinary(app)

    from app.services.ai_service import init_ai_service
    init_ai_service(app)

    # Register root routes
    from app.routes.root import register_root_routes
    register_root_routes(app)

    # Register blueprints
    register_blueprints(app)

    return app


def configure_logging(app):
    """Configure application logging."""
    log_level = logging.DEBUG if app.debug else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler()
        ],
        force=True
    )
    
    logging.info("="*60)
    logging.info("SHARIAA CONTRACT ANALYZER - STARTUP")
    logging.info("="*60)
    logging.info(f"Debug Mode: {app.debug}")
    logging.info(f"Log Level: {'DEBUG' if app.debug else 'INFO'}")


def register_blueprints(app):
    """Register application blueprints."""
    from app.routes import analysis_bp
    from app.routes.generation import generation_bp
    from app.routes.interaction import interaction_bp
    from app.routes.admin import admin_bp
    from app.routes.file_search import file_search_bp
    from app.routes.api_stats import api_bp

    # Register without /api prefix to match frontend expectations
    app.register_blueprint(analysis_bp)
    app.register_blueprint(generation_bp)
    app.register_blueprint(interaction_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(file_search_bp)
    app.register_blueprint(api_bp)