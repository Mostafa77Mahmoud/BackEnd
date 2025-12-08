"""
Analysis Admin Routes

Administrative endpoints including statistics and feedback.
"""

import logging
import datetime
from flask import Blueprint, request, jsonify

# Import services
from app.services.database import get_contracts_collection, get_terms_collection

logger = logging.getLogger(__name__)

# Get blueprint from __init__.py
from . import analysis_bp


@analysis_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Provide system statistics."""
    logger.info("Retrieving system statistics")
    
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        return jsonify({"error": "Database service unavailable."}), 503
    
    try:
        # Get basic counts
        total_sessions = contracts_collection.count_documents({})
        completed_sessions = contracts_collection.count_documents({"status": "completed"})
        failed_sessions = contracts_collection.count_documents({"status": "failed"})
        processing_sessions = contracts_collection.count_documents({"status": "processing"})
        
        # Get analysis type breakdown
        sharia_analyses = contracts_collection.count_documents({"analysis_type": "sharia"})
        legal_analyses = contracts_collection.count_documents({"analysis_type": "legal"})
        
        # Get recent activity (last 7 days)
        seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        recent_sessions = contracts_collection.count_documents({
            "created_at": {"$gte": seven_days_ago}
        })
        
        # Get total terms analyzed
        total_terms = terms_collection.count_documents({})
        
        statistics = {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "failed_sessions": failed_sessions,
            "processing_sessions": processing_sessions,
            "success_rate": (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0,
            "analysis_types": {
                "sharia": sharia_analyses,
                "legal": legal_analyses
            },
            "recent_activity": {
                "last_7_days": recent_sessions
            },
            "total_terms_analyzed": total_terms,
            "generated_at": datetime.datetime.now().isoformat()
        }
        
        return jsonify(statistics)
        
    except Exception as e:
        logger.error(f"Error retrieving statistics: {str(e)}")
        return jsonify({"error": "Failed to retrieve statistics."}), 500


@analysis_bp.route('/stats/user', methods=['GET'])
def get_user_stats():
    """Provide user-specific statistics."""
    logger.info("Retrieving user-specific statistics")
    
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        return jsonify({"error": "Database service unavailable."}), 503
    
    try:
        # For now, return aggregate stats since we don't have user authentication
        # This could be enhanced with user-specific filtering later
        
        # Get recent analysis activity
        recent_limit = int(request.args.get('limit', 10))
        recent_sessions = list(contracts_collection.find(
            {},
            {
                "_id": 1, 
                "original_filename": 1, 
                "analysis_type": 1, 
                "status": 1, 
                "created_at": 1,
                "jurisdiction": 1
            }
        ).sort("created_at", -1).limit(recent_limit))
        
        # Convert ObjectId and datetime objects
        from bson import ObjectId
        
        def convert_for_json(obj):
            if isinstance(obj, ObjectId):
                return str(obj)
            elif isinstance(obj, datetime.datetime):
                return obj.isoformat()
            return obj
        
        for session in recent_sessions:
            for key, value in session.items():
                session[key] = convert_for_json(value)
        
        # Get activity summary for last 30 days
        thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        monthly_count = contracts_collection.count_documents({
            "created_at": {"$gte": thirty_days_ago}
        })
        
        user_stats = {
            "recent_sessions": recent_sessions,
            "monthly_analysis_count": monthly_count,
            "total_sessions": len(recent_sessions),
            "generated_at": datetime.datetime.now().isoformat()
        }
        
        return jsonify(user_stats)
        
    except Exception as e:
        logger.error(f"Error retrieving user stats: {str(e)}")
        return jsonify({"error": "Failed to retrieve user statistics."}), 500


@analysis_bp.route('/feedback/expert', methods=['POST'])
def submit_expert_feedback():
    """Submit expert feedback on analysis."""
    logger.info("Processing expert feedback submission")
    
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None:
        return jsonify({"error": "Database service unavailable."}), 503
    
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json."}), 415
    
    try:
        request_data = request.get_json()
        
        # Support both old format (feedback_text) and new format (feedback_data with nested structure)
        session_id = request_data.get("session_id")
        term_id = request_data.get("term_id")
        
        if not session_id:
            return jsonify({"error": "Missing required field: session_id"}), 400
        
        # Verify session exists
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            return jsonify({"error": "Session not found."}), 404
        
        # Handle new frontend format with feedback_data nested structure
        feedback_data_nested = request_data.get("feedback_data")
        
        if feedback_data_nested:
            # New format from frontend
            feedback_doc = {
                "term_id": term_id,
                "ai_analysis_approved": feedback_data_nested.get("aiAnalysisApproved"),
                "expert_is_valid_sharia": feedback_data_nested.get("expertIsValidSharia"),
                "expert_comment": feedback_data_nested.get("expertComment", ""),
                "expert_corrected_sharia_issue": feedback_data_nested.get("expertCorrectedShariaIssue"),
                "expert_corrected_reference": feedback_data_nested.get("expertCorrectedReference"),
                "expert_corrected_suggestion": feedback_data_nested.get("expertCorrectedSuggestion"),
                "submitted_at": datetime.datetime.now()
            }
            
            # Update term with expert feedback if term_id is provided
            if term_id and terms_collection is not None:
                terms_collection.update_one(
                    {"session_id": session_id, "term_id": term_id},
                    {"$set": {
                        "has_expert_feedback": True,
                        "expert_override_is_valid_sharia": feedback_data_nested.get("expertIsValidSharia"),
                        "expert_feedback_comment": feedback_data_nested.get("expertComment", "")
                    }}
                )
        else:
            # Old format with feedback_text (backward compatibility)
            feedback_text = request_data.get("feedback_text")
            if not feedback_text:
                return jsonify({"error": "Missing required field: feedback_text or feedback_data"}), 400
            
            feedback_doc = {
                "term_id": term_id,
                "expert_name": request_data.get("expert_name", ""),
                "feedback_text": feedback_text,
                "rating": request_data.get("rating"),
                "submitted_at": datetime.datetime.now()
            }
        
        # Generate feedback ID
        import uuid
        feedback_id = str(uuid.uuid4())[:8]
        feedback_doc["feedback_id"] = feedback_id
        
        # Update session with expert feedback
        contracts_collection.update_one(
            {"_id": session_id},
            {"$push": {"expert_feedback": feedback_doc}}
        )
        
        logger.info(f"Expert feedback submitted for session: {session_id}, term: {term_id}")
        return jsonify({
            "success": True,
            "message": "Expert feedback submitted successfully.",
            "session_id": session_id,
            "feedback_id": feedback_id,
            "submitted_at": feedback_doc["submitted_at"].isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error submitting expert feedback: {str(e)}")
        return jsonify({"error": "Failed to submit expert feedback."}), 500


@analysis_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "service": "Shariaa Contract Analyzer",
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat()
    }), 200