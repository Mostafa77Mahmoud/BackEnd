"""
Generation Routes

Contract generation endpoints.
"""

import os
import json
import datetime
import logging
import tempfile
from flask import Blueprint, request, jsonify, Response
from werkzeug.utils import secure_filename

# Import services
from app.services.database import get_contracts_collection, get_terms_collection

logger = logging.getLogger(__name__)
generation_bp = Blueprint('generation', __name__)


@generation_bp.route('/generate_from_brief', methods=['POST'])
def generate_from_brief():
    """Generate contract from brief."""
    logger.info("Generating contract from brief")
    
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json."}), 415
    
    data = request.get_json()
    brief = data.get("brief")
    contract_type = data.get("contract_type", "general")
    jurisdiction = data.get("jurisdiction", "Egypt")
    
    if not brief:
        return jsonify({"error": "Brief is required."}), 400
    
    try:
        from app.services.ai_service import send_text_to_remote_api, get_chat_session
        from config.default import DefaultConfig
        
        # Create generation prompt
        generation_prompt = f"""
        Generate a Sharia-compliant contract based on the following brief:
        
        Brief: {brief}
        Contract Type: {contract_type}
        Jurisdiction: {jurisdiction}
        
        Please provide a complete contract in Arabic that follows Islamic law principles.
        """
        
        # Send to AI service
        response = send_text_to_remote_api(generation_prompt)
        
        if not response:
            return jsonify({"error": "Failed to generate contract."}), 500
        
        # Generate session ID
        session_id = f"gen_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Save generation result
        contracts_collection = get_contracts_collection()
        if contracts_collection:
            generation_doc = {
                "_id": session_id,
                "generation_type": "from_brief",
                "brief": brief,
                "contract_type": contract_type,
                "jurisdiction": jurisdiction,
                "generated_contract": response,
                "created_at": datetime.datetime.now(),
                "status": "completed"
            }
            contracts_collection.insert_one(generation_doc)
        
        return jsonify({
            "message": "Contract generated successfully.",
            "session_id": session_id,
            "generated_contract": response,
            "contract_type": contract_type,
            "jurisdiction": jurisdiction
        })
        
    except Exception as e:
        logger.error(f"Error generating contract from brief: {str(e)}")
        return jsonify({"error": "Internal server error during generation."}), 500


@generation_bp.route('/generate_modified_contract', methods=['POST'])
def generate_modified_contract():
    """Generate modified contract."""
    logger.info("Generating modified contract")
    
    contracts_collection = get_contracts_collection()
    
    if contracts_collection is None:
        logger.error("Database service unavailable for contract generation")
        return jsonify({"error": "Database service unavailable."}), 503
    
    # Get session ID from cookie or request data
    session_id = request.cookies.get("session_id")
    if request.is_json:
        data = request.get_json()
        session_id = session_id or data.get("session_id")
    
    if not session_id:
        logger.warning("No session ID provided for contract generation")
        return jsonify({"error": "No session ID provided."}), 400
    
    try:
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            logger.warning(f"Session not found for contract generation: {session_id}")
            return jsonify({"error": "Session not found."}), 404
        
        original_filename = session_doc.get("original_filename", "contract.docx")
        contract_lang = session_doc.get("detected_contract_language", "ar")
        confirmed_terms = session_doc.get("confirmed_terms", {})
        
        logger.info(f"Contract language: {contract_lang}, Confirmed terms: {len(confirmed_terms)}")
        
        # Get contract source
        markdown_source = session_doc.get("generated_markdown_from_docx") or session_doc.get("original_contract_markdown")
        if not markdown_source:
            logger.error("Contract source text (markdown) not found for generation")
            return jsonify({"error": "Contract source text not found for generation."}), 500
        
        # Import document processing services
        from app.services.document_processor import create_docx_from_llm_markdown
        from app.services.cloudinary_service import upload_to_cloudinary_helper
        from app.utils.file_helpers import clean_filename
        
        # Create temporary file for modified contract
        temp_dir = tempfile.gettempdir()
        temp_docx_path = os.path.join(temp_dir, f"modified_{session_id}.docx")
        
        # Generate modified DOCX using confirmed terms
        success = create_docx_from_llm_markdown(
            markdown_source, 
            temp_docx_path, 
            confirmed_terms=confirmed_terms,
            contract_language=contract_lang
        )
        
        if not success:
            return jsonify({"error": "Failed to create modified contract document."}), 500
        
        # Upload to Cloudinary
        cloudinary_folder = f"shariaa_analyzer/{session_id}/modified_contracts"
        cloudinary_result = upload_to_cloudinary_helper(temp_docx_path, cloudinary_folder)
        
        # Update session with modified contract info
        modified_contract_info = {
            "docx_cloudinary_info": cloudinary_result,
            "generated_at": datetime.datetime.now(),
            "confirmed_terms_count": len(confirmed_terms)
        }
        
        contracts_collection.update_one(
            {"_id": session_id},
            {"$set": {"modified_contract_info": modified_contract_info}}
        )
        
        # Cleanup temp file
        try:
            os.remove(temp_docx_path)
        except:
            pass
        
        logger.info(f"Modified contract generated successfully for session: {session_id}")
        return jsonify({
            "message": "Modified contract generated successfully.",
            "session_id": session_id,
            "download_url": cloudinary_result.get("url") if cloudinary_result else None,
            "confirmed_terms_count": len(confirmed_terms)
        })
        
    except Exception as e:
        logger.error(f"Error generating modified contract: {str(e)}")
        return jsonify({"error": "Internal server error during contract generation."}), 500


