"""
Analysis Routes

Contract analysis endpoints for the Shariaa Contract Analyzer.
"""

import os
import uuid
import json
import datetime
import logging
import tempfile
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

# Import services
from app.services.database import get_contracts_collection, get_terms_collection

logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

# Temporary folder setup
APP_TEMP_BASE_DIR = os.path.join(tempfile.gettempdir(), "shariaa_analyzer_temp")
TEMP_PROCESSING_FOLDER = os.path.join(APP_TEMP_BASE_DIR, "processing_files")

# Ensure directories exist
os.makedirs(TEMP_PROCESSING_FOLDER, exist_ok=True)


@analysis_bp.route('/analyze', methods=['POST'])
def analyze_contract():
    """
    Analyze contract for Sharia compliance.
    
    Enhanced to support:
    - File uploads or text input
    - analysis_type parameter (sharia, legal)
    - jurisdiction parameter (default: Egypt)
    """
    session_id = str(uuid.uuid4())
    logger.info(f"Starting contract analysis for session: {session_id}")
    
    # Get collections
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable")
        return jsonify({"error": "Database service unavailable."}), 503
    
    # Get analysis parameters
    analysis_type = request.form.get('analysis_type', 'sharia')
    jurisdiction = request.form.get('jurisdiction', 'Egypt')
    
    logger.info(f"Analysis type: {analysis_type}, Jurisdiction: {jurisdiction}")
    
    # Handle file upload or text input
    if 'file' in request.files:
        uploaded_file = request.files['file']
        if not uploaded_file or not uploaded_file.filename:
            return jsonify({"error": "Invalid file."}), 400
        
        filename = secure_filename(uploaded_file.filename)
        logger.info(f"Processing uploaded file: {filename}")
        
        # For now, return a simplified response to get the system working
        # Full implementation will be completed in the next phase
        return jsonify({
            "message": "Contract analysis initiated successfully.",
            "session_id": session_id,
            "analysis_type": analysis_type,
            "jurisdiction": jurisdiction,
            "status": "processing",
            "note": "Full analysis implementation in progress"
        })
    
    elif request.json and 'text' in request.json:
        text_content = request.json['text']
        logger.info(f"Processing text input: {len(text_content)} characters")
        
        return jsonify({
            "message": "Text analysis initiated successfully.",
            "session_id": session_id,
            "analysis_type": analysis_type,
            "jurisdiction": jurisdiction,
            "status": "processing",
            "text_length": len(text_content),
            "note": "Full analysis implementation in progress"
        })
    
    else:
        return jsonify({"error": "No file or text provided for analysis."}), 400


@analysis_bp.route('/analysis/<analysis_id>', methods=['GET'])
def get_analysis_results(analysis_id):
    """Get analysis results by ID."""
    logger.info(f"Retrieving analysis results for ID: {analysis_id}")
    
    contracts_collection = get_contracts_collection()
    
    if contracts_collection is None:
        return jsonify({"error": "Database service unavailable."}), 503
    
    # For now, return a placeholder response
    return jsonify({
        "analysis_id": analysis_id,
        "status": "completed",
        "message": "Analysis retrieval endpoint working",
        "note": "Full implementation in progress"
    })


@analysis_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "Shariaa Contract Analyzer",
        "timestamp": datetime.datetime.now().isoformat()
    })