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
    
    # Configure CORS with comprehensive settings
    CORS(app, 
         resources={r"/*": {
             "origins": "*",
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization", "Accept"],
             "expose_headers": ["Content-Type"],
             "supports_credentials": False,  # Set to False when using origins="*"
             "max_age": 3600
         }})
    
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
    
    # Add after_request handler for additional CORS headers
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'false')
        return response
    
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
    from app.routes import analysis_bp
    from app.routes.generation import generation_bp
    from app.routes.interaction import interaction_bp
    from app.routes.admin import admin_bp
    from app.routes.file_search import file_search_bp
    
    # Register without /api prefix to match frontend expectations
    app.register_blueprint(analysis_bp)
    app.register_blueprint(generation_bp)
    app.register_blueprint(interaction_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(file_search_bp)