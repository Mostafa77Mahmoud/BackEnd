"""
Analysis Session Routes

Session management and history endpoints.
"""

import logging
import datetime
from flask import Blueprint, request, jsonify

# Import services
from app.services.database import get_contracts_collection

logger = logging.getLogger(__name__)

# Get blueprint from __init__.py
from . import analysis_bp


@analysis_bp.route('/sessions', methods=['GET'])
def get_sessions():
    """List recent sessions with pagination."""
    logger.info("Retrieving recent sessions")
    
    contracts_collection = get_contracts_collection()
    
    if contracts_collection is None:
        return jsonify({"error": "Database service unavailable."}), 503
    
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        skip = (page - 1) * limit
        
        # Get sessions with pagination
        sessions_cursor = contracts_collection.find().sort([("created_at", -1)]).skip(skip).limit(limit)
        sessions_list = list(sessions_cursor)
        
        # Convert ObjectId and datetime objects
        from bson import ObjectId
        
        def convert_for_json(obj):
            if isinstance(obj, ObjectId):
                return str(obj)
            elif isinstance(obj, datetime.datetime):
                return obj.isoformat()
            return obj
        
        for session in sessions_list:
            for key, value in session.items():
                session[key] = convert_for_json(value)
        
        # Get total count
        total_sessions = contracts_collection.count_documents({})
        
        return jsonify({
            "sessions": sessions_list,
            "total_sessions": total_sessions,
            "current_page": page,
            "total_pages": (total_sessions + limit - 1) // limit,
            "limit": limit
        })
        
    except Exception as e:
        logger.error(f"Error retrieving sessions: {str(e)}")
        return jsonify({"error": "Failed to retrieve sessions."}), 500


@analysis_bp.route('/history', methods=['GET'])
def get_analysis_history():
    """Retrieve analysis history."""
    logger.info("Retrieving analysis history")
    
    contracts_collection = get_contracts_collection()
    
    if contracts_collection is None:
        return jsonify({"error": "Database service unavailable."}), 503
    
    try:
        # Get only completed analyses
        history_cursor = contracts_collection.find({"status": "completed"}).sort([("completed_at", -1)]).limit(20)
        history_list = list(history_cursor)
        
        # Convert ObjectId and datetime objects
        from bson import ObjectId
        
        def convert_for_json(obj):
            if isinstance(obj, ObjectId):
                return str(obj)
            elif isinstance(obj, datetime.datetime):
                return obj.isoformat()
            return obj
        
        for item in history_list:
            for key, value in item.items():
                item[key] = convert_for_json(value)
        
        return jsonify({
            "history": history_list,
            "total_items": len(history_list)
        })
        
    except Exception as e:
        logger.error(f"Error retrieving analysis history: {str(e)}")
        return jsonify({"error": "Failed to retrieve analysis history."}), 500