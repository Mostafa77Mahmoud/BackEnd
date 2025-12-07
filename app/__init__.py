"""
Flask Application Factory

This module provides the Flask application factory pattern for the Shariaa Contract Analyzer.
"""

import os
import logging
from flask import Flask, request, g
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

    if config_name == 'testing':
        app.config.from_object('config.testing.TestingConfig')
    elif config_name == 'production':
        app.config.from_object('config.production.ProductionConfig')
    else:
        app.config.from_object('config.default.DefaultConfig')

    if not app.config.get('SECRET_KEY'):
        error_msg = "FLASK_SECRET_KEY environment variable is required"
        logging.error(error_msg)
        if config_name == 'production':
            raise ValueError(error_msg)
        else:
            logging.warning("Running with insecure default SECRET_KEY for development")

    CORS(app, resources={r"/*": {"origins": "*"}})

    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    configure_logging(app)

    register_trace_id_handler(app)

    from app.services.database import init_db
    init_db(app)

    from app.services.cloudinary_service import init_cloudinary
    init_cloudinary(app)

    from app.services.ai_service import init_ai_service
    init_ai_service(app)

    from app.routes.root import register_root_routes
    register_root_routes(app)

    register_blueprints(app)
    
    register_error_handlers(app)

    return app


def configure_logging(app):
    """Configure application logging with clean output."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    logging.basicConfig(
        level=logging.DEBUG if app.debug else logging.INFO,
        format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler()
        ],
        force=True
    )
    
    noisy_loggers = [
        'pymongo', 'pymongo.topology', 'pymongo.connection', 
        'pymongo.serverSelection', 'pymongo.command',
        'google', 'google.auth', 'google.genai', 'google_genai',
        'urllib3', 'httpcore', 'httpx',
        'werkzeug'
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    logging.info("=" * 50)
    logging.info("SHARIAA CONTRACT ANALYZER - STARTUP")
    logging.info("=" * 50)
    logging.info(f"Debug Mode: {app.debug}")


def register_trace_id_handler(app):
    """Register before/after request handlers for trace ID management."""
    from app.utils.logging_utils import set_trace_id, clear_trace_id, get_trace_id
    import time
    
    @app.before_request
    def before_request():
        g.request_start_time = time.time()
        trace_id = request.headers.get('X-Trace-ID') or request.args.get('trace_id')
        set_trace_id(trace_id)
        g.trace_id = get_trace_id()
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'trace_id'):
            response.headers['X-Trace-ID'] = g.trace_id
        clear_trace_id()
        return response


def register_error_handlers(app):
    """Register global error handlers for consistent JSON responses."""
    from flask import jsonify
    from app.utils.logging_utils import get_trace_id, get_logger
    
    logger = get_logger('app.error_handler')
    
    @app.errorhandler(400)
    def bad_request(error):
        logger.warning(f"Bad request: {error}")
        return jsonify({
            "status": "error",
            "error_type": "BAD_REQUEST",
            "message": str(error.description) if hasattr(error, 'description') else "Bad request",
            "details": {},
            "trace_id": get_trace_id()
        }), 400
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "status": "error",
            "error_type": "NOT_FOUND",
            "message": "Resource not found",
            "details": {},
            "trace_id": get_trace_id()
        }), 404
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        logger.warning("File too large")
        return jsonify({
            "status": "error",
            "error_type": "FILE_TOO_LARGE",
            "message": "File size exceeds maximum allowed (16MB)",
            "details": {},
            "trace_id": get_trace_id()
        }), 413
    
    @app.errorhandler(500)
    def internal_server_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({
            "status": "error",
            "error_type": "INTERNAL_ERROR",
            "message": "An internal error occurred",
            "details": {},
            "trace_id": get_trace_id()
        }), 500
    
    @app.errorhandler(503)
    def service_unavailable(error):
        logger.error(f"Service unavailable: {error}")
        return jsonify({
            "status": "error",
            "error_type": "SERVICE_UNAVAILABLE",
            "message": "Service temporarily unavailable",
            "details": {},
            "trace_id": get_trace_id()
        }), 503


def register_blueprints(app):
    """Register application blueprints."""
    from app.routes import analysis_bp
    from app.routes.generation import generation_bp
    from app.routes.interaction import interaction_bp
    from app.routes.admin import admin_bp
    from app.routes.file_search import file_search_bp
    from app.routes.api_stats import api_bp

    app.register_blueprint(analysis_bp)
    app.register_blueprint(generation_bp)
    app.register_blueprint(interaction_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(file_search_bp)
    app.register_blueprint(api_bp)
