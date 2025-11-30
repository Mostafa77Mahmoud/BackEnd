"""
Analysis Upload Routes

File upload and analysis endpoints - matches old api_server.py format.
"""

import os
import re
import uuid
import json
import datetime
import tempfile
import traceback
import logging
from flask import request, jsonify, current_app
from docx import Document as DocxDocument
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

from app.routes import analysis_bp
from app.services.database import get_contracts_collection, get_terms_collection
from app.services.document_processor import build_structured_text_for_analysis
from app.services.ai_service import send_text_to_remote_api, extract_text_from_file as ai_extract_text
from app.services.cloudinary_service import upload_to_cloudinary_helper, CLOUDINARY_AVAILABLE
from app.utils.file_helpers import ensure_dir, clean_filename, download_file_from_url
from app.utils.text_processing import clean_model_response, generate_safe_public_id
from app.utils.analysis_helpers import TEMP_PROCESSING_FOLDER

logger = logging.getLogger(__name__)

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    cloudinary = None
    logger.warning("Cloudinary not available")


@analysis_bp.route('/analyze', methods=['POST'])
def analyze_file():
    """Upload and analyze a contract file - matches old api_server.py format exactly."""
    session_id_local = str(uuid.uuid4())
    logger.info(f"Starting file analysis for session: {session_id_local}")

    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable")
        return jsonify({"error": "Database service unavailable."}), 503

    if "file" not in request.files:
        logger.warning("No file sent in request")
        return jsonify({"error": "No file sent."}), 400

    uploaded_file_storage = request.files["file"]
    if not uploaded_file_storage or not uploaded_file_storage.filename:
        logger.warning("Invalid file in request")
        return jsonify({"error": "Invalid file."}), 400

    original_filename = clean_filename(uploaded_file_storage.filename)
    logger.info(f"Processing file: {original_filename} for session: {session_id_local}")

    # Cloudinary folder structure
    CLOUDINARY_BASE_FOLDER = current_app.config.get('CLOUDINARY_BASE_FOLDER', 'shariaa_analyzer_uploads')
    CLOUDINARY_ORIGINAL_UPLOADS_SUBFOLDER = current_app.config.get('CLOUDINARY_ORIGINAL_UPLOADS_SUBFOLDER', 'original_contracts')
    CLOUDINARY_ANALYSIS_RESULTS_SUBFOLDER = current_app.config.get('CLOUDINARY_ANALYSIS_RESULTS_SUBFOLDER', 'analysis_results_json')
    
    original_upload_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id_local}/{CLOUDINARY_ORIGINAL_UPLOADS_SUBFOLDER}"
    analysis_results_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id_local}/{CLOUDINARY_ANALYSIS_RESULTS_SUBFOLDER}"

    original_cloudinary_info = None
    analysis_results_cloudinary_info = None
    temp_processing_file_path = None
    temp_analysis_results_path = None

    try:
        file_base, _ = os.path.splitext(original_filename)

        # Upload original file to Cloudinary
        if CLOUDINARY_AVAILABLE and cloudinary:
            safe_public_id = generate_safe_public_id(file_base, "original")
            original_upload_result = cloudinary.uploader.upload(
                uploaded_file_storage,
                folder=original_upload_cloudinary_folder,
                public_id=safe_public_id,
                resource_type="auto",
                overwrite=True
            )

            if not original_upload_result or not original_upload_result.get("secure_url"):
                logger.error("Cloudinary upload failed for original file")
                raise Exception("Cloudinary upload failed for original file.")

            original_cloudinary_info = {
                "url": original_upload_result.get("secure_url"),
                "public_id": original_upload_result.get("public_id"),
                "format": original_upload_result.get("format"),
                "user_facing_filename": original_filename
            }
            logger.info(f"Original file uploaded to Cloudinary: {original_cloudinary_info['url']}")

            # Download for processing
            temp_processing_file_path = download_file_from_url(
                original_cloudinary_info["url"], 
                original_filename, 
                TEMP_PROCESSING_FOLDER
            )
            if not temp_processing_file_path:
                logger.error("Failed to download original file from Cloudinary for processing")
                raise Exception("Failed to download original file from Cloudinary for processing.")
                
            effective_ext = f".{original_cloudinary_info['format']}" if original_cloudinary_info['format'] else os.path.splitext(original_filename)[1].lower()
        else:
            # Fallback: save locally if Cloudinary not available
            ensure_dir(TEMP_PROCESSING_FOLDER)
            temp_processing_file_path = os.path.join(TEMP_PROCESSING_FOLDER, f"{session_id_local}_{original_filename}")
            uploaded_file_storage.save(temp_processing_file_path)
            effective_ext = os.path.splitext(original_filename)[1].lower()
            original_cloudinary_info = {
                "url": f"local://{temp_processing_file_path}",
                "public_id": None,
                "format": effective_ext.replace(".", ""),
                "user_facing_filename": original_filename
            }
            logger.info(f"File saved locally (Cloudinary unavailable): {temp_processing_file_path}")

        detected_lang = 'ar'
        original_contract_plain = ""
        original_contract_markdown = None
        generated_markdown_from_docx = None
        analysis_input_text = None
        original_format_to_store = effective_ext.replace(".", "") if effective_ext else "unknown"

        logger.info(f"Processing file with extension: {effective_ext}")

        if effective_ext == ".docx":
            logger.info("Processing DOCX file")
            doc = DocxDocument(temp_processing_file_path)
            analysis_input_text, original_contract_plain = build_structured_text_for_analysis(doc)
            generated_markdown_from_docx = analysis_input_text
            original_format_to_store = "docx"
            logger.info(f"Extracted {len(original_contract_plain)} characters from DOCX")
            
        elif effective_ext in [".pdf", ".txt"]:
            logger.info(f"Processing {effective_ext.upper()} file")
            extracted_markdown_from_llm = ai_extract_text(temp_processing_file_path)
            if extracted_markdown_from_llm is None:
                logger.error(f"Text extraction failed for {effective_ext}")
                raise ValueError(f"Text extraction failed for {effective_ext}.")
            original_contract_markdown = extracted_markdown_from_llm
            analysis_input_text = original_contract_markdown
            if extracted_markdown_from_llm:
                original_contract_plain = re.sub(
                    r'^#+\s*|\*\*|\*|__|`|\[\[.*?\]\]', 
                    '', 
                    extracted_markdown_from_llm, 
                    flags=re.MULTILINE
                ).strip()
            original_format_to_store = effective_ext.replace(".", "")
            logger.info(f"Extracted {len(original_contract_plain)} characters from {effective_ext.upper()}")
        else:
            logger.error(f"Unsupported file type: {effective_ext}")
            return jsonify({"error": f"Unsupported file type after upload: {effective_ext}"}), 400

        # Detect language
        if original_contract_plain and len(original_contract_plain) > 20:
            try:
                detected_lang = 'ar' if detect(original_contract_plain[:1000]) == 'ar' else 'en'
                logger.info(f"Detected contract language: {detected_lang}")
            except LangDetectException:
                logger.warning("Language detection failed, defaulting to Arabic")

        # Load and format system prompt
        from config.default import DefaultConfig
        config = DefaultConfig()
        sys_prompt = config.SYS_PROMPT
        if not sys_prompt:
            logger.error("System prompt not loaded - check prompts/ directory")
            raise ValueError("System prompt configuration error.")
        formatted_sys_prompt = sys_prompt.format(output_language=detected_lang)
        
        if not analysis_input_text or not analysis_input_text.strip():
            logger.error("Analysis input text is empty")
            raise ValueError("Analysis input text is empty.")

        # Send to AI for analysis
        logger.info("Sending contract to LLM for analysis")
        external_response_text = send_text_to_remote_api(
            analysis_input_text, 
            f"{session_id_local}_analysis_final", 
            formatted_sys_prompt
        )
        
        if not external_response_text or external_response_text.startswith(("ERROR_PROMPT_BLOCKED", "ERROR_CONTENT_BLOCKED")):
            logger.error(f"Invalid/blocked response from analysis: {external_response_text}")
            raise ValueError(f"Invalid/blocked response from analysis: {external_response_text or 'No response'}")

        # Parse analysis results
        logger.info("Parsing LLM analysis results")
        analysis_results_list = json.loads(clean_model_response(external_response_text))
        if not isinstance(analysis_results_list, list):
            analysis_results_list = []

        logger.info(f"Analysis completed with {len(analysis_results_list)} terms identified")

        # Save analysis results to temp JSON file
        with tempfile.NamedTemporaryFile(
            mode='w', 
            encoding='utf-8', 
            suffix='.json', 
            dir=TEMP_PROCESSING_FOLDER, 
            delete=False
        ) as tmp_json_file:
            json.dump(analysis_results_list, tmp_json_file, ensure_ascii=False, indent=2)
            temp_analysis_results_path = tmp_json_file.name

        # Upload analysis results to Cloudinary
        if temp_analysis_results_path and CLOUDINARY_AVAILABLE:
            results_safe_public_id = generate_safe_public_id(file_base, "analysis_results")
            results_upload_result = upload_to_cloudinary_helper(
                temp_analysis_results_path,
                analysis_results_cloudinary_folder,
                resource_type="raw",
                public_id_prefix="analysis_results",
                custom_public_id=results_safe_public_id
            )
            if results_upload_result:
                analysis_results_cloudinary_info = {
                    "url": results_upload_result.get("secure_url"),
                    "public_id": results_upload_result.get("public_id"),
                    "format": results_upload_result.get("format", "json"),
                    "user_facing_filename": "analysis_results.json"
                }
                logger.info("Analysis results uploaded to Cloudinary")

        # Save contract document to database
        contract_doc = {
            "_id": session_id_local,
            "session_id": session_id_local,
            "original_filename": original_filename,
            "original_cloudinary_info": original_cloudinary_info,
            "analysis_results_cloudinary_info": analysis_results_cloudinary_info,
            "original_format": original_format_to_store,
            "original_contract_plain": original_contract_plain,
            "original_contract_markdown": original_contract_markdown,
            "generated_markdown_from_docx": generated_markdown_from_docx,
            "detected_contract_language": detected_lang,
            "analysis_timestamp": datetime.datetime.now(datetime.timezone.utc),
            "confirmed_terms": {},
            "interactions": [],
            "modified_contract_info": None,
            "marked_contract_info": None,
            "pdf_preview_info": {}
        }
        contracts_collection.insert_one(contract_doc)
        logger.info(f"Contract document saved to database for session: {session_id_local}")

        # Save terms to database
        terms_to_insert = [
            {"session_id": session_id_local, **term} 
            for term in analysis_results_list 
            if isinstance(term, dict) and "term_id" in term
        ]
        if terms_to_insert:
            terms_collection.insert_many(terms_to_insert)
            logger.info(f"Inserted {len(terms_to_insert)} terms to database")

        # Build response matching old API format exactly
        response_payload = {
            "message": "Contract analyzed successfully.",
            "analysis_results": analysis_results_list,
            "session_id": session_id_local,
            "original_contract_plain": original_contract_plain,
            "detected_contract_language": detected_lang,
            "original_cloudinary_url": original_cloudinary_info.get("url") if original_cloudinary_info else None
        }
        response = jsonify(response_payload)
        response.set_cookie(
            "session_id", 
            session_id_local, 
            max_age=86400*30, 
            httponly=True, 
            samesite='Lax', 
            secure=request.is_secure
        )

        logger.info(f"Analysis completed successfully for session: {session_id_local}")
        return response

    except json.JSONDecodeError as je:
        logger.error(f"JSON parse error in analysis for session {session_id_local}: {je}")
        traceback.print_exc()
        return jsonify({"error": f"Failed to parse analysis response: {str(je)}"}), 500
        
    except Exception as e:
        logger.error(f"Analysis failed for session {session_id_local}: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500
        
    finally:
        # Cleanup temporary files
        if temp_processing_file_path and os.path.exists(temp_processing_file_path):
            try:
                os.remove(temp_processing_file_path)
                logger.debug("Cleaned up temporary processing file")
            except Exception as e_clean:
                logger.warning(f"Error deleting temp original file: {e_clean}")
        if temp_analysis_results_path and os.path.exists(temp_analysis_results_path):
            try:
                os.remove(temp_analysis_results_path)
                logger.debug("Cleaned up temporary analysis results file")
            except Exception as e_clean:
                logger.warning(f"Error deleting temp analysis JSON file: {e_clean}")
