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
import time
from flask import request, jsonify, current_app, g
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
from app.utils.logging_utils import (
    get_logger, get_trace_id, create_error_response, 
    RequestTimer, log_request_summary,
    RequestTracer, set_request_tracer, get_request_tracer, clear_request_tracer
)

logger = get_logger(__name__)

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    cloudinary = None
    logger.warning("Cloudinary not available")


def normalize_term_ids(terms_list):
    """
    Normalize term_id values to the expected format: clause_0, clause_1, clause_2, etc.
    This ensures frontend compatibility regardless of what the AI model outputs.
    Guarantees unique clause IDs by tracking used numbers.
    """
    if not terms_list or not isinstance(terms_list, list):
        return terms_list
    
    normalized = []
    used_ids = set()
    next_clause_num = 1
    
    for term in terms_list:
        if not isinstance(term, dict):
            continue
            
        original_id = term.get("term_id", "")
        original_id_lower = original_id.lower() if original_id else ""
        
        if "preamble" in original_id_lower or "تمهيدي" in original_id_lower or "ديباجة" in original_id_lower:
            new_id = "clause_0"
        elif original_id_lower.startswith("clause_"):
            suffix = original_id_lower.replace("clause_", "")
            if suffix.isdigit():
                num = int(suffix)
                if num > 0:
                    new_id = f"clause_{num}"
                else:
                    new_id = "clause_0"
            else:
                new_id = None
        else:
            new_id = None
        
        if new_id is None or new_id in used_ids:
            while f"clause_{next_clause_num}" in used_ids:
                next_clause_num += 1
            new_id = f"clause_{next_clause_num}"
            next_clause_num += 1
        
        used_ids.add(new_id)
        term["term_id"] = new_id
        normalized.append(term)
    
    return normalized


def create_analysis_error_response(error_type: str, message: str, details: dict = None, status_code: int = 500):
    """Create a standardized error response for analysis endpoints."""
    response_data = create_error_response(error_type, message, details or {})
    return jsonify(response_data), status_code


