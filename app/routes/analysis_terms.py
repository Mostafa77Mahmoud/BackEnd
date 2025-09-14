"""
Analysis Terms Routes

Term-related endpoints and session data retrieval.
"""

import logging
import datetime
from flask import Blueprint, request, jsonify

# Import services
from app.services.database import get_contracts_collection, get_terms_collection

logger = logging.getLogger(__name__)

# Get blueprint from __init__.py
from . import analysis_bp


@analysis_bp.route('/analysis/<analysis_id>', methods=['GET'])
def get_analysis_results(analysis_id):
    """Get analysis results by ID."""
    logger.info(f"Retrieving analysis results for ID: {analysis_id}")
    
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        return jsonify({"error": "Database service unavailable."}), 503
    
    try:
        # Get session document
        session_doc = contracts_collection.find_one({"_id": analysis_id})
        if not session_doc:
            logger.warning(f"Analysis session not found: {analysis_id}")
            return jsonify({"error": "Analysis session not found."}), 404
        
        # Get terms for this session
        terms_list = list(terms_collection.find({"session_id": analysis_id}))
        
        # Convert ObjectId and datetime objects to JSON-serializable format
        from bson import ObjectId
        
        def convert_for_json(obj):
            if isinstance(obj, ObjectId):
                return str(obj)
            elif isinstance(obj, datetime.datetime):
                return obj.isoformat()
            return obj
        
        # Process session document
        for key, value in session_doc.items():
            session_doc[key] = convert_for_json(value)
        
        # Process terms
        for term in terms_list:
            for key, value in term.items():
                term[key] = convert_for_json(value)
        
        return jsonify({
            "session_id": analysis_id,
            "session_info": session_doc,
            "terms": terms_list,
            "total_terms": len(terms_list)
        })
        
    except Exception as e:
        logger.error(f"Error retrieving analysis results: {str(e)}")
        return jsonify({"error": "Failed to retrieve analysis results."}), 500


@analysis_bp.route('/session/<session_id>', methods=['GET'])
def get_session_details(session_id):
    """Fetch session details including contract info."""
    logger.info(f"Retrieving session details for ID: {session_id}")
    
    contracts_collection = get_contracts_collection()
    
    if contracts_collection is None:
        return jsonify({"error": "Database service unavailable."}), 503
    
    try:
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            logger.warning(f"Session not found: {session_id}")
            return jsonify({"error": "Session not found."}), 404
        
        # Convert ObjectId and datetime objects
        from bson import ObjectId
        
        def convert_for_json(obj):
            if isinstance(obj, ObjectId):
                return str(obj)
            elif isinstance(obj, datetime.datetime):
                return obj.isoformat()
            return obj
        
        for key, value in session_doc.items():
            session_doc[key] = convert_for_json(value)
        
        return jsonify({
            "session_id": session_id,
            "session_details": session_doc
        })
        
    except Exception as e:
        logger.error(f"Error retrieving session details: {str(e)}")
        return jsonify({"error": "Failed to retrieve session details."}), 500


@analysis_bp.route('/terms/<session_id>', methods=['GET'])
def get_session_terms(session_id):
    """Retrieve all terms for a session."""
    logger.info(f"Retrieving terms for session: {session_id}")
    
    terms_collection = get_terms_collection()
    
    if terms_collection is None:
        return jsonify({"error": "Database service unavailable."}), 503
    
    try:
        terms_list = list(terms_collection.find({"session_id": session_id}))
        
        # Convert ObjectId and datetime objects
        from bson import ObjectId
        
        def convert_for_json(obj):
            if isinstance(obj, ObjectId):
                return str(obj)
            elif isinstance(obj, datetime.datetime):
                return obj.isoformat()
            return obj
        
        for term in terms_list:
            for key, value in term.items():
                term[key] = convert_for_json(value)
        
        return jsonify({
            "session_id": session_id,
            "terms": terms_list,
            "total_terms": len(terms_list)
        })
        
    except Exception as e:
        logger.error(f"Error retrieving session terms: {str(e)}")
        return jsonify({"error": "Failed to retrieve session terms."}), 500