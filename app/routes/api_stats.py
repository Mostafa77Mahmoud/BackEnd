"""
API Statistics and History Routes

Matches old api_server.py format for /api/stats/user and /api/history endpoints.
"""

import datetime
import logging
import traceback
from flask import Blueprint, jsonify
from bson import ObjectId

from app.services.database import get_contracts_collection, get_terms_collection

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/stats/user', methods=['GET'])
def get_user_stats():
    """
    Calculates and returns statistics for the user.
    Matches old api_server.py format exactly.
    """
    logger.info("Calculating user statistics")

    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for user stats")
        return jsonify({"error": "Database service is currently unavailable."}), 503

    try:
        total_sessions = contracts_collection.count_documents({})
        total_terms_analyzed = terms_collection.count_documents({})

        compliant_terms = terms_collection.count_documents({"is_valid_sharia": True})
        compliance_rate = (compliant_terms / total_terms_analyzed * 100) if total_terms_analyzed > 0 else 0

        average_processing_time = 15.5

        stats = {
            "totalSessions": total_sessions,
            "totalTerms": total_terms_analyzed,
            "complianceRate": round(compliance_rate, 2),
            "averageProcessingTime": average_processing_time
        }

        logger.info(f"User stats calculated: {total_sessions} sessions, {total_terms_analyzed} terms")
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error calculating user stats: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Failed to retrieve user stats: {str(e)}"}), 500


@api_bp.route('/history', methods=['GET'])
def get_history():
    """
    Fetches all contract analysis sessions and enriches them with calculated stats.
    Matches old api_server.py format exactly.
    """
    logger.info("Fetching contract analysis history")

    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for history")
        return jsonify({"error": "Database service is currently unavailable."}), 503

    try:
        contracts_cursor = contracts_collection.find().sort("analysis_timestamp", -1)
        contracts = list(contracts_cursor)

        if not contracts:
            logger.info("No contract history found")
            return jsonify([]), 200

        session_ids = [c.get("session_id", c.get("_id")) for c in contracts]

        terms_cursor = terms_collection.find({"session_id": {"$in": session_ids}})

        terms_by_session = {}
        for term in terms_cursor:
            session_id = term["session_id"]
            if session_id not in terms_by_session:
                terms_by_session[session_id] = []

            if '_id' in term and isinstance(term['_id'], ObjectId):
                term['_id'] = str(term['_id'])
            if 'last_expert_feedback_id' in term and isinstance(term.get('last_expert_feedback_id'), ObjectId):
                term['last_expert_feedback_id'] = str(term['last_expert_feedback_id'])

            terms_by_session[session_id].append(term)

        history_results = []
        for contract_doc in contracts:
            session_id = contract_doc.get("session_id", contract_doc.get("_id"))
            session_terms = terms_by_session.get(session_id, [])

            total_terms = len(session_terms)
            valid_terms = sum(1 for term in session_terms if term.get("is_valid_sharia") is True)
            compliance_percentage = (valid_terms / total_terms * 100) if total_terms > 0 else 100

            interactions_count = len(contract_doc.get("interactions", []))
            modifications_made = len(contract_doc.get("confirmed_terms", {}))
            generated_contracts = bool(contract_doc.get("modified_contract_info") or contract_doc.get("marked_contract_info"))

            if '_id' in contract_doc and isinstance(contract_doc['_id'], ObjectId):
                contract_doc['_id'] = str(contract_doc['_id'])
            if 'analysis_timestamp' in contract_doc and isinstance(contract_doc['analysis_timestamp'], datetime.datetime):
                contract_doc['analysis_timestamp'] = contract_doc['analysis_timestamp'].isoformat()

            for key, value in contract_doc.items():
                if isinstance(value, datetime.datetime):
                    contract_doc[key] = value.isoformat()
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, datetime.datetime):
                            value[sub_key] = sub_value.isoformat()
                        if isinstance(sub_value, ObjectId):
                            value[sub_key] = str(sub_value)

            enriched_session = {
                **contract_doc,
                "analysis_results": session_terms,
                "compliance_percentage": round(compliance_percentage, 2),
                "interactions_count": interactions_count,
                "modifications_made": modifications_made,
                "generated_contracts": generated_contracts,
            }
            history_results.append(enriched_session)

        logger.info(f"Retrieved history for {len(history_results)} sessions")
        return jsonify(history_results)

    except Exception as e:
        logger.error(f"Error retrieving session history: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Failed to retrieve session history: {str(e)}"}), 500
