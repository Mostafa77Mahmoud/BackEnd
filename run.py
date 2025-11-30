#!/usr/bin/env python3
"""
Flask application entry point for the Shariaa Analyzer backend.
This file serves as the main entry point for both development and production.
"""

from dotenv import load_dotenv
load_dotenv()

from app import create_app
import os

# Create Flask app using factory pattern
app = create_app()

if __name__ == "__main__":
    # Development server configuration
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # Configure for Replit environment - bind to all interfaces
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=False  # Disable reloader to prevent issues in Replit
    )