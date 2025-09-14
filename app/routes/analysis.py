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
                if analysis_type == "sharia":
                    sys_prompt = config.SYS_PROMPT_SHARIA
                elif analysis_type == "legal":
                    sys_prompt = config.SYS_PROMPT_LEGAL 
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
                if analysis_type == "sharia":
                    sys_prompt = config.SYS_PROMPT_SHARIA
                elif analysis_type == "legal":
                    sys_prompt = config.SYS_PROMPT_LEGAL 
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
        if '_id' in session_doc and isinstance(session_doc['_id'], ObjectId):
            session_doc['_id'] = str(session_doc['_id'])
        
        for key, value in session_doc.items():
            if isinstance(value, datetime.datetime):
                session_doc[key] = value.isoformat()
            elif isinstance(value, ObjectId):
                session_doc[key] = str(value)
        
        # Process terms
        for term in terms_list:
            if '_id' in term and isinstance(term['_id'], ObjectId):
                term['_id'] = str(term['_id'])
            for key, value in term.items():
                if isinstance(value, datetime.datetime):
                    term[key] = value.isoformat()
                elif isinstance(value, ObjectId):
                    term[key] = str(value)
        
        response_data = {
            "analysis_id": analysis_id,
            "session_details": session_doc,
            "terms": terms_list,
            "terms_count": len(terms_list),
            "status": session_doc.get("status", "unknown"),
            "completed_at": session_doc.get("completed_at"),
            "retrieved_at": datetime.datetime.now().isoformat()
        }
        
        logger.info(f"Analysis results retrieved for: {analysis_id} with {len(terms_list)} terms")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error retrieving analysis results: {str(e)}")
        return jsonify({"error": "Internal server error."}), 500


@analysis_bp.route('/session/<session_id>', methods=['GET'])
def get_session_details(session_id):
    """Get session details by ID."""
    logger.info(f"Fetching session details for: {session_id}")
    
    contracts_collection = get_contracts_collection()
    
    if contracts_collection is None:
        logger.error("Database service unavailable for session details")
        return jsonify({"error": "Database service unavailable."}), 503
    
    try:
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            logger.warning(f"Session not found: {session_id}")
            return jsonify({"error": "Session not found."}), 404
        
        # Convert ObjectId and datetime objects to JSON-serializable format
        from bson import ObjectId
        if '_id' in session_doc and isinstance(session_doc['_id'], ObjectId):
            session_doc['_id'] = str(session_doc['_id'])
        
        for key, value in session_doc.items():
            if isinstance(value, datetime.datetime):
                session_doc[key] = value.isoformat()
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, datetime.datetime):
                        value[sub_key] = sub_value.isoformat()
                    elif isinstance(sub_value, ObjectId):
                        value[sub_key] = str(sub_value)
        
        logger.info(f"Session details retrieved for: {session_id}")
        return jsonify(session_doc), 200
        
    except Exception as e:
        logger.error(f"Error fetching session details: {str(e)}")
        return jsonify({"error": "Internal server error."}), 500


@analysis_bp.route('/terms/<session_id>', methods=['GET'])
def get_session_terms(session_id):
    """Get all terms for a session."""
    logger.info(f"Fetching terms for session: {session_id}")
    
    terms_collection = get_terms_collection()
    
    if terms_collection is None:
        logger.error("Database service unavailable for terms")
        return jsonify({"error": "Database service unavailable."}), 503
    
    try:
        terms_list = list(terms_collection.find({"session_id": session_id}))
        
        # Convert ObjectId and datetime objects to JSON-serializable format
        from bson import ObjectId
        for term in terms_list:
            if '_id' in term and isinstance(term['_id'], ObjectId):
                term['_id'] = str(term['_id'])
            for key, value in term.items():
                if isinstance(value, datetime.datetime):
                    term[key] = value.isoformat()
                elif isinstance(value, ObjectId):
                    term[key] = str(value)
        
        logger.info(f"Retrieved {len(terms_list)} terms for session: {session_id}")
        return jsonify({"terms": terms_list, "count": len(terms_list)}), 200
        
    except Exception as e:
        logger.error(f"Error fetching terms: {str(e)}")
        return jsonify({"error": "Internal server error."}), 500


