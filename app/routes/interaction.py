"""
Interaction Routes

User interaction and consultation endpoints.
"""

import json
import datetime
import logging
from flask import Blueprint, request, jsonify

# Import services
from app.services.database import get_contracts_collection, get_terms_collection

logger = logging.getLogger(__name__)
interaction_bp = Blueprint('interaction', __name__)


@interaction_bp.route('/interact', methods=['POST'])
def interact():
    """Interactive consultation."""
    logger.info("Processing interaction request")
    
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for interaction")
        return jsonify({"error": "Database service is currently unavailable."}), 503
    
    if not request.is_json:
        logger.warning("Non-JSON request received for interaction")
        return jsonify({"error": "Content-Type must be application/json."}), 415
    
    interaction_data = request.get_json()
    if not interaction_data or "question" not in interaction_data:
        logger.warning("Invalid interaction request - missing question")
        return jsonify({"error": "الرجاء إرسال سؤال في صيغة JSON"}), 400
    
    user_question = interaction_data.get("question")
    term_id_context = interaction_data.get("term_id")
    term_text_context = interaction_data.get("term_text")
    
    session_id = request.cookies.get("session_id") or request.args.get("session_id") or interaction_data.get("session_id")
    
    logger.info(f"Processing interaction for session: {session_id}, term: {term_id_context or 'general'}")
    
    if not session_id:
        logger.warning("No session ID provided for interaction")
        return jsonify({"error": "لم يتم العثور على جلسة. يرجى تحميل العقد أولاً."}), 400
    
    try:
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            logger.warning(f"Session not found for interaction: {session_id}")
            return jsonify({"error": "الجلسة غير موجودة أو منتهية الصلاحية"}), 404
        
        contract_lang = session_doc.get("detected_contract_language", "ar")
        
        # Import AI service
        from app.services.ai_service import get_chat_session
        from config.default import DefaultConfig
        
        # Get interaction prompt from config
        config = DefaultConfig()
        
        # Get analysis type from session (already fetched above)
        analysis_type = session_doc.get("analysis_type", "sharia")
            
        # Select appropriate interaction prompt
        # Select appropriate interaction prompt
        # if analysis_type == "legal":
        #     interaction_prompt = getattr(config, 'INTERACTION_PROMPT_LEGAL', config.INTERACTION_PROMPT_SHARIA)
        # else:
        interaction_prompt = config.INTERACTION_PROMPT_SHARIA
        
        try:
            formatted_interaction_prompt = interaction_prompt.format(output_language=contract_lang)
        except KeyError as ke:
            logger.warning(f"KeyError formatting INTERACTION_PROMPT: {ke}. Using default language 'ar'")
            formatted_interaction_prompt = interaction_prompt.format(output_language='ar')
        
        # Get contract context
        full_contract_context = session_doc.get("original_contract_plain", session_doc.get("original_contract_markdown", ""))
        
        initial_analysis_summary_str = ""
        if term_id_context:
            term_doc_from_db = terms_collection.find_one({"session_id": session_id, "term_id": term_id_context})
            if term_doc_from_db:
                initial_analysis_summary_str = (
                    f"ملخص التحليل الأولي للبند '{term_id_context}' (لغة التحليل الأصلية: {contract_lang}):\n"
                    f"  - هل هو متوافق شرعاً؟ {'نعم' if term_doc_from_db.get('is_valid_sharia') else 'لا'}\n"
                    f"  - المشكلة الشرعية (إن وجدت): {term_doc_from_db.get('sharia_issue', 'لا يوجد')}\n"
                    f"  - النص المقترح للتعديل: {term_doc_from_db.get('modified_term', 'لا يوجد')}\n"
                    f"  - المرجع الشرعي: {term_doc_from_db.get('reference_number', 'لا يوجد')}\n"
                )
        
        # Build full context for LLM
        full_prompt_context = f"""
        === سياق العقد ===
        {full_contract_context[:2000]}  # Limit context size
        
        === تحليل البند المحدد ===
        {initial_analysis_summary_str}
        
        === سؤال المستخدم ===
        {user_question}
        """
        
        # Get chat session and send question
        chat = get_chat_session(f"{session_id}_interaction", system_instruction=formatted_interaction_prompt)
        response = chat.send_message(full_prompt_context)
        
        if not response or not response.text:
            logger.error("Empty response from AI service")
            return jsonify({"error": "لم نتمكن من الحصول على رد من الخدمة. حاول مرة أخرى."}), 500
        
        if response.text.startswith("ERROR_PROMPT_BLOCKED") or response.text.startswith("ERROR_CONTENT_BLOCKED"):
            logger.warning(f"Interaction blocked: {response.text}")
            return jsonify({"error": f"محتوى محظور: {response.text}"}), 400
        
        # Clean response
        from app.utils.text_processing import clean_model_response
        cleaned_response = clean_model_response(response.text)
        
        logger.info(f"Interaction processed successfully for session: {session_id}")
        return jsonify({
            "answer": cleaned_response,
            "session_id": session_id,
            "term_id": term_id_context,
            "contract_language": contract_lang,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error processing interaction: {str(e)}")
        return jsonify({"error": "حدث خطأ أثناء معالجة السؤال. حاول مرة أخرى."}), 500


@interaction_bp.route('/review_modification', methods=['POST'])
def review_modification():
    """Review user modifications."""
    logger.info("Processing review modification request")
    
    contracts_collection = get_contracts_collection()
    
    if contracts_collection is None:
        logger.error("Database service unavailable for review modification")
        return jsonify({"error": "Database service is currently unavailable."}), 503
    
    if not request.is_json:
        logger.warning("Non-JSON request received for review modification")
        return jsonify({"error": "Content-Type must be application/json."}), 415
    
    data = request.get_json()
    session_id = request.cookies.get("session_id") or data.get("session_id")
    term_id = data.get("term_id")
    user_modified_text = data.get("user_modified_text")
    original_term_text = data.get("original_term_text")
    
    logger.info(f"Reviewing modification for session: {session_id}, term: {term_id}")
    
    if not all([session_id, term_id, user_modified_text is not None, original_term_text is not None]):
        logger.warning("Incomplete data for review modification")
        return jsonify({"error": "بيانات ناقصة"}), 400
    
    try:
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            logger.warning(f"Session not found for review modification: {session_id}")
            return jsonify({"error": "الجلسة غير موجودة"}), 404
        
        contract_lang = session_doc.get("detected_contract_language", "ar")
        
        # Import AI service
        from app.services.ai_service import get_chat_session
        from config.default import DefaultConfig
        
        # Get review prompt from config
        config = DefaultConfig()
        
        # Get analysis type from session (already fetched above)
        analysis_type = session_doc.get("analysis_type", "sharia")
            
        # Select appropriate review prompt
        # Select appropriate review prompt
        # if analysis_type == "legal":
        #     review_prompt = getattr(config, 'REVIEW_MODIFICATION_PROMPT_LEGAL', '')
        # else:
        review_prompt = getattr(config, 'REVIEW_MODIFICATION_PROMPT_SHARIA', '')
        
        try:
            formatted_review_prompt = review_prompt.format(output_language=contract_lang)
        except KeyError as ke:
            logger.error(f"KeyError in REVIEW_MODIFICATION_PROMPT: {ke}")
            return jsonify({"error": f"Prompt format error: {ke}"}), 500
        
        # Create review payload
        review_payload = json.dumps({
            "original_term_text": original_term_text,
            "user_modified_text": user_modified_text
        }, ensure_ascii=False, indent=2)
        
        # Send to AI service
        logger.info("Sending modification review to AI service")
        chat = get_chat_session(f"{session_id}_review_{term_id}", system_instruction=formatted_review_prompt, force_new=True)
        response = chat.send_message(review_payload)
        
        if not response or not response.text:
            logger.error("Empty response from AI service for review")
            return jsonify({"error": "لم نتمكن من الحصول على رد من الخدمة. حاول مرة أخرى."}), 500
        
        if response.text.startswith("ERROR_PROMPT_BLOCKED") or response.text.startswith("ERROR_CONTENT_BLOCKED"):
            logger.warning(f"Review modification blocked: {response.text}")
            return jsonify({"error": f"محتوى محظور: {response.text}"}), 400
        
        # Clean response
        from app.utils.text_processing import clean_model_response
        cleaned_response = clean_model_response(response.text)
        
        logger.info(f"Modification review completed for session: {session_id}, term: {term_id}")
        return jsonify({
            "review_result": cleaned_response,
            "session_id": session_id,
            "term_id": term_id,
            "contract_language": contract_lang,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error reviewing modification: {str(e)}")
        return jsonify({"error": "حدث خطأ أثناء مراجعة التعديل. حاول مرة أخرى."}), 500


@interaction_bp.route('/confirm_modification', methods=['POST'])
def confirm_modification():
    """Confirm user modifications."""
    logger.info("Processing confirm modification request")
    
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for confirm modification")
        return jsonify({"error": "Database service is currently unavailable."}), 503
    
    data = request.get_json()
    if not data:
        logger.warning("No data sent in confirm modification request")
        return jsonify({"error": "لم يتم إرسال بيانات في الطلب"}), 400
    
    term_id = data.get("term_id")
    modified_text = data.get("modified_text")
    session_id = request.cookies.get("session_id") or data.get("session_id")
    
    logger.info(f"Confirming modification for session: {session_id}, term: {term_id}")
    
    if term_id is None or modified_text is None or not session_id:
        logger.warning("Incomplete data for confirm modification")
        return jsonify({"error": "البيانات المطلوبة غير مكتملة"}), 400
    
    try:
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            logger.warning(f"Session not found for confirm modification: {session_id}")
            return jsonify({"error": "الجلسة غير موجودة"}), 404
        
        # Update confirmed terms in session
        updated_confirmed_terms = session_doc.get("confirmed_terms", {})
        
        # Get original term text
        term_doc = terms_collection.find_one({"session_id": session_id, "term_id": term_id})
        if term_doc:
            updated_confirmed_terms[str(term_id)] = {
                "original_text": term_doc.get("term_text", ""),
                "confirmed_text": modified_text
            }
        else:
            logger.warning(f"Original term not found in DB for confirmation: {term_id}")
            updated_confirmed_terms[str(term_id)] = {
                "original_text": "",
                "confirmed_text": modified_text
            }
        
        # Update database
        contracts_collection.update_one(
            {"_id": session_id},
            {"$set": {"confirmed_terms": updated_confirmed_terms}}
        )
        
        terms_collection.update_one(
            {"session_id": session_id, "term_id": term_id},
            {"$set": {
                "is_confirmed_by_user": True,
                "confirmed_modified_text": modified_text,
            }}
        )
        
        logger.info(f"Modification confirmed for session {session_id}, term {term_id}")
        return jsonify({
            "success": True, 
            "message": f"تم تأكيد التعديل للبند: {term_id}",
            "session_id": session_id,
            "term_id": term_id
        })
        
    except Exception as e:
        logger.error(f"Error confirming modification: {str(e)}")
        return jsonify({"error": f"خطأ أثناء تأكيد التعديل: {str(e)}"}), 500