@analysis_bp.route('/analyze', methods=['POST'])
def analyze_file():
    """Upload and analyze a contract file - matches old api_server.py format exactly."""
    timer = RequestTimer()
    timer.start_step("initialization")
    
    session_id_local = str(uuid.uuid4())
    file_size = 0
    extracted_chars = 0
    file_search_status = "not_started"
    analysis_status = "not_started"
    
    tracer = RequestTracer(endpoint="/analyze")
    set_request_tracer(tracer)
    tracer.set_metadata("session_id", session_id_local)
    
    logger.info(f"Starting analysis for session: {session_id_local}")

    tracer.start_step("1_initialization", {"request_method": "POST", "endpoint": "/analyze"})
    
    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
    if contracts_collection is None or terms_collection is None:
        logger.error("Database unavailable")
        tracer.record_error("database_error", "Database service unavailable")
        tracer.end_step(status="error", error="Database unavailable")
        trace_path = tracer.save_trace()
        logger.info(f"Trace saved: {trace_path}")
        return create_analysis_error_response(
            "DATABASE_ERROR", 
            "Database service unavailable",
            status_code=503
        )

    if "file" not in request.files:
        logger.warning("No file in request")
        tracer.record_error("validation_error", "No file sent")
        tracer.end_step(status="error", error="No file in request")
        trace_path = tracer.save_trace()
        logger.info(f"Trace saved: {trace_path}")
        return create_analysis_error_response(
            "VALIDATION_ERROR",
            "No file sent",
            status_code=400
        )

    uploaded_file_storage = request.files["file"]
    if not uploaded_file_storage or not uploaded_file_storage.filename:
        logger.warning("Invalid file")
        tracer.record_error("validation_error", "Invalid file")
        tracer.end_step(status="error", error="Invalid file")
        trace_path = tracer.save_trace()
        logger.info(f"Trace saved: {trace_path}")
        return create_analysis_error_response(
            "VALIDATION_ERROR",
            "Invalid file",
            status_code=400
        )

    original_filename = clean_filename(uploaded_file_storage.filename)
    tracer.set_metadata("original_filename", original_filename)
    logger.info(f"Processing: {original_filename}")
    tracer.end_step({"filename": original_filename, "db_connected": True})
    timer.end_step()

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
        timer.start_step("upload")
        tracer.start_step("2_file_upload", {"filename": original_filename, "cloudinary_available": CLOUDINARY_AVAILABLE})
        file_base, _ = os.path.splitext(original_filename)

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
                logger.error("Cloudinary upload failed")
                tracer.record_error("upload_error", "Cloudinary upload failed")
                tracer.end_step(status="error", error="Cloudinary upload failed")
                trace_path = tracer.save_trace()
                logger.info(f"Trace saved: {trace_path}")
                return create_analysis_error_response(
                    "UPLOAD_ERROR",
                    "Failed to upload file to storage",
                    status_code=500
                )

            file_size = original_upload_result.get("bytes", 0)
            original_cloudinary_info = {
                "url": original_upload_result.get("secure_url"),
                "public_id": original_upload_result.get("public_id"),
                "format": original_upload_result.get("format"),
                "user_facing_filename": original_filename
            }
            logger.info(f"Uploaded to Cloudinary ({file_size} bytes)")

            temp_processing_file_path = download_file_from_url(
                original_cloudinary_info["url"], 
                original_filename, 
                TEMP_PROCESSING_FOLDER
            )
            if not temp_processing_file_path:
                logger.error("Download from Cloudinary failed")
                tracer.record_error("download_error", "Failed to download file for processing")
                tracer.end_step(status="error", error="Download from Cloudinary failed")
                trace_path = tracer.save_trace()
                logger.info(f"Trace saved: {trace_path}")
                return create_analysis_error_response(
                    "DOWNLOAD_ERROR",
                    "Failed to download file for processing",
                    status_code=500
                )
                
            effective_ext = f".{original_cloudinary_info['format']}" if original_cloudinary_info['format'] else os.path.splitext(original_filename)[1].lower()
        else:
            ensure_dir(TEMP_PROCESSING_FOLDER)
            temp_processing_file_path = os.path.join(TEMP_PROCESSING_FOLDER, f"{session_id_local}_{original_filename}")
            uploaded_file_storage.save(temp_processing_file_path)
            file_size = os.path.getsize(temp_processing_file_path)
            effective_ext = os.path.splitext(original_filename)[1].lower()
            original_cloudinary_info = {
                "url": f"local://{temp_processing_file_path}",
                "public_id": None,
                "format": effective_ext.replace(".", ""),
                "user_facing_filename": original_filename
            }
            logger.info(f"Saved locally ({file_size} bytes)")
        
        tracer.end_step({
            "file_size_bytes": file_size,
            "storage_type": "cloudinary" if CLOUDINARY_AVAILABLE else "local",
            "cloudinary_url": original_cloudinary_info.get("url") if original_cloudinary_info else None
        })
        timer.end_step()

        timer.start_step("text_extraction")
        tracer.start_step("3_text_extraction", {"file_extension": effective_ext})
        detected_lang = 'ar'
        original_contract_plain = ""
        original_contract_markdown = None
        generated_markdown_from_docx = None
        analysis_input_text = None
        original_format_to_store = effective_ext.replace(".", "") if effective_ext else "unknown"

        logger.debug(f"Extension: {effective_ext}")

        if effective_ext == ".docx":
            logger.info("Processing DOCX")
            doc = DocxDocument(temp_processing_file_path)
            analysis_input_text, original_contract_plain = build_structured_text_for_analysis(doc)
            generated_markdown_from_docx = analysis_input_text
            original_format_to_store = "docx"
            extracted_chars = len(original_contract_plain)
            logger.info(f"Extracted {extracted_chars} chars from DOCX")
            
        elif effective_ext in [".pdf", ".txt"]:
            logger.info(f"Processing {effective_ext.upper()}")
            extracted_markdown_from_llm = ai_extract_text(temp_processing_file_path)
            if extracted_markdown_from_llm is None:
                logger.error(f"Extraction failed for {effective_ext}")
                tracer.record_error("extraction_error", f"Failed to extract text from {effective_ext}")
                tracer.end_step(status="error", error=f"Extraction failed for {effective_ext}")
                trace_path = tracer.save_trace()
                logger.info(f"Trace saved: {trace_path}")
                return create_analysis_error_response(
                    "EXTRACTION_ERROR",
                    f"Failed to extract text from {effective_ext} file",
                    status_code=500
                )
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
            extracted_chars = len(original_contract_plain)
            logger.info(f"Extracted {extracted_chars} chars from {effective_ext.upper()}")
        else:
            logger.error(f"Unsupported type: {effective_ext}")
            tracer.record_error("validation_error", f"Unsupported file type: {effective_ext}")
            tracer.end_step(status="error", error=f"Unsupported: {effective_ext}")
            trace_path = tracer.save_trace()
            logger.info(f"Trace saved: {trace_path}")
            return create_analysis_error_response(
                "VALIDATION_ERROR",
                f"Unsupported file type: {effective_ext}",
                status_code=400
            )
        
        tracer.set_metadata("extracted_chars", extracted_chars)
        tracer.end_step({
            "format": original_format_to_store,
            "extracted_chars": extracted_chars,
            "has_markdown": bool(original_contract_markdown or generated_markdown_from_docx)
        })
        timer.end_step()

        if original_contract_plain and len(original_contract_plain) > 20:
            try:
                detected_lang = 'ar' if detect(original_contract_plain[:1000]) == 'ar' else 'en'
                logger.debug(f"Language: {detected_lang}")
            except LangDetectException:
                logger.debug("Language detection failed, defaulting to Arabic")

        from config.default import DefaultConfig
        sys_prompt = DefaultConfig.SYS_PROMPT
        if not sys_prompt:
            logger.error("System prompt not loaded")
            tracer.start_step("3b_config_validation", {"check": "system_prompt"})
            tracer.record_error("config_error", "System prompt not loaded")
            tracer.end_step(status="error", error="System prompt not loaded")
            trace_path = tracer.save_trace()
            logger.info(f"Trace saved: {trace_path}")
            return create_analysis_error_response(
                "CONFIG_ERROR",
                "System prompt configuration error",
                status_code=500
            )
        
        timer.start_step("file_search")
        tracer.start_step("4_file_search_aaoifi", {"input_text_length": len(analysis_input_text) if analysis_input_text else 0})
        aaoifi_context = ""
        aaoifi_chunks = []
        file_search_status = "in_progress"
        extracted_terms = []
        
        try:
            logger.info("Starting AAOIFI context retrieval")
            from app.services.file_search import FileSearchService
            file_search_service = FileSearchService()
            aaoifi_chunks, extracted_terms = file_search_service.search_chunks(analysis_input_text, top_k=10)
            
            tracer.add_sub_step("extracted_terms", {
                "count": len(extracted_terms),
                "terms": extracted_terms
            })
            
            if aaoifi_chunks:
                logger.info(f"Retrieved {len(aaoifi_chunks)} chunks")
                chunk_texts = []
                for idx, chunk in enumerate(aaoifi_chunks, 1):
                    chunk_text = chunk.get("chunk_text", "")
                    if chunk_text:
                        chunk_texts.append(f"[معيار AAOIFI {idx}]\n{chunk_text}")
                aaoifi_context = "\n\n".join(chunk_texts) if chunk_texts else ""
                logger.info(f"Context size: {len(aaoifi_context)} chars")
                file_search_status = "success"
                
                tracer.add_sub_step("aaoifi_chunks", {
                    "count": len(aaoifi_chunks),
                    "chunks": aaoifi_chunks
                })
            else:
                logger.warning("No chunks retrieved")
                file_search_status = "no_results"
        except Exception as e:
            logger.warning(f"File search failed: {e}")
            file_search_status = f"error: {str(e)[:50]}"
            aaoifi_context = ""
            tracer.record_error("file_search_error", str(e))
        
        tracer.end_step({
            "status": file_search_status,
            "chunks_count": len(aaoifi_chunks),
            "context_length": len(aaoifi_context),
            "extracted_terms_count": len(extracted_terms)
        })
        timer.end_step()
        
        formatted_sys_prompt = sys_prompt.format(
            output_language=detected_lang,
            aaoifi_context=aaoifi_context
        )
        
        if not analysis_input_text or not analysis_input_text.strip():
            logger.error("Empty analysis input")
            tracer.start_step("4b_input_validation", {"check": "analysis_input_text"})
            tracer.record_error("extraction_error", "No text could be extracted from the file")
            tracer.end_step(status="error", error="Empty analysis input")
            trace_path = tracer.save_trace()
            logger.info(f"Trace saved: {trace_path}")
            return create_analysis_error_response(
                "EXTRACTION_ERROR",
                "No text could be extracted from the file",
                status_code=400
            )

        timer.start_step("ai_analysis")
        tracer.start_step("5_ai_analysis", {
            "input_text_length": len(analysis_input_text) if analysis_input_text else 0,
            "prompt_length": len(formatted_sys_prompt),
            "detected_language": detected_lang
        })
        analysis_status = "in_progress"
        logger.info("Sending to LLM for analysis")
        
        external_response_text = send_text_to_remote_api(
            analysis_input_text, 
            f"{session_id_local}_analysis_final", 
            formatted_sys_prompt
        )
        
        tracer.add_sub_step("llm_response_received", {
            "response_length": len(external_response_text) if external_response_text else 0,
            "response_preview": external_response_text[:500] if external_response_text else None
        })
        
        if not external_response_text or external_response_text.startswith(("ERROR_PROMPT_BLOCKED", "ERROR_CONTENT_BLOCKED")):
            logger.error(f"LLM response blocked: {external_response_text}")
            analysis_status = "blocked"
            tracer.record_error("ai_blocked", f"Response blocked: {external_response_text}")
            tracer.end_step(status="error", error="Content blocked")
            trace_path = tracer.save_trace()
            logger.info(f"Trace saved: {trace_path}")
            return create_analysis_error_response(
                "AI_ERROR",
                "Analysis was blocked by content filter",
                {"response_code": external_response_text},
                status_code=500
            )

        logger.info("Parsing analysis results")
        analysis_results_list = json.loads(clean_model_response(external_response_text))
        if not isinstance(analysis_results_list, list):
            analysis_results_list = []

        analysis_results_list = normalize_term_ids(analysis_results_list)
        
        analysis_status = "success"
        tracer.add_sub_step("analysis_parsed", {
            "terms_count": len(analysis_results_list),
            "terms": analysis_results_list
        })
        logger.info(f"Analysis complete: {len(analysis_results_list)} terms")
        tracer.end_step({
            "status": "success",
            "terms_count": len(analysis_results_list),
            "response_length": len(external_response_text) if external_response_text else 0
        })
        timer.end_step()

        timer.start_step("save_results")
        tracer.start_step("6_save_results", {"terms_count": len(analysis_results_list)})
        with tempfile.NamedTemporaryFile(
            mode='w', 
            encoding='utf-8', 
            suffix='.json', 
            dir=TEMP_PROCESSING_FOLDER, 
            delete=False
        ) as tmp_json_file:
            json.dump(analysis_results_list, tmp_json_file, ensure_ascii=False, indent=2)
            temp_analysis_results_path = tmp_json_file.name

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
                logger.debug("Results uploaded to Cloudinary")

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
        logger.info(f"Saved to database: {session_id_local}")

        terms_to_insert = [
            {"session_id": session_id_local, **term} 
            for term in analysis_results_list 
            if isinstance(term, dict) and "term_id" in term
        ]
        if terms_to_insert:
            terms_collection.insert_many(terms_to_insert)
            logger.debug(f"Inserted {len(terms_to_insert)} terms")
        
        tracer.add_sub_step("mongodb_saved", {
            "contract_id": session_id_local,
            "terms_inserted": len(terms_to_insert)
        })
        tracer.end_step({
            "session_id": session_id_local,
            "terms_saved": len(terms_to_insert),
            "cloudinary_uploaded": bool(analysis_results_cloudinary_info)
        })
        timer.end_step()

        timing_summary = timer.get_summary()
        # Get token usage from tracer for session total
        trace_data = tracer.get_trace()
        token_usage = trace_data.get("summary", {}).get("token_usage", {})
        log_request_summary(logger, {
            "trace_id": get_trace_id(),
            "file_size": file_size,
            "extracted_chars": extracted_chars,
            "analysis_status": analysis_status,
            "file_search_status": file_search_status,
            "total_time": timing_summary["total_time_seconds"],
            "step_times": timing_summary["steps"],
            "token_usage": token_usage
        })

        response_payload = {
            "status": "success",
            "message": "Contract analyzed successfully.",
            "analysis_results": analysis_results_list,
            "session_id": session_id_local,
            "original_contract_plain": original_contract_plain,
            "detected_contract_language": detected_lang,
            "original_cloudinary_url": original_cloudinary_info.get("url") if original_cloudinary_info else None,
            "trace_id": get_trace_id()
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

        trace_path = tracer.save_trace()
        logger.info(f"Trace saved: {trace_path}")
        logger.info(f"Analysis successful: {session_id_local}")
        return response

    except json.JSONDecodeError as je:
        analysis_status = "json_error"
        logger.exception(f"JSON parse error: {je}")
        tracer.record_error("json_decode_error", str(je))
        timing_summary = timer.get_summary()
        log_request_summary(logger, {
            "trace_id": get_trace_id(),
            "file_size": file_size,
            "extracted_chars": extracted_chars,
            "analysis_status": analysis_status,
            "file_search_status": file_search_status,
            "total_time": timing_summary["total_time_seconds"],
            "step_times": timing_summary["steps"]
        })
        trace_path = tracer.save_trace()
        logger.info(f"Trace saved: {trace_path}")
        return create_analysis_error_response(
            "PARSE_ERROR",
            "Failed to parse analysis response",
            {"error_detail": str(je)},
            status_code=500
        )
        
    except Exception as e:
        analysis_status = "exception"
        logger.exception(f"Analysis failed: {e}")
        tracer.record_error("exception", str(e))
        timing_summary = timer.get_summary()
        log_request_summary(logger, {
            "trace_id": get_trace_id(),
            "file_size": file_size,
            "extracted_chars": extracted_chars,
            "analysis_status": analysis_status,
            "file_search_status": file_search_status,
            "total_time": timing_summary["total_time_seconds"],
            "step_times": timing_summary["steps"]
        })
        trace_path = tracer.save_trace()
        logger.info(f"Trace saved: {trace_path}")
        return create_analysis_error_response(
            "ANALYSIS_ERROR",
            f"Analysis failed: {str(e)}",
            status_code=500
        )
        
    finally:
        if temp_processing_file_path and os.path.exists(temp_processing_file_path):
            try:
                os.remove(temp_processing_file_path)
                logger.debug("Cleaned temp processing file")
            except Exception as e_clean:
                logger.debug(f"Temp file cleanup error: {e_clean}")
        if temp_analysis_results_path and os.path.exists(temp_analysis_results_path):
            try:
                os.remove(temp_analysis_results_path)
                logger.debug("Cleaned temp analysis file")
            except Exception as e_clean:
                logger.debug(f"Temp analysis cleanup error: {e_clean}")
