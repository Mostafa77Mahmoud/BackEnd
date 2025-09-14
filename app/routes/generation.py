"""
Generation Routes

Contract generation endpoints.
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)
generation_bp = Blueprint('generation', __name__)


@generation_bp.route('/generate_from_brief', methods=['POST'])
def generate_from_brief():
    """Generate contract from brief."""
    return jsonify({"message": "Generate from brief endpoint", "status": "coming_soon"})


@generation_bp.route('/generate_modified_contract', methods=['POST'])
def generate_modified_contract():
    """Generate modified contract."""
    return jsonify({"message": "Generate modified contract endpoint", "status": "coming_soon"})