@analysis_bp.route('/history', methods=['GET'])
def get_analysis_history():
    """Get analysis history."""
    logger.info("Fetching analysis history")
    
    contracts_collection = get_contracts_collection()
    
    if contracts_collection is None:
        logger.error("Database service unavailable for history")
        return jsonify({"error": "Database service unavailable."}), 503
    
    try:
        # Get recent sessions, sorted by creation date
        sessions = list(contracts_collection.find(
            {}, 
            {"_id": 1, "original_filename": 1, "analysis_type": 1, "jurisdiction": 1, "created_at": 1, "status": 1}
        ).sort("created_at", -1).limit(50))
        
        # Convert ObjectId and datetime objects to JSON-serializable format
        from bson import ObjectId
        for session in sessions:
            if '_id' in session and isinstance(session['_id'], ObjectId):
                session['_id'] = str(session['_id'])
            if 'created_at' in session and isinstance(session['created_at'], datetime.datetime):
                session['created_at'] = session['created_at'].isoformat()
        
        logger.info(f"Retrieved {len(sessions)} recent sessions")
        return jsonify({"sessions": sessions, "count": len(sessions)}), 200
        
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        return jsonify({"error": "Internal server error."}), 500


@analysis_bp.route('/stats/user', methods=['GET'])
def get_user_stats():
    """Get user statistics."""
    logger.info("Fetching user statistics")
    
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for stats")
        return jsonify({"error": "Database service unavailable."}), 503
    
    try:
        # Count total sessions
        total_sessions = contracts_collection.count_documents({})
        
        # Count sessions by status
        processing_sessions = contracts_collection.count_documents({"status": "processing"})
        completed_sessions = contracts_collection.count_documents({"status": "completed"})
        
        # Count total terms analyzed
        total_terms = terms_collection.count_documents({})
        
        # Count terms by compliance
        compliant_terms = terms_collection.count_documents({"is_valid_sharia": True})
        non_compliant_terms = terms_collection.count_documents({"is_valid_sharia": False})
        
        stats = {
            "total_sessions": total_sessions,
            "processing_sessions": processing_sessions,
            "completed_sessions": completed_sessions,
            "total_terms_analyzed": total_terms,
            "compliant_terms": compliant_terms,
            "non_compliant_terms": non_compliant_terms,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        logger.info("User statistics retrieved successfully")
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Error fetching user stats: {str(e)}")
        return jsonify({"error": "Internal server error."}), 500


@analysis_bp.route('/preview_contract/<session_id>/<contract_type>', methods=['GET'])
def preview_contract(session_id, contract_type):
    """Generate PDF preview for modified or marked contracts."""
    logger.info(f"Generating PDF preview for {contract_type} contract, session: {session_id}")
    
    contracts_collection = get_contracts_collection()
    
    if contracts_collection is None:
        logger.error("Database service unavailable for PDF preview")
        return jsonify({"error": "Database service unavailable."}), 503
    
    if contract_type not in ["modified", "marked"]:
        logger.warning(f"Invalid contract type requested: {contract_type}")
        return jsonify({"error": "Invalid contract type."}), 400
    
    try:
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            logger.warning(f"Session not found for PDF preview: {session_id}")
            return jsonify({"error": "Session not found."}), 404
        
        # Check if PDF preview already exists
        existing_pdf_info = session_doc.get("pdf_preview_info", {}).get(contract_type)
        if existing_pdf_info and existing_pdf_info.get("url"):
            logger.info(f"Returning existing PDF preview URL for {contract_type}: {existing_pdf_info['url']}")
            return jsonify({"pdf_url": existing_pdf_info["url"]})
        
        # Get source contract info
        source_contract_info = None
        if contract_type == "modified":
            source_contract_info = session_doc.get("modified_contract_info", {}).get("docx_cloudinary_info")
        elif contract_type == "marked":
            source_contract_info = session_doc.get("marked_contract_info", {}).get("docx_cloudinary_info")
        
        if not source_contract_info or not source_contract_info.get("url"):
            logger.warning(f"Source contract for {contract_type} not found")
            return jsonify({"error": f"Source contract for {contract_type} not found. Generate the contract first."}), 404
        
        # Import document processing services
        from app.services.document_processor import convert_docx_to_pdf
        from app.services.cloudinary_service import upload_to_cloudinary_helper
        from app.utils.file_helpers import download_file_from_url
        
        # Download source DOCX from Cloudinary
        temp_dir = tempfile.gettempdir()
        source_filename = source_contract_info.get("user_facing_filename", f"{contract_type}_contract.docx")
        temp_docx_path = download_file_from_url(source_contract_info["url"], source_filename, temp_dir)
        
        if not temp_docx_path:
            logger.error("Failed to download source DOCX for preview")
            return jsonify({"error": "Failed to download source contract for preview."}), 500
        
        # Convert DOCX to PDF
        temp_pdf_path = os.path.join(temp_dir, f"preview_{session_id}_{contract_type}.pdf")
        pdf_success = convert_docx_to_pdf(temp_docx_path, temp_pdf_path)
        
        if not pdf_success or not os.path.exists(temp_pdf_path):
            logger.error("Failed to convert DOCX to PDF")
            return jsonify({"error": "Failed to generate PDF preview."}), 500
        
        # Upload PDF to Cloudinary
        pdf_cloudinary_folder = f"shariaa_analyzer/{session_id}/pdf_previews"
        pdf_cloudinary_result = upload_to_cloudinary_helper(temp_pdf_path, pdf_cloudinary_folder)
        
        if not pdf_cloudinary_result:
            logger.error("Failed to upload PDF to Cloudinary")
            return jsonify({"error": "Failed to upload PDF preview."}), 500
        
        # Update session with PDF info
        pdf_preview_info = session_doc.get("pdf_preview_info", {})
        pdf_preview_info[contract_type] = {
            "url": pdf_cloudinary_result.get("url"),
            "public_id": pdf_cloudinary_result.get("public_id"),
            "user_facing_filename": f"{contract_type}_preview_{session_id[:8]}.pdf",
            "generated_at": datetime.datetime.now()
        }
        
        contracts_collection.update_one(
            {"_id": session_id},
            {"$set": {"pdf_preview_info": pdf_preview_info}}
        )
        
        # Cleanup temp files
        try:
            os.remove(temp_docx_path)
            os.remove(temp_pdf_path)
        except:
            pass
        
        logger.info(f"PDF preview generated successfully for {contract_type} contract")
        return jsonify({"pdf_url": pdf_cloudinary_result.get("url")})
        
    except Exception as e:
        logger.error(f"Error generating PDF preview: {str(e)}")
        return jsonify({"error": "Internal server error during PDF generation."}), 500


@analysis_bp.route('/download_pdf_preview/<session_id>/<contract_type>', methods=['GET'])
def download_pdf_preview(session_id, contract_type):
    """Download PDF preview."""
    logger.info(f"PDF download requested for {contract_type} contract, session: {session_id}")
    
    contracts_collection = get_contracts_collection()
    
    if contracts_collection is None:
        logger.error("Database service unavailable for PDF download")
        return jsonify({"error": "Database service unavailable."}), 503
    
    if contract_type not in ["modified", "marked"]:
        logger.warning(f"Invalid contract type for download: {contract_type}")
        return jsonify({"error": "Invalid contract type."}), 400
    
    try:
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            logger.warning(f"Session not found for PDF download: {session_id}")
            return jsonify({"error": "Session not found."}), 404
        
        pdf_info = session_doc.get("pdf_preview_info", {}).get(contract_type)
        if not pdf_info or not pdf_info.get("url"):
            logger.warning(f"PDF preview URL for {contract_type} contract not available")
            return jsonify({"error": f"PDF preview for {contract_type} contract not available. Generate preview first."}), 404
        
        cloudinary_pdf_url = pdf_info["url"]
        user_facing_filename = pdf_info.get("user_facing_filename", f"{contract_type}_preview_{session_id[:8]}.pdf")
        
        # Import utilities
        from app.utils.file_helpers import clean_filename
        import urllib.parse
        import requests
        
        # Proxy download from Cloudinary
        logger.info(f"Proxying PDF download from Cloudinary: {cloudinary_pdf_url}")
        r = requests.get(cloudinary_pdf_url, stream=True, timeout=120)
        r.raise_for_status()
        
        safe_filename = clean_filename(user_facing_filename)
        encoded_filename = urllib.parse.quote(safe_filename)
        
        logger.info(f"PDF download successful for {contract_type} contract")
        return Response(
            r.iter_content(chunk_size=8192),
            content_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}',
                'Content-Security-Policy': "default-src 'self'",
                'X-Content-Type-Options': 'nosniff'
            }
        )
        
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error fetching PDF from Cloudinary: {http_err.response.status_code}")
        return jsonify({"error": f"Cloudinary denied access to PDF (Status {http_err.response.status_code})."}), http_err.response.status_code if http_err.response.status_code >= 400 else 500
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching PDF from Cloudinary for download: {e}")
        return jsonify({"error": "Could not fetch PDF from cloud storage."}), 500
    except Exception as e:
        logger.error(f"Unexpected error during PDF download proxy: {e}")
        return jsonify({"error": "An unexpected error occurred during download."}), 500


