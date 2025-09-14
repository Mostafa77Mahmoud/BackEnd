"""
Flask Application Factory

This module provides the Flask application factory pattern for the Shariaa Contract Analyzer.
"""

import os
import logging
from flask import Flask
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
    
    # Configure CORS - restrict origins for security
    CORS(app, origins=["http://localhost:3000", "http://localhost:5000"], supports_credentials=False)
    
    # Set maximum content length (16MB)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    
    # Configure logging
    configure_logging(app)
    
    # Initialize services
    from app.services.database import init_db
    init_db(app)
    
    from app.services.cloudinary_service import init_cloudinary
    init_cloudinary(app)
    
    # Register blueprints
    register_blueprints(app)
    
    return app


def configure_logging(app):
    """Configure application logging."""
    if not app.debug and not app.testing:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('shariaa_analyzer.log', encoding='utf-8')
            ]
        )


def register_blueprints(app):
    """Register application blueprints."""
    from app.routes.analysis import analysis_bp
    from app.routes.generation import generation_bp
    from app.routes.interaction import interaction_bp
    from app.routes.admin import admin_bp
    
    app.register_blueprint(analysis_bp, url_prefix='/api')
    app.register_blueprint(generation_bp, url_prefix='/api')
    app.register_blueprint(interaction_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api')