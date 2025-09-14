"""
Routes Package

Registers analysis blueprint and imports all route modules.
"""

from flask import Blueprint

# Create the analysis blueprint
analysis_bp = Blueprint('analysis', __name__)

# Import all route modules to register their handlers
from . import analysis_upload
from . import analysis_terms  
from . import analysis_session
from . import analysis_admin
from . import analysis_generation