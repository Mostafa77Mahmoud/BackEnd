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
            
            # Detect contract language for output
            from langdetect import detect
            try:
                detected_lang = detect(extracted_text[:1000])
                output_language = "العربية" if detected_lang == "ar" else "English"
                logger.info(f"Detected contract language: {detected_lang}, output_language: {output_language}")
            except:
                output_language = "العربية"
                logger.info(f"Language detection failed, defaulting to Arabic")
            
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
            
            # Perform actual analysis using AI service with file_search integration
            try:
                from config.default import DefaultConfig
                from app.services.file_search import FileSearchService
                config = DefaultConfig()
                
                # Step 1: Use file_search to get relevant AAOIFI context
                aaoifi_context = ""
                try:
                    logger.info(f"Starting file search for session: {session_id}")
                    file_search_service = FileSearchService()
                    chunks, extracted_terms = file_search_service.search_chunks(structured_text)
                    
                    if chunks:
                        logger.info(f"File search returned {len(chunks)} relevant AAOIFI chunks")
                        aaoifi_chunks_text = []
                        for chunk in chunks:
                            chunk_text = chunk.get("chunk_text", "")
                            if chunk_text:
                                aaoifi_chunks_text.append(chunk_text)
                        aaoifi_context = "\n\n---\n\n".join(aaoifi_chunks_text)
                        logger.info(f"AAOIFI context length: {len(aaoifi_context)} characters")
                    else:
                        logger.warning("No AAOIFI chunks found from file search")
                        aaoifi_context = "لا توجد مراجع AAOIFI متاحة حالياً"
                except Exception as fs_error:
                    logger.error(f"File search failed: {str(fs_error)}")
                    aaoifi_context = "لا توجد مراجع AAOIFI متاحة حالياً"
                
                # Step 2: Select and format the system prompt
                if analysis_type == "sharia":
                    sys_prompt_template = config.SYS_PROMPT_SHARIA
                else:
                    sys_prompt_template = config.SYS_PROMPT_SHARIA  # Default to Sharia
                
                if sys_prompt_template and sys_prompt_template.startswith("ERROR:"):
                    logger.error(f"Failed to load system prompt: {sys_prompt_template}")
                    sys_prompt_template = ""
                
                if sys_prompt_template:
                    # Format the prompt with output_language and aaoifi_context
                    sys_prompt = sys_prompt_template.format(
                        output_language=output_language,
                        aaoifi_context=aaoifi_context
                    )
                    logger.info(f"Formatted system prompt length: {len(sys_prompt)} characters")
                    
                    # Send text for analysis
                    analysis_result = send_text_to_remote_api(structured_text, session_id_key=f"{session_id}_analysis", formatted_system_prompt=sys_prompt)
                    
                    if analysis_result and not analysis_result.startswith("ERROR"):
                        # Parse and store analysis results
                        import json
                        import re
                        try:
                            # Clean up the response - extract JSON from possible markdown or extra text
                            clean_result = analysis_result.strip()
                            logger.info(f"Raw analysis result length: {len(clean_result)} characters")
                            
                            # Try to extract JSON from markdown code blocks
                            if "```" in clean_result:
                                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_result)
                                if json_match:
                                    clean_result = json_match.group(1).strip()
                                    logger.info(f"Extracted JSON from markdown block")
                            
                            # Try to find JSON array if response has extra text
                            if not clean_result.startswith('[') and not clean_result.startswith('{'):
                                # Look for JSON array in the response
                                array_match = re.search(r'(\[[\s\S]*\])', clean_result)
                                if array_match:
                                    clean_result = array_match.group(1).strip()
                                    logger.info(f"Extracted JSON array from text")
                            
                            logger.info(f"Clean result starts with: {clean_result[:100] if len(clean_result) > 100 else clean_result}")
                            analysis_data = json.loads(clean_result)
                            logger.info(f"Parsed JSON type: {type(analysis_data).__name__}")
                            
                            # Handle both list format and dict with "terms" key
                            terms_list = []
                            if isinstance(analysis_data, list):
                                terms_list = analysis_data
                                logger.info(f"Analysis data is a list with {len(terms_list)} items")
                            elif isinstance(analysis_data, dict):
                                if "terms" in analysis_data:
                                    terms_list = analysis_data["terms"]
                                    logger.info(f"Analysis data is a dict with 'terms' key, {len(terms_list)} items")
                                else:
                                    logger.warning(f"Analysis data is dict but no 'terms' key. Keys: {list(analysis_data.keys())}")
                            
                            if terms_list:
                                logger.info(f"Parsed {len(terms_list)} terms from analysis result")
                                # Store individual terms
                                for term_data in terms_list:
                                    term_doc = {
                                        "session_id": session_id,
                                        "term_id": term_data.get("term_id"),
                                        "term_text": term_data.get("term_text"),
                                        "is_valid_sharia": term_data.get("is_valid_sharia", False),
                                        "sharia_issue": term_data.get("sharia_issue"),
                                        "modified_term": term_data.get("modified_term"),
                                        "reference_number": term_data.get("reference_number"),
                                        "aaoifi_evidence": term_data.get("aaoifi_evidence"),
                                        "analyzed_at": datetime.datetime.now()
                                    }
                                    terms_collection.insert_one(term_doc)
                                
                                # Update session status
                                contracts_collection.update_one(
                                    {"_id": session_id},
                                    {"$set": {
                                        "status": "completed",
                                        "analysis_result": {"terms": terms_list},
                                        "terms_count": len(terms_list),
                                        "completed_at": datetime.datetime.now()
                                    }}
                                )
                                logger.info(f"Analysis completed successfully with {len(terms_list)} terms for session: {session_id}")
                            else:
                                logger.warning("No terms found in analysis result")
                                contracts_collection.update_one(
                                    {"_id": session_id},
                                    {"$set": {
                                        "status": "completed",
                                        "analysis_result": {"raw_response": analysis_result},
                                        "completed_at": datetime.datetime.now()
                                    }}
                                )
                        except json.JSONDecodeError as je:
                            logger.warning(f"Failed to parse analysis result as JSON: {str(je)}")
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
                        logger.warning(f"No valid analysis result from AI service: {analysis_result}")
                        contracts_collection.update_one(
                            {"_id": session_id},
                            {"$set": {"status": "failed", "error": analysis_result or "AI service unavailable"}}
                        )
                else:
                    logger.warning("No system prompt configured for analysis")
                    contracts_collection.update_one(
                        {"_id": session_id},
                        {"$set": {"status": "failed", "error": "No system prompt configured"}}
                    )
                    
            except Exception as analysis_error:
                logger.error(f"Error during analysis: {str(analysis_error)}")
                import traceback
                traceback.print_exc()
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
            
            # For text input, create simple structured format with paragraph IDs
            paragraphs = text_content.strip().split('\n')
            structured_parts = []
            for idx, para in enumerate(paragraphs):
                if para.strip():
                    structured_parts.append(f"[[ID:para_{idx}]]\n{para.strip()}")
            structured_text = "\n\n".join(structured_parts) if structured_parts else text_content
            
            # Detect contract language for output
            from langdetect import detect
            try:
                detected_lang = detect(text_content[:1000])
                output_language = "العربية" if detected_lang == "ar" else "English"
                logger.info(f"Detected contract language: {detected_lang}, output_language: {output_language}")
            except:
                output_language = "العربية"
                logger.info(f"Language detection failed, defaulting to Arabic")
            
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
            
            # Perform actual analysis using AI service with file_search integration
            try:
                from config.default import DefaultConfig
                from app.services.file_search import FileSearchService
                config = DefaultConfig()
                
                # Step 1: Use file_search to get relevant AAOIFI context
                aaoifi_context = ""
                try:
                    logger.info(f"Starting file search for session: {session_id}")
                    file_search_service = FileSearchService()
                    chunks, extracted_terms = file_search_service.search_chunks(structured_text)
                    
                    if chunks:
                        logger.info(f"File search returned {len(chunks)} relevant AAOIFI chunks")
                        aaoifi_chunks_text = []
                        for chunk in chunks:
                            chunk_text = chunk.get("chunk_text", "")
                            if chunk_text:
                                aaoifi_chunks_text.append(chunk_text)
                        aaoifi_context = "\n\n---\n\n".join(aaoifi_chunks_text)
                        logger.info(f"AAOIFI context length: {len(aaoifi_context)} characters")
                    else:
                        logger.warning("No AAOIFI chunks found from file search")
                        aaoifi_context = "لا توجد مراجع AAOIFI متاحة حالياً"
                except Exception as fs_error:
                    logger.error(f"File search failed: {str(fs_error)}")
                    aaoifi_context = "لا توجد مراجع AAOIFI متاحة حالياً"
                
                # Step 2: Select and format the system prompt
                if analysis_type == "sharia":
                    sys_prompt_template = config.SYS_PROMPT_SHARIA
                else:
                    sys_prompt_template = config.SYS_PROMPT_SHARIA  # Default to Sharia
                
                if sys_prompt_template and sys_prompt_template.startswith("ERROR:"):
                    logger.error(f"Failed to load system prompt: {sys_prompt_template}")
                    sys_prompt_template = ""
                
                if sys_prompt_template:
                    # Format the prompt with output_language and aaoifi_context
                    sys_prompt = sys_prompt_template.format(
                        output_language=output_language,
                        aaoifi_context=aaoifi_context
                    )
                    logger.info(f"Formatted system prompt length: {len(sys_prompt)} characters")
                    
                    # Send text for analysis
                    analysis_result = send_text_to_remote_api(structured_text, session_id_key=f"{session_id}_analysis", formatted_system_prompt=sys_prompt)
                    
                    if analysis_result and not analysis_result.startswith("ERROR"):
                        # Parse and store analysis results
                        import json
                        import re
                        try:
                            # Clean up the response - extract JSON from possible markdown or extra text
                            clean_result = analysis_result.strip()
                            logger.info(f"Raw analysis result length: {len(clean_result)} characters")
                            
                            # Try to extract JSON from markdown code blocks
                            if "```" in clean_result:
                                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_result)
                                if json_match:
                                    clean_result = json_match.group(1).strip()
                                    logger.info(f"Extracted JSON from markdown block")
                            
                            # Try to find JSON array if response has extra text
                            if not clean_result.startswith('[') and not clean_result.startswith('{'):
                                # Look for JSON array in the response
                                array_match = re.search(r'(\[[\s\S]*\])', clean_result)
                                if array_match:
                                    clean_result = array_match.group(1).strip()
                                    logger.info(f"Extracted JSON array from text")
                            
                            logger.info(f"Clean result starts with: {clean_result[:100] if len(clean_result) > 100 else clean_result}")
                            analysis_data = json.loads(clean_result)
                            logger.info(f"Parsed JSON type: {type(analysis_data).__name__}")
                            
                            # Handle both list format and dict with "terms" key
                            terms_list = []
                            if isinstance(analysis_data, list):
                                terms_list = analysis_data
                                logger.info(f"Analysis data is a list with {len(terms_list)} items")
                            elif isinstance(analysis_data, dict):
                                if "terms" in analysis_data:
                                    terms_list = analysis_data["terms"]
                                    logger.info(f"Analysis data is a dict with 'terms' key, {len(terms_list)} items")
                                else:
                                    logger.warning(f"Analysis data is dict but no 'terms' key. Keys: {list(analysis_data.keys())}")
                            
                            if terms_list:
                                logger.info(f"Parsed {len(terms_list)} terms from analysis result")
                                # Store individual terms
                                for term_data in terms_list:
                                    term_doc = {
                                        "session_id": session_id,
                                        "term_id": term_data.get("term_id"),
                                        "term_text": term_data.get("term_text"),
                                        "is_valid_sharia": term_data.get("is_valid_sharia", False),
                                        "sharia_issue": term_data.get("sharia_issue"),
                                        "modified_term": term_data.get("modified_term"),
                                        "reference_number": term_data.get("reference_number"),
                                        "aaoifi_evidence": term_data.get("aaoifi_evidence"),
                                        "analyzed_at": datetime.datetime.now()
                                    }
                                    terms_collection.insert_one(term_doc)
                                
                                # Update session status
                                contracts_collection.update_one(
                                    {"_id": session_id},
                                    {"$set": {
                                        "status": "completed",
                                        "analysis_result": {"terms": terms_list},
                                        "terms_count": len(terms_list),
                                        "completed_at": datetime.datetime.now()
                                    }}
                                )
                                logger.info(f"Text analysis completed successfully with {len(terms_list)} terms for session: {session_id}")
                            else:
                                logger.warning("No terms found in analysis result")
                                contracts_collection.update_one(
                                    {"_id": session_id},
                                    {"$set": {
                                        "status": "completed",
                                        "analysis_result": {"raw_response": analysis_result},
                                        "completed_at": datetime.datetime.now()
                                    }}
                                )
                        except json.JSONDecodeError as je:
                            logger.warning(f"Failed to parse analysis result as JSON: {str(je)}")
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
                        logger.warning(f"No valid analysis result from AI service: {analysis_result}")
                        contracts_collection.update_one(
                            {"_id": session_id},
                            {"$set": {"status": "failed", "error": analysis_result or "AI service unavailable"}}
                        )
                else:
                    logger.warning("No system prompt configured for analysis")
                    contracts_collection.update_one(
                        {"_id": session_id},
                        {"$set": {"status": "failed", "error": "No system prompt configured"}}
                    )
                    
            except Exception as analysis_error:
                logger.error(f"Error during text analysis: {str(analysis_error)}")
                import traceback
                traceback.print_exc()
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