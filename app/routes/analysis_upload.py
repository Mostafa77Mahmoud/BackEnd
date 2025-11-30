"""
Analysis Upload Routes

Contract upload and main analysis entry point.
"""

import os
import uuid
import json
import datetime
import logging
from flask import Blueprint, request, jsonify

# Import services
from app.services.database import get_contracts_collection, get_terms_collection
from app.utils.analysis_helpers import TEMP_PROCESSING_FOLDER

logger = logging.getLogger(__name__)

# Get blueprint from __init__.py
from . import analysis_bp


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
    
    # Get analysis parameters from form or JSON data
    analysis_type = 'sharia'
    jurisdiction = 'Egypt'
    
    if request.is_json and request.get_json():
        json_data = request.get_json()
        analysis_type = json_data.get('analysis_type', 'sharia')
        jurisdiction = json_data.get('jurisdiction', 'Egypt')
    else:
        analysis_type = request.form.get('analysis_type', 'sharia')
        jurisdiction = request.form.get('jurisdiction', 'Egypt')
    
    # Force Sharia analysis for now (Legal disabled)
    if analysis_type == 'legal':
        logger.warning("Legal analysis requested but currently disabled. Defaulting to Sharia.")
        analysis_type = 'sharia'
    
    logger.info(f"Analysis type: {analysis_type}, Jurisdiction: {jurisdiction}")
    
    try:
        # Import services
        from app.services.document_processor import extract_text_from_file, build_structured_text_for_analysis
        from app.services.ai_service import send_text_to_remote_api
        from app.services.cloudinary_service import upload_to_cloudinary_helper
        from app.utils.file_helpers import clean_filename, download_file_from_url, ensure_dir
        from config.default import DefaultConfig
        
        # Handle file upload or text input
        if 'file' in request.files:
            uploaded_file = request.files['file']
            if not uploaded_file or not uploaded_file.filename:
                return jsonify({"error": "Invalid file."}), 400
            
            original_filename = clean_filename(uploaded_file.filename)
            logger.info(f"Processing uploaded file: {original_filename}")
            
            # Save uploaded file temporarily
            temp_file_path = os.path.join(TEMP_PROCESSING_FOLDER, f"{session_id}_{original_filename}")
            uploaded_file.save(temp_file_path)
            
            # Extract text from file
            extracted_text = extract_text_from_file(temp_file_path)
            if not extracted_text:
                return jsonify({"error": "Could not extract text from file."}), 400
            
            # Upload to Cloudinary
            cloudinary_folder = f"shariaa_analyzer/{session_id}/original_uploads"
            cloudinary_result = upload_to_cloudinary_helper(temp_file_path, cloudinary_folder)
            
            # Build structured text for analysis
            structured_text = build_structured_text_for_analysis(extracted_text)
            
            # Save session to database first
            session_doc = {
                "_id": session_id,
                "original_filename": original_filename,
                "analysis_type": analysis_type,
                "jurisdiction": jurisdiction,
                "original_contract_plain": extracted_text,
                "original_contract_markdown": structured_text,
                "created_at": datetime.datetime.now(),
                "status": "processing",
                "cloudinary_info": cloudinary_result if cloudinary_result else None
            }
            contracts_collection.insert_one(session_doc)
            
            # Perform actual analysis using AI service
            try:
                from config.default import DefaultConfig
                config = DefaultConfig()
                
                # Select appropriate prompt based on analysis type
                # Select appropriate prompt based on analysis type
                if analysis_type == "sharia":
                    sys_prompt = config.SYS_PROMPT_SHARIA
                # elif analysis_type == "legal":
                #     sys_prompt = config.SYS_PROMPT_LEGAL 
                else:
                    sys_prompt = config.SYS_PROMPT_SHARIA  # Default to Sharia
                
                if sys_prompt and sys_prompt.startswith("ERROR:"):
                    logger.error(f"Failed to load system prompt: {sys_prompt}")
                    sys_prompt = ""
                
                if sys_prompt:
                    # Send text for analysis
                    analysis_result = send_text_to_remote_api(structured_text, system_prompt=sys_prompt)
                    
                    if analysis_result:
                        # Parse and store analysis results
                        import json
                        try:
                            analysis_data = json.loads(analysis_result)
                            if isinstance(analysis_data, dict) and "terms" in analysis_data:
                                # Store individual terms
                                for term_data in analysis_data["terms"]:
                                    term_doc = {
                                        "session_id": session_id,
                                        "term_id": term_data.get("term_id"),
                                        "term_text": term_data.get("term_text"),
                                        "is_valid_sharia": term_data.get("is_valid_sharia", False),
                                        "sharia_issue": term_data.get("sharia_issue", ""),
                                        "modified_term": term_data.get("modified_term", ""),
                                        "reference_number": term_data.get("reference_number", ""),
                                        "analyzed_at": datetime.datetime.now()
                                    }
                                    terms_collection.insert_one(term_doc)
                                
                                # Update session status
                                contracts_collection.update_one(
                                    {"_id": session_id},
                                    {"$set": {
                                        "status": "completed",
                                        "analysis_result": analysis_data,
                                        "completed_at": datetime.datetime.now()
                                    }}
                                )
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse analysis result as JSON")
                            # Store raw result
                            contracts_collection.update_one(
                                {"_id": session_id},
                                {"$set": {
                                    "status": "completed",
                                    "analysis_result": {"raw_response": analysis_result},
                                    "completed_at": datetime.datetime.now()
                                }}
                            )
                    else:
                        logger.warning("No analysis result from AI service")
                        contracts_collection.update_one(
                            {"_id": session_id},
                            {"$set": {"status": "failed", "error": "AI service unavailable"}}
                        )
                else:
                    logger.warning("No system prompt configured for analysis")
                    
            except Exception as analysis_error:
                logger.error(f"Error during analysis: {str(analysis_error)}")
                contracts_collection.update_one(
                    {"_id": session_id},
                    {"$set": {"status": "failed", "error": str(analysis_error)}}
                )
            
            # Cleanup temp file
            try:
                os.remove(temp_file_path)
            except:
                pass
            
            return jsonify({
                "message": "Contract analysis initiated successfully.",
                "session_id": session_id,
                "analysis_type": analysis_type,
                "jurisdiction": jurisdiction,
                "status": "processing",
                "original_filename": original_filename
            })
        
        elif request.json and 'text' in request.json:
            text_content = request.json['text']
            logger.info(f"Processing text input: {len(text_content)} characters")
            
            # Build structured text for analysis
            structured_text = build_structured_text_for_analysis(text_content)
            
            # Save session to database first
            session_doc = {
                "_id": session_id,
                "original_filename": "text_input.txt",
                "analysis_type": analysis_type,
                "jurisdiction": jurisdiction,
                "original_contract_plain": text_content,
                "original_contract_markdown": structured_text,
                "created_at": datetime.datetime.now(),
                "status": "processing",
                "text_length": len(text_content)
            }
            contracts_collection.insert_one(session_doc)
            
            # Perform actual analysis using AI service
            try:
                from config.default import DefaultConfig
                config = DefaultConfig()
                
                # Select appropriate prompt based on analysis type
                # Select appropriate prompt based on analysis type
                if analysis_type == "sharia":
                    sys_prompt = config.SYS_PROMPT_SHARIA
                # elif analysis_type == "legal":
                #     sys_prompt = config.SYS_PROMPT_LEGAL 
                else:
                    sys_prompt = config.SYS_PROMPT_SHARIA  # Default to Sharia
                
                if sys_prompt and sys_prompt.startswith("ERROR:"):
                    logger.error(f"Failed to load system prompt: {sys_prompt}")
                    sys_prompt = ""
                
                if sys_prompt:
                    # Send text for analysis
                    analysis_result = send_text_to_remote_api(structured_text, system_prompt=sys_prompt)
                    
                    if analysis_result:
                        # Parse and store analysis results
                        import json
                        try:
                            analysis_data = json.loads(analysis_result)
                            if isinstance(analysis_data, dict) and "terms" in analysis_data:
                                # Store individual terms
                                for term_data in analysis_data["terms"]:
                                    term_doc = {
                                        "session_id": session_id,
                                        "term_id": term_data.get("term_id"),
                                        "term_text": term_data.get("term_text"),
                                        "is_valid_sharia": term_data.get("is_valid_sharia", False),
                                        "sharia_issue": term_data.get("sharia_issue", ""),
                                        "modified_term": term_data.get("modified_term", ""),
                                        "reference_number": term_data.get("reference_number", ""),
                                        "analyzed_at": datetime.datetime.now()
                                    }
                                    terms_collection.insert_one(term_doc)
                                
                                # Update session status
                                contracts_collection.update_one(
                                    {"_id": session_id},
                                    {"$set": {
                                        "status": "completed",
                                        "analysis_result": analysis_data,
                                        "completed_at": datetime.datetime.now()
                                    }}
                                )
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse analysis result as JSON")
                            # Store raw result
                            contracts_collection.update_one(
                                {"_id": session_id},
                                {"$set": {
                                    "status": "completed",
                                    "analysis_result": {"raw_response": analysis_result},
                                    "completed_at": datetime.datetime.now()
                                }}
                            )
                    else:
                        logger.warning("No analysis result from AI service")
                        contracts_collection.update_one(
                            {"_id": session_id},
                            {"$set": {"status": "failed", "error": "AI service unavailable"}}
                        )
                else:
                    logger.warning("No system prompt configured for analysis")
                    contracts_collection.update_one(
                        {"_id": session_id},
                        {"$set": {"status": "failed", "error": "No system prompt configured"}}
                    )
                    
            except Exception as analysis_error:
                logger.error(f"Error during text analysis: {str(analysis_error)}")
                contracts_collection.update_one(
                    {"_id": session_id},
                    {"$set": {"status": "failed", "error": str(analysis_error)}}
                )
            
            return jsonify({
                "message": "Text analysis initiated successfully.",
                "session_id": session_id,
                "analysis_type": analysis_type,
                "jurisdiction": jurisdiction,
                "status": "processing",
                "text_length": len(text_content)
            })
        
        else:
            return jsonify({"error": "No file or text provided for analysis."}), 400
            
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}")
        return jsonify({"error": "Internal server error during analysis."}), 500