@analysis_bp.route('/feedback/expert', methods=['POST'])
def submit_expert_feedback():
    """Submit expert feedback."""
    logger.info("Processing expert feedback submission")
    
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for expert feedback")
        return jsonify({"error": "Database service is currently unavailable."}), 503
    
    if not request.is_json:
        logger.warning("Non-JSON request received for expert feedback")
        return jsonify({"error": "Content-Type must be application/json."}), 415
    
    data = request.get_json()
    session_id = request.cookies.get("session_id") or data.get("session_id")
    term_id = data.get("term_id")
    feedback_data = data.get("feedback_data")
    expert_user_id = data.get("expert_user_id", "default_expert_id")
    expert_username = data.get("expert_username", "Default Expert")
    
    logger.info(f"Submitting expert feedback for session: {session_id}, term: {term_id}")
    
    if not all([session_id, term_id, feedback_data]):
        logger.warning("Incomplete data for expert feedback")
        return jsonify({"error": "البيانات المطلوبة غير مكتملة (session_id, term_id, feedback_data)"}), 400
    
    try:
        # Get original term
        original_term_doc = terms_collection.find_one({"session_id": session_id, "term_id": term_id})
        snapshot_ai_data = {}
        original_term_text = ""
        
        if original_term_doc:
            original_term_text = original_term_doc.get("term_text", "")
            snapshot_ai_data = {
                "original_ai_is_valid_sharia": original_term_doc.get("is_valid_sharia"),
                "original_ai_sharia_issue": original_term_doc.get("sharia_issue"),
                "original_ai_modified_term": original_term_doc.get("modified_term"),
                "original_ai_reference_number": original_term_doc.get("reference_number")
            }
        
        # Create feedback document
        feedback_doc = {
            "session_id": session_id,
            "term_id": term_id,
            "original_term_text_snapshot": original_term_text,
            "expert_user_id": expert_user_id,
            "expert_username": expert_username,
            "feedback_timestamp": datetime.datetime.now(),
            "ai_initial_analysis_assessment": {
                "is_correct_compliance": feedback_data.get("aiAnalysisApproved"),
            },
            "expert_verdict_is_valid_sharia": feedback_data.get("expertIsValidSharia"),
            "expert_comment_on_term": feedback_data.get("expertComment"),
            "expert_corrected_sharia_issue": feedback_data.get("expertCorrectedShariaIssue"),
            "expert_corrected_reference": feedback_data.get("expertCorrectedReference"),
            "expert_final_suggestion_for_term": feedback_data.get("expertCorrectedSuggestion"),
            "snapshot_ai_data": snapshot_ai_data
        }
        
        # Store in expert feedback collection (create if doesn't exist)
        expert_feedback_collection = get_contracts_collection().database["expert_feedback"]
        expert_feedback_collection.insert_one(feedback_doc)
        
        logger.info(f"Expert feedback saved successfully for session {session_id}, term {term_id}")
        return jsonify({
            "success": True,
            "message": f"تم حفظ ملاحظات الخبير للبند: {term_id}",
            "session_id": session_id,
            "term_id": term_id
        })
        
    except Exception as e:
        logger.error(f"Error saving expert feedback: {str(e)}")
        return jsonify({"error": f"فشل حفظ ملاحظات الخبير: {str(e)}"}), 500


@analysis_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "Shariaa Contract Analyzer",
        "timestamp": datetime.datetime.now().isoformat()
    })