@generation_bp.route('/generate_marked_contract', methods=['POST'])
def generate_marked_contract():
    """Generate marked contract with highlighted terms."""
    logger.info("Generating marked contract")
    
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for marked contract generation")
        return jsonify({"error": "Database service unavailable."}), 503
    
    # Get session ID from cookie or request data
    session_id = request.cookies.get("session_id")
    if request.is_json:
        data = request.get_json()
        session_id = session_id or data.get("session_id")
    
    if not session_id:
        logger.warning("No session ID provided for marked contract generation")
        return jsonify({"error": "No session ID provided."}), 400
    
    try:
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            logger.warning(f"Session not found for marked contract generation: {session_id}")
            return jsonify({"error": "Session not found."}), 404
        
        original_filename = session_doc.get("original_filename", "contract.docx")
        contract_lang = session_doc.get("detected_contract_language", "ar")
        
        # Get contract source
        markdown_source = session_doc.get("generated_markdown_from_docx") or session_doc.get("original_contract_markdown")
        if not markdown_source:
            logger.error("Contract source text (markdown) not found for marked contract generation")
            return jsonify({"error": "Contract source text not found for generation."}), 500
        
        # Get terms for marking
        db_terms_list = list(terms_collection.find({"session_id": session_id}))
        logger.info(f"Found {len(db_terms_list)} terms for marking")
        
        # Import document processing services
        from app.services.document_processor import create_docx_from_llm_markdown
        from app.services.cloudinary_service import upload_to_cloudinary_helper
        from app.utils.file_helpers import clean_filename
        
        # Create temporary file for marked contract
        temp_dir = tempfile.gettempdir()
        temp_docx_path = os.path.join(temp_dir, f"marked_{session_id}.docx")
        
        # Generate marked DOCX with terms highlighting
        success = create_docx_from_llm_markdown(
            markdown_source, 
            temp_docx_path, 
            terms_for_marking=db_terms_list,
            contract_language=contract_lang
        )
        
        if not success:
            return jsonify({"error": "Failed to create marked contract document."}), 500
        
        # Upload to Cloudinary
        cloudinary_folder = f"shariaa_analyzer/{session_id}/marked_contracts"
        cloudinary_result = upload_to_cloudinary_helper(temp_docx_path, cloudinary_folder)
        
        # Update session with marked contract info
        marked_contract_info = {
            "docx_cloudinary_info": cloudinary_result,
            "generated_at": datetime.datetime.now(),
            "marked_terms_count": len(db_terms_list)
        }
        
        contracts_collection.update_one(
            {"_id": session_id},
            {"$set": {"marked_contract_info": marked_contract_info}}
        )
        
        # Cleanup temp file
        try:
            os.remove(temp_docx_path)
        except:
            pass
        
        logger.info(f"Marked contract generated successfully for session: {session_id}")
        return jsonify({
            "message": "Marked contract generated successfully.",
            "session_id": session_id,
            "download_url": cloudinary_result.get("url") if cloudinary_result else None,
            "marked_terms_count": len(db_terms_list)
        })
        
    except Exception as e:
        logger.error(f"Error generating marked contract: {str(e)}")
        return jsonify({"error": "Internal server error during contract generation."}), 500