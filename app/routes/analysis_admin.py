"""
Analysis Admin Routes

Administrative endpoints including statistics and feedback.
"""

import logging
import datetime
from flask import Blueprint, request, jsonify

# Import services
from app.services.database import get_contracts_collection, get_terms_collection, get_expert_feedback_collection

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
    """Submit expert feedback on analysis to the dedicated expert_feedback collection."""
    logger.info("Processing expert feedback submission")
    
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    expert_feedback_collection = get_expert_feedback_collection()
    
    if expert_feedback_collection is None:
        return jsonify({"error": "Database service unavailable."}), 503
    
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json."}), 415
    
    try:
        request_data = request.get_json()
        
        session_id = request_data.get("session_id")
        term_id = request_data.get("term_id")
        
        if not session_id:
            return jsonify({"error": "Missing required field: session_id"}), 400
        
        if not term_id:
            return jsonify({"error": "Missing required field: term_id"}), 400
        
        # Verify session exists
        if contracts_collection is not None:
            session_doc = contracts_collection.find_one({"_id": session_id})
            if not session_doc:
                return jsonify({"error": "Session not found."}), 404
        
        # Get the term data to capture original AI analysis
        term_doc = None
        if terms_collection is not None:
            term_doc = terms_collection.find_one({"session_id": session_id, "term_id": term_id})
        
        # Get feedback data from request
        feedback_data_nested = request_data.get("feedback_data", {})
        
        # Get original term text snapshot
        original_term_text = request_data.get("original_term_text_snapshot", "")
        if not original_term_text and term_doc:
            original_term_text = term_doc.get("original_text", term_doc.get("text", ""))
        
        # Get expert info
        expert_user_id = request_data.get("expert_user_id", "default_expert_id")
        expert_username = request_data.get("expert_username", "Default Expert")
        
        # Build AI initial analysis assessment object from term data
        ai_initial_analysis_assessment = {}
        if term_doc:
            ai_initial_analysis_assessment = {
                "is_valid_sharia": term_doc.get("is_valid_sharia"),
                "sharia_issue": term_doc.get("sharia_issue", term_doc.get("issue", "")),
                "modified_term": term_doc.get("modified_term", term_doc.get("suggested_modification", "")),
                "reference_number": term_doc.get("reference_number", term_doc.get("reference", ""))
            }
        
        # Create the feedback document with the specified schema
        feedback_doc = {
            "session_id": session_id,
            "term_id": term_id,
            "original_term_text_snapshot": original_term_text,
            "expert_user_id": expert_user_id,
            "expert_username": expert_username,
            "feedback_timestamp": datetime.datetime.utcnow(),
            "ai_initial_analysis_assessment": ai_initial_analysis_assessment,
            "expert_verdict_is_valid_sharia": feedback_data_nested.get("expertIsValidSharia", feedback_data_nested.get("expert_verdict_is_valid_sharia")),
            "expert_comment_on_term": feedback_data_nested.get("expertComment", feedback_data_nested.get("expert_comment_on_term", "")),
            "expert_corrected_sharia_issue": feedback_data_nested.get("expertCorrectedShariaIssue", feedback_data_nested.get("expert_corrected_sharia_issue")),
            "expert_corrected_reference": feedback_data_nested.get("expertCorrectedReference", feedback_data_nested.get("expert_corrected_reference")),
            "expert_final_suggestion_for_term": feedback_data_nested.get("expertCorrectedSuggestion", feedback_data_nested.get("expert_final_suggestion_for_term")),
            "original_ai_is_valid_sharia": ai_initial_analysis_assessment.get("is_valid_sharia"),
            "original_ai_sharia_issue": ai_initial_analysis_assessment.get("sharia_issue"),
            "original_ai_modified_term": ai_initial_analysis_assessment.get("modified_term"),
            "original_ai_reference_number": ai_initial_analysis_assessment.get("reference_number")
        }
        
        # Insert into expert_feedback collection
        result = expert_feedback_collection.insert_one(feedback_doc)
        feedback_id = str(result.inserted_id)
        
        # Update term with expert feedback flag if term exists
        if term_doc and terms_collection is not None:
            terms_collection.update_one(
                {"session_id": session_id, "term_id": term_id},
                {"$set": {
                    "has_expert_feedback": True,
                    "expert_override_is_valid_sharia": feedback_doc["expert_verdict_is_valid_sharia"],
                    "expert_feedback_comment": feedback_doc["expert_comment_on_term"]
                }}
            )
        
        logger.info(f"Expert feedback submitted for session: {session_id}, term: {term_id}")
        return jsonify({
            "success": True,
            "message": "Expert feedback submitted successfully.",
            "session_id": session_id,
            "term_id": term_id,
            "feedback_id": feedback_id,
            "submitted_at": feedback_doc["feedback_timestamp"].isoformat()
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