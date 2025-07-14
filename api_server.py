# backend/api_server.py
import os
import uuid
import json
import datetime
import logging
import traceback
import tempfile 
import re 
import urllib.parse
from dotenv import load_dotenv

# Load environment variables from .env file at the very beginning
# This should be the first import to ensure all variables are available
load_dotenv()

from flask import Flask, request, jsonify, Response
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson import ObjectId
from flask_cors import CORS
from langdetect import detect, LangDetectException, DetectorFactory
import cloudinary
import cloudinary.uploader
import cloudinary.api
import requests

# --- Local Imports ---
# These are imported after load_dotenv() to ensure they get the env vars
from config import (
    MONGO_URI, GOOGLE_API_KEY, CLOUDMERSIVE_API_KEY,
    SYS_PROMPT, INTERACTION_PROMPT,
    REVIEW_MODIFICATION_PROMPT, CONTRACT_REGENERATION_PROMPT,
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET,
    CLOUDINARY_BASE_FOLDER, CLOUDINARY_ORIGINAL_UPLOADS_SUBFOLDER,
    CLOUDINARY_ANALYSIS_RESULTS_SUBFOLDER, CLOUDINARY_MODIFIED_CONTRACTS_SUBFOLDER,
    CLOUDINARY_MARKED_CONTRACTS_SUBFOLDER, CLOUDINARY_PDF_PREVIEWS_SUBFOLDER
)
from remote_api import send_text_to_remote_api, get_chat_session, extract_text_from_file
from doc_processing import (
    build_structured_text_for_analysis,
    create_docx_from_llm_markdown,
    convert_docx_to_pdf_cloudmersive,
)
from utils import ensure_dir, clean_filename, clean_model_response, download_file_from_url, upload_to_cloudinary_helper

from docx import Document as DocxDocument
from docx.text.paragraph import Paragraph
from docx.table import Table

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s.%(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Flask App Initialization ---
DetectorFactory.seed = 0
app = Flask(__name__)
CORS(app, origins="*", supports_credentials=True)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# --- Service Configurations ---
try:
    # Validate essential environment variables
    required_vars = ["CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "MONGO_URI", "GOOGLE_API_KEY", "CLOUDMERSIVE_API_KEY"]
    missing_vars = [var for var in required_vars if not globals().get(var)]
    if missing_vars:
        logger.critical(f"Missing critical environment variables: {', '.join(missing_vars)}")
        # In a real production scenario, you might want to exit the application
        # import sys
        # sys.exit(1)

    cloudinary.config(
      cloud_name=CLOUDINARY_CLOUD_NAME,
      api_key=CLOUDINARY_API_KEY,
      api_secret=CLOUDINARY_API_SECRET,
      secure=True
    )
    logger.info("✅ Cloudinary configured successfully.")
except Exception as e:
    logger.critical(f"❌ Cloudinary configuration failed: {e}", exc_info=True)

APP_TEMP_BASE_DIR = os.path.join(tempfile.gettempdir(), "shariaa_analyzer_temp")
TEMP_PROCESSING_FOLDER = os.path.join(APP_TEMP_BASE_DIR, "processing_files")
PDF_PREVIEW_FOLDER = os.path.join(APP_TEMP_BASE_DIR, "pdf_previews_temp_output")

ensure_dir(TEMP_PROCESSING_FOLDER)
ensure_dir(PDF_PREVIEW_FOLDER)
logger.info(f"Temporary processing folder: {TEMP_PROCESSING_FOLDER}")
logger.info(f"Temporary PDF output folder: {PDF_PREVIEW_FOLDER}")

client = None; db = None; contracts_collection = None; terms_collection = None; expert_feedback_collection = None
DB_NAME = "shariaa_analyzer_db"

try:
    logger.info("Attempting to connect to MongoDB...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=45000)
    client.admin.command('ping')
    db = client[DB_NAME]
    contracts_collection = db.contracts
    terms_collection = db.terms
    expert_feedback_collection = db.expert_feedback
    logger.info(f"✅ Successfully connected to MongoDB: {DB_NAME}.")
except Exception as e:
    logger.critical(f"❌ MongoDB connection failed: {e}", exc_info=True)


@app.route("/analyze", methods=["POST"])
def analyze_file():
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for /analyze endpoint.")
        return jsonify({"error": "Database service unavailable."}), 503
    
    if "file" not in request.files:
        logger.warning("Analyze request received with no file part.")
        return jsonify({"error": "No file sent."}), 400
    
    uploaded_file_storage = request.files["file"]
    if not uploaded_file_storage or not uploaded_file_storage.filename:
        logger.warning("Analyze request received with invalid file.")
        return jsonify({"error": "Invalid file."}), 400

    original_filename = clean_filename(uploaded_file_storage.filename)
    session_id_local = str(uuid.uuid4())
    logger.info(f"Starting analysis for session {session_id_local}, filename: '{original_filename}'")
    
    original_upload_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id_local}/{CLOUDINARY_ORIGINAL_UPLOADS_SUBFOLDER}"
    analysis_results_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id_local}/{CLOUDINARY_ANALYSIS_RESULTS_SUBFOLDER}"
    
    temp_processing_file_path = None 
    temp_analysis_results_path = None

    try:
        file_base, _ = os.path.splitext(original_filename)
        
        logger.info(f"Uploading '{original_filename}' to Cloudinary folder: {original_upload_cloudinary_folder}...")
        original_upload_result = cloudinary.uploader.upload(
            uploaded_file_storage, 
            folder=original_upload_cloudinary_folder,
            public_id=f"{file_base}_{uuid.uuid4().hex[:8]}",
            resource_type="auto", 
            overwrite=True
        )

        if not original_upload_result or not original_upload_result.get("secure_url"):
            raise Exception("Cloudinary upload failed for original file.")

        original_cloudinary_info = {
            "url": original_upload_result.get("secure_url"),
            "public_id": original_upload_result.get("public_id"),
            "format": original_upload_result.get("format"),
            "user_facing_filename": original_filename
        }
        logger.info(f"✅ Original file uploaded: {original_cloudinary_info['url']}")

        temp_processing_file_path = download_file_from_url(original_cloudinary_info["url"], original_filename, TEMP_PROCESSING_FOLDER)
        if not temp_processing_file_path:
            raise Exception("Failed to download original file from Cloudinary for processing.")

        effective_ext = f".{original_cloudinary_info['format']}" if original_cloudinary_info['format'] else os.path.splitext(original_filename)[1].lower()
        logger.info(f"Effective file extension for processing: {effective_ext}")
        
        detected_lang = 'ar'
        original_contract_plain = ""
        original_contract_markdown = None
        generated_markdown_from_docx = None
        analysis_input_text = None
        original_format_to_store = effective_ext.replace(".", "") if effective_ext else "unknown"

        if effective_ext == ".docx":
            doc = DocxDocument(temp_processing_file_path)
            analysis_input_text, original_contract_plain = build_structured_text_for_analysis(doc)
            generated_markdown_from_docx = analysis_input_text
            original_format_to_store = "docx"
            logger.info("Successfully built structured markdown from DOCX.")
        elif effective_ext in [".pdf", ".txt"]:
            extracted_markdown_from_llm = extract_text_from_file(temp_processing_file_path) 
            if extracted_markdown_from_llm is None: raise ValueError(f"Text extraction failed for {effective_ext}.")
            original_contract_markdown = extracted_markdown_from_llm
            analysis_input_text = original_contract_markdown
            if extracted_markdown_from_llm:
                original_contract_plain = re.sub(r'^#+\s*|\*\*|\*|__|`|\[\[.*?\]\]', '', extracted_markdown_from_llm, flags=re.MULTILINE).strip()
            original_format_to_store = effective_ext.replace(".", "")
            logger.info(f"Successfully extracted text from {effective_ext} using LLM.")
        else:
            logger.error(f"Unsupported file type after upload: {effective_ext}")
            return jsonify({"error": f"Unsupported file type after upload: {effective_ext}"}), 400

        if original_contract_plain and len(original_contract_plain) > 20:
            try: 
                detected_lang = 'ar' if detect(original_contract_plain[:1000]) == 'ar' else 'en'
                logger.info(f"Detected contract language: {detected_lang}")
            except LangDetectException: 
                logger.warning("Language detection failed, defaulting to Arabic.")
        
        formatted_sys_prompt = SYS_PROMPT.format(output_language=detected_lang)
        if not analysis_input_text or not analysis_input_text.strip(): 
            raise ValueError("Analysis input text is empty.")

        logger.info("Sending text to remote API for analysis...")
        external_response_text = send_text_to_remote_api(analysis_input_text, f"{session_id_local}_analysis_final", formatted_sys_prompt)
        if not external_response_text or external_response_text.startswith(("ERROR_PROMPT_BLOCKED", "ERROR_CONTENT_BLOCKED")):
            raise ValueError(f"Invalid/blocked response from analysis: {external_response_text or 'No response'}")
        logger.info("✅ Received analysis from remote API.")

        analysis_results_list = json.loads(clean_model_response(external_response_text))
        if not isinstance(analysis_results_list, list): 
            logger.warning("Analysis result was not a list, defaulting to empty list.")
            analysis_results_list = []
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', dir=TEMP_PROCESSING_FOLDER, delete=False) as tmp_json_file:
            json.dump(analysis_results_list, tmp_json_file, ensure_ascii=False, indent=2)
            temp_analysis_results_path = tmp_json_file.name
        
        if temp_analysis_results_path:
            results_upload_result = upload_to_cloudinary_helper(
                temp_analysis_results_path, 
                analysis_results_cloudinary_folder,
                resource_type="raw", 
                public_id_prefix="analysis_results"
            )
            if results_upload_result:
                analysis_results_cloudinary_info = {
                    "url": results_upload_result.get("secure_url"),
                    "public_id": results_upload_result.get("public_id"),
                    "format": results_upload_result.get("format", "json"),
                    "user_facing_filename": "analysis_results.json"
                }
                logger.info("✅ Uploaded analysis results JSON to Cloudinary.")

        contract_doc = {
            "_id": session_id_local, "session_id": session_id_local,
            "original_filename": original_filename,
            "original_cloudinary_info": original_cloudinary_info,
            "analysis_results_cloudinary_info": analysis_results_cloudinary_info,
            "original_format": original_format_to_store,
            "original_contract_plain": original_contract_plain,
            "original_contract_markdown": original_contract_markdown,
            "generated_markdown_from_docx": generated_markdown_from_docx, 
            "detected_contract_language": detected_lang,
            "analysis_timestamp": datetime.datetime.now(datetime.timezone.utc),
            "confirmed_terms": {}, "interactions": [],
            "modified_contract_info": None, "marked_contract_info": None, "pdf_preview_info": {}
        }
        contracts_collection.insert_one(contract_doc)
        logger.info(f"✅ Inserted new contract document into MongoDB for session {session_id_local}.")

        terms_to_insert = [{"session_id": session_id_local, **term} for term in analysis_results_list if isinstance(term, dict) and "term_id" in term]
        if terms_to_insert: 
            terms_collection.insert_many(terms_to_insert)
            logger.info(f"✅ Inserted {len(terms_to_insert)} term documents into MongoDB.")
        
        response_payload = {
            "message": "Contract analyzed successfully.", "analysis_results": analysis_results_list,
            "session_id": session_id_local, "original_contract_plain": original_contract_plain,
            "detected_contract_language": detected_lang,
            "original_cloudinary_url": original_cloudinary_info["url"]
        }
        response = jsonify(response_payload)
        response.set_cookie("session_id", session_id_local, max_age=86400*30, httponly=True, samesite='Lax', secure=request.is_secure)
        logger.info(f"✅ Successfully completed analysis for session {session_id_local}.")
        return response

    except Exception as e:
        logger.error(f"❌ Error in /analyze for session {session_id_local}: {e}", exc_info=True)
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500
    finally:
        if temp_processing_file_path and os.path.exists(temp_processing_file_path):
            try: os.remove(temp_processing_file_path)
            except Exception as e_clean: logger.error(f"Error deleting temp original file: {e_clean}", exc_info=True)
        if temp_analysis_results_path and os.path.exists(temp_analysis_results_path):
            try: os.remove(temp_analysis_results_path)
            except Exception as e_clean: logger.error(f"Error deleting temp analysis JSON file: {e_clean}", exc_info=True)

@app.route("/preview_contract/<session_id>/<contract_type>", methods=["GET"])
def preview_contract(session_id, contract_type):
    logger.info(f"Received request for PDF preview for session {session_id}, type: {contract_type}")
    if contracts_collection is None: 
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service unavailable."}), 503
    if contract_type not in ["modified", "marked"]: 
        logger.warning(f"Invalid contract type '{contract_type}' requested.")
        return jsonify({"error": "Invalid contract type."}), 400

    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc: 
        logger.warning(f"Session not found for ID: {session_id}")
        return jsonify({"error": "Session not found."}), 404

    pdf_previews_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id}/{CLOUDINARY_PDF_PREVIEWS_SUBFOLDER}"
    
    existing_pdf_info = session_doc.get("pdf_preview_info", {}).get(contract_type)
    if existing_pdf_info and existing_pdf_info.get("url"):
        logger.info(f"✅ Returning existing PDF preview URL for {contract_type}: {existing_pdf_info['url']}")
        return jsonify({"pdf_url": existing_pdf_info["url"]})

    source_docx_cloudinary_info = None
    if contract_type == "modified":
        source_docx_cloudinary_info = session_doc.get("modified_contract_info", {}).get("docx_cloudinary_info")
    elif contract_type == "marked":
        source_docx_cloudinary_info = session_doc.get("marked_contract_info", {}).get("docx_cloudinary_info")

    if not source_docx_cloudinary_info or not source_docx_cloudinary_info.get("url"):
        logger.error(f"Source DOCX for {contract_type} contract not found on Cloudinary for session {session_id}.")
        return jsonify({"error": f"Source DOCX for {contract_type} contract not found on Cloudinary."}), 404

    temp_source_docx_path = None
    temp_pdf_preview_path_local = None
    try:
        original_filename_for_suffix = source_docx_cloudinary_info.get("user_facing_filename", f"{contract_type}_contract.docx")
        temp_source_docx_path = download_file_from_url(source_docx_cloudinary_info["url"], original_filename_for_suffix, TEMP_PROCESSING_FOLDER)
        if not temp_source_docx_path:
            return jsonify({"error": "Failed to download source DOCX for preview."}), 500

        logger.info(f"Starting PDF conversion for {temp_source_docx_path}...")
        temp_pdf_preview_path_local = convert_docx_to_pdf_cloudmersive(temp_source_docx_path, PDF_PREVIEW_FOLDER)
        
        if not temp_pdf_preview_path_local or not os.path.exists(temp_pdf_preview_path_local):
             logger.critical(f"PDF file was NOT created at {temp_pdf_preview_path_local}")
             raise Exception("PDF file not created by Cloudmersive or path is incorrect.")
        else:
            logger.info(f"✅ PDF successfully created locally at: {temp_pdf_preview_path_local}")
        
        pdf_public_id_prefix = f"{contract_type}_preview_{os.path.splitext(original_filename_for_suffix)[0]}"
        pdf_upload_result = upload_to_cloudinary_helper(
            temp_pdf_preview_path_local, 
            pdf_previews_cloudinary_folder, 
            resource_type="raw", 
            public_id_prefix=pdf_public_id_prefix
        )
        logger.debug(f"Cloudinary upload result for PDF preview: {pdf_upload_result}")
        
        if not pdf_upload_result or not pdf_upload_result.get("secure_url"):
            logger.error(f"Failed to upload PDF preview to Cloudinary. Full result: {pdf_upload_result}")
            return jsonify({"error": "Failed to upload PDF preview to Cloudinary."}), 500

        pdf_cloudinary_info = {
            "url": pdf_upload_result.get("secure_url"),
            "public_id": pdf_upload_result.get("public_id"),
            "format": pdf_upload_result.get("format", "pdf"),
            "user_facing_filename": f"{pdf_public_id_prefix}.pdf"
        }

        contracts_collection.update_one(
            {"_id": session_id},
            {"$set": {f"pdf_preview_info.{contract_type}": pdf_cloudinary_info}}
        )
        logger.info(f"✅ PDF preview for {contract_type} uploaded to Cloudinary: {pdf_cloudinary_info['url']}")
        
        return jsonify({"pdf_url": pdf_cloudinary_info["url"]})

    except Exception as e:
        logger.error(f"❌ Error during PDF preview for {contract_type} ({session_id}): {e}", exc_info=True)
        return jsonify({"error": f"Could not generate PDF preview: {str(e)}"}), 500
    finally:
        if temp_source_docx_path and os.path.exists(temp_source_docx_path): os.remove(temp_source_docx_path)
        if temp_pdf_preview_path_local and os.path.exists(temp_pdf_preview_path_local): os.remove(temp_pdf_preview_path_local)

@app.route("/download_pdf_preview/<session_id>/<contract_type>", methods=["GET"])
def download_pdf_preview(session_id, contract_type):
    logger.info(f"Request to download PDF for session {session_id}, type {contract_type}")
    if contracts_collection is None:
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service unavailable."}), 503
    if contract_type not in ["modified", "marked"]:
        logger.warning(f"Invalid contract type for download: {contract_type}")
        return jsonify({"error": "Invalid contract type."}), 400

    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc:
        logger.warning(f"Session not found for download: {session_id}")
        return jsonify({"error": "Session not found."}), 404

    pdf_info = session_doc.get("pdf_preview_info", {}).get(contract_type)
    if not pdf_info or not pdf_info.get("url"):
        logger.warning(f"PDF preview URL for {contract_type} not available for session {session_id}.")
        return jsonify({"error": f"PDF preview URL for {contract_type} contract not yet available or generation failed. Please try previewing first."}), 404
    
    cloudinary_pdf_url = pdf_info["url"]
    user_facing_filename = pdf_info.get("user_facing_filename", f"{contract_type}_preview_{session_id[:8]}.pdf")

    try:
        logger.info(f"Attempting to proxy download for PDF: {cloudinary_pdf_url}")
        r = requests.get(cloudinary_pdf_url, stream=True, timeout=120)
        r.raise_for_status() 

        safe_filename = clean_filename(user_facing_filename) 
        encoded_filename = urllib.parse.quote(safe_filename)

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
        logger.error(f"HTTP error fetching PDF from Cloudinary for download: {http_err.response.status_code} - {http_err.response.text}", exc_info=True)
        return jsonify({"error": f"Cloudinary denied access to PDF (Status {http_err.response.status_code}). Check asset permissions."}), http_err.response.status_code if http_err.response.status_code >= 400 else 500
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching PDF from Cloudinary for download: {e}", exc_info=True)
        return jsonify({"error": "Could not fetch PDF from cloud storage."}), 500
    except Exception as e:
        logger.error(f"Unexpected error during PDF download proxy: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred during download."}), 500


@app.route("/generate_modified_contract", methods=["POST"])
def generate_modified_contract():
    if contracts_collection is None: 
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service unavailable."}), 503
    session_id = request.cookies.get("session_id") or (request.is_json and request.get_json().get("session_id"))
    if not session_id: 
        logger.warning("Request to generate modified contract with no session ID.")
        return jsonify({"error": "No session"}), 400
    
    logger.info(f"Generating modified contract for session {session_id}")
    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc: 
        logger.warning(f"Session not found for ID: {session_id}")
        return jsonify({"error": "Session not found"}), 404

    original_filename_from_db = session_doc.get("original_filename", "contract.docx")
    contract_lang = session_doc.get("detected_contract_language", "ar")
    confirmed_terms = session_doc.get("confirmed_terms", {})
    
    markdown_source = session_doc.get("generated_markdown_from_docx") or session_doc.get("original_contract_markdown")
    if not markdown_source:
        logger.error(f"Contract source text (markdown) not found for generation in session {session_id}.")
        return jsonify({"error": "Contract source text (markdown) not found for generation."}), 500

    modified_contracts_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id}/{CLOUDINARY_MODIFIED_CONTRACTS_SUBFOLDER}"
    user_facing_base, _ = os.path.splitext(original_filename_from_db)
    user_facing_clean_base = clean_filename(user_facing_base) or "contract"
    
    docx_public_id_prefix = f"modified_{user_facing_clean_base}"
    txt_public_id_prefix = f"modified_{user_facing_clean_base}"
    
    temp_modified_docx_path = None
    temp_modified_txt_path = None
    
    try:
        temp_modified_docx_fd, temp_modified_docx_path = tempfile.mkstemp(suffix=".docx", prefix="mod_docx_", dir=TEMP_PROCESSING_FOLDER)
        os.close(temp_modified_docx_fd)
        temp_modified_txt_fd, temp_modified_txt_path = tempfile.mkstemp(suffix=".txt", prefix="mod_txt_", dir=TEMP_PROCESSING_FOLDER)
        os.close(temp_modified_txt_fd)

        formatted_regen_prompt = CONTRACT_REGENERATION_PROMPT.format(output_language=contract_lang)
        regeneration_request_payload = {"original_markdown": markdown_source, "confirmed_modifications": confirmed_terms}
        regeneration_request_text = json.dumps(regeneration_request_payload, ensure_ascii=False, indent=2)
        
        logger.info(f"Requesting contract regeneration from LLM for session {session_id}")
        chat = get_chat_session(f"{session_id}_regeneration", system_instruction=formatted_regen_prompt, force_new=True)
        response = chat.send_message(regeneration_request_text)
        
        if response.text is None or response.text.startswith(("ERROR_PROMPT_BLOCKED", "ERROR_CONTENT_BLOCKED")):
            raise ValueError(f"Regeneration blocked: {response.text or 'Empty response'}")
        
        final_text_content_for_output = clean_model_response(response.text).strip()
        if not final_text_content_for_output: 
            raise ValueError("LLM failed to generate content for contract regeneration.")
        logger.info(f"✅ Received regenerated contract text from LLM for session {session_id}")

        create_docx_from_llm_markdown(final_text_content_for_output, temp_modified_docx_path, contract_lang) 

        with open(temp_modified_txt_path, "w", encoding="utf-8") as f: f.write(final_text_content_for_output)

        docx_upload_res = upload_to_cloudinary_helper(temp_modified_docx_path, modified_contracts_cloudinary_folder, public_id_prefix=docx_public_id_prefix)
        final_docx_cloudinary_info = {"url": docx_upload_res.get("secure_url"), "public_id": docx_upload_res.get("public_id"), "format": "docx", "user_facing_filename": f"{docx_public_id_prefix}.docx"} if docx_upload_res else None
        
        txt_upload_res = upload_to_cloudinary_helper(temp_modified_txt_path, modified_contracts_cloudinary_folder, resource_type="raw", public_id_prefix=txt_public_id_prefix)
        final_txt_cloudinary_info = {"url": txt_upload_res.get("secure_url"), "public_id": txt_upload_res.get("public_id"), "format": "txt", "user_facing_filename": f"{txt_public_id_prefix}.txt"} if txt_upload_res else None

        contracts_collection.update_one({"_id": session_id}, {"$set": {"modified_contract_info": {"docx_cloudinary_info": final_docx_cloudinary_info, "txt_cloudinary_info": final_txt_cloudinary_info, "generation_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}}})
        logger.info(f"✅ Successfully generated and uploaded modified contract for session {session_id}")
        
        return jsonify({"success": True, "message": "Modified contract generated.", "modified_docx_cloudinary_url": final_docx_cloudinary_info.get("url") if final_docx_cloudinary_info else None, "modified_txt_cloudinary_url": final_txt_cloudinary_info.get("url") if final_txt_cloudinary_info else None})
    except Exception as e: 
        logger.error(f"❌ Error in /generate_modified_contract for session {session_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed: {str(e)}"}), 500
    finally:
        if temp_modified_docx_path and os.path.exists(temp_modified_docx_path): os.remove(temp_modified_docx_path)
        if temp_modified_txt_path and os.path.exists(temp_modified_txt_path): os.remove(temp_modified_txt_path)


@app.route("/generate_marked_contract", methods=["POST"])
def generate_marked_contract():
    if contracts_collection is None or terms_collection is None: 
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service unavailable."}), 503
    session_id = request.cookies.get("session_id") or (request.is_json and request.get_json().get("session_id"))
    if not session_id: 
        logger.warning("Request to generate marked contract with no session ID.")
        return jsonify({"error": "No session"}), 400
    
    logger.info(f"Generating marked contract for session {session_id}")
    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc: 
        logger.warning(f"Session not found for ID: {session_id}")
        return jsonify({"error": "Session not found"}), 404

    original_filename_from_db = session_doc.get("original_filename", "contract.docx")
    contract_lang = session_doc.get("detected_contract_language", "ar")
    
    markdown_source = session_doc.get("generated_markdown_from_docx") or session_doc.get("original_contract_markdown")
    if not markdown_source:
        logger.error(f"Contract source text (markdown) not found for generation in session {session_id}.")
        return jsonify({"error": "Contract source text (markdown) not found for generation."}), 500

    db_terms_list = list(terms_collection.find({"session_id": session_id}))
    
    marked_contracts_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id}/{CLOUDINARY_MARKED_CONTRACTS_SUBFOLDER}"
    user_facing_base, _ = os.path.splitext(original_filename_from_db)
    user_facing_clean_base = clean_filename(user_facing_base) or "contract"
    marked_docx_public_id_prefix = f"marked_{user_facing_clean_base}"

    temp_marked_docx_path = None

    try:
        temp_marked_docx_fd, temp_marked_docx_path = tempfile.mkstemp(suffix=".docx", prefix="marked_", dir=TEMP_PROCESSING_FOLDER)
        os.close(temp_marked_docx_fd)

        def smart_sort_key(term):
            term_id = term.get("term_id", "")
            if term_id.startswith("para_"):
                parts = re.findall(r'[A-Za-z]+|\d+', term_id)
                return tuple(int(p) if p.isdigit() else p for p in parts)
            elif term_id.startswith("clause_"):
                match = re.match(r"clause_(\d+)", term_id)
                return ('clause', int(match.group(1))) if match else ('clause', float('inf'))
            return ('z', float('inf'))
            
        sorted_db_terms = sorted(db_terms_list, key=smart_sort_key)
        logger.info(f"Sorted {len(sorted_db_terms)} terms for marking.")

        create_docx_from_llm_markdown(
            markdown_source, 
            temp_marked_docx_path, 
            contract_lang, 
            terms_for_marking=sorted_db_terms 
        )

        marked_upload_res = upload_to_cloudinary_helper(temp_marked_docx_path, marked_contracts_cloudinary_folder, public_id_prefix=marked_docx_public_id_prefix)
        final_marked_docx_cloudinary_info = {
            "url": marked_upload_res.get("secure_url"), 
            "public_id": marked_upload_res.get("public_id"), 
            "format": "docx", 
            "user_facing_filename": f"{marked_docx_public_id_prefix}.docx"
        } if marked_upload_res else None
        
        contracts_collection.update_one(
            {"_id": session_id}, 
            {"$set": {
                "marked_contract_info": {
                    "docx_cloudinary_info": final_marked_docx_cloudinary_info, 
                    "generation_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                 }
            }}
        )
        logger.info(f"✅ Successfully generated and uploaded marked contract for session {session_id}")
        return jsonify({
            "success": True, 
            "message": "Marked contract generated.", 
            "marked_docx_cloudinary_url": final_marked_docx_cloudinary_info.get("url") if final_marked_docx_cloudinary_info else None
        })
    except Exception as e: 
        logger.error(f"❌ Error in /generate_marked_contract for session {session_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed: {str(e)}"}), 500
    finally:
        if temp_marked_docx_path and os.path.exists(temp_marked_docx_path): os.remove(temp_marked_docx_path)


@app.route("/interact", methods=["POST"])
def interact():
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service is currently unavailable."}), 503
    if not request.is_json:
        logger.warning("Interaction request received with non-JSON content type.")
        return jsonify({"error": "Unsupported Media Type: Expected application/json"}), 415
        
    interaction_data = request.get_json()
    if not interaction_data or "question" not in interaction_data:
        logger.warning("Interaction request is missing 'question' field.")
        return jsonify({"error": "الرجاء إرسال سؤال في صيغة JSON"}), 400

    user_question = interaction_data.get("question")
    term_id_context = interaction_data.get("term_id") 

    session_id = request.cookies.get("session_id") or request.args.get("session_id") or interaction_data.get("session_id")
    
    if not session_id: 
        logger.warning("Interaction request with no session ID.")
        return jsonify({"error": "لم يتم العثور على جلسة. يرجى تحميل العقد أولاً."}), 400
    
    logger.info(f"Interaction request for session {session_id}, term '{term_id_context or 'general'}'")
    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc:
         logger.warning(f"Session not found for ID: {session_id}")
         return jsonify({"error": "الجلسة غير موجودة أو منتهية الصلاحية"}), 404
    
    contract_lang = session_doc.get("detected_contract_language", "ar")
    try:
        formatted_interaction_prompt = INTERACTION_PROMPT.format(output_language=contract_lang)
    except KeyError as ke:
        logger.error(f"KeyError formatting INTERACTION_PROMPT: {ke}. Using default language 'ar'.")
        formatted_interaction_prompt = INTERACTION_PROMPT.format(output_language='ar')

    full_contract_context_for_llm = session_doc.get("original_contract_plain", session_doc.get("original_contract_markdown", ""))
    term_text_context = interaction_data.get("term_text") 
    initial_analysis_summary_str = "" 
    if term_id_context:
        term_doc_from_db = terms_collection.find_one({"session_id": session_id, "term_id": term_id_context})
        if term_doc_from_db:
            initial_analysis_summary_str = (
                f"ملخص التحليل الأولي للبند '{term_id_context}' (لغة التحليل الأصلية: {contract_lang}):\n"
                f"  - هل هو متوافق شرعاً؟ {'نعم' if term_doc_from_db.get('is_valid_sharia') else 'لا'}\n"
                f"  - المشكلة الشرعية (إن وجدت): {term_doc_from_db.get('sharia_issue', 'لا يوجد')}\n"
                f"  - الاقتراح الأولي (إن وجد): {term_doc_from_db.get('modified_term', 'لا يوجد')}\n"
                f"  - المرجع (إن وجد): {term_doc_from_db.get('reference_number', 'لا يوجد')}\n"
            )

    llm_payload_parts = [f"سؤال المستخدم (الرجاء الرد بلغة {contract_lang}): {user_question}\n"]
    if term_id_context and term_text_context:
        llm_payload_parts.append(f"معلومات البند المحدد (معرف: {term_id_context}):")
        llm_payload_parts.append(f"نص البند الأصلي: {term_text_context}")
        if initial_analysis_summary_str:
            llm_payload_parts.append(initial_analysis_summary_str)
        llm_payload_parts.append("\n")
    
    llm_payload_parts.append(f"النص الكامل للعقد الأصلي (للسياق العام، لغة العقد الأصلية هي على الأرجح {contract_lang}):\n---\n{full_contract_context_for_llm}\n---")
    interaction_payload_for_llm = "\n".join(llm_payload_parts)
    
    try:
        chat = get_chat_session(f"{session_id}_interaction", system_instruction=formatted_interaction_prompt, force_new=True)
        response = chat.send_message(interaction_payload_for_llm)
        external_response_text = response.text

        if external_response_text is None or external_response_text.startswith("ERROR_PROMPT_BLOCKED") or external_response_text.startswith("ERROR_CONTENT_BLOCKED"):
            error_msg_detail = external_response_text if external_response_text else "Blocked or empty response from API."
            logger.error(f"Interaction blocked by API for session {session_id}: {error_msg_detail}")
            return jsonify({"error": f"Blocked by API: {error_msg_detail}"}), 400

        interaction_to_save = {
            "user_question": user_question,
            "term_id": term_id_context, 
            "term_text": term_text_context, 
            "response": external_response_text,
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
        }
        contracts_collection.update_one(
            {"_id": session_id},
            {"$push": {"interactions": interaction_to_save}}
        )
        logger.info(f"✅ Interaction (term: {term_id_context or 'general'}) added to session {session_id} in MongoDB.")
        
        resp = Response(external_response_text, status=200, mimetype='text/plain; charset=utf-8')
        resp.set_cookie("session_id", session_id, max_age=86400*30, httponly=True, samesite='Lax', secure=request.is_secure)
        return resp
    except Exception as e:
        logger.error(f"❌ Error during interaction for session {session_id}: {e}", exc_info=True)
        return jsonify({"error": f"فشل في معالجة التفاعل: {str(e)}"}), 500


@app.route("/review_modification", methods=["POST"])
def review_modification():
    if contracts_collection is None: 
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service is currently unavailable."}), 503
    if not request.is_json: 
        logger.warning("Review modification request with non-JSON content type.")
        return jsonify({"error": "Unsupported Media Type"}), 415
    
    data = request.get_json()
    session_id = request.cookies.get("session_id") or data.get("session_id")
    term_id = data.get("term_id")
    user_modified_text = data.get("user_modified_text")
    original_term_text_from_req = data.get("original_term_text")
    
    if not all([session_id, term_id, user_modified_text is not None, original_term_text_from_req is not None]): 
        logger.warning(f"Missing data in review_modification request for session {session_id}.")
        return jsonify({"error": "بيانات ناقصة"}), 400
    
    logger.info(f"Reviewing modification for session {session_id}, term {term_id}.")
    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc: 
        logger.warning(f"Session not found for ID: {session_id}")
        return jsonify({"error": "الجلسة غير موجودة"}), 404
    
    contract_lang = session_doc.get("detected_contract_language", "ar")
    try: 
        formatted_review_prompt = REVIEW_MODIFICATION_PROMPT.format(output_language=contract_lang)
    except KeyError as ke: 
        logger.error(f"KeyError formatting REVIEW_MODIFICATION_PROMPT: {ke}")
        return jsonify({"error": f"Prompt format error: {ke}"}), 500

    review_payload_for_llm = json.dumps({
        "original_term_text": original_term_text_from_req, 
        "user_modified_text": user_modified_text
    }, ensure_ascii=False, indent=2)
    
    try:
        chat = get_chat_session(f"{session_id}_review_{term_id}", system_instruction=formatted_review_prompt, force_new=True)
        response = chat.send_message(review_payload_for_llm)
        
        if response.text is None or response.text.startswith("ERROR_PROMPT_BLOCKED") or response.text.startswith("ERROR_CONTENT_BLOCKED"): 
            error_msg_detail = response.text if response.text else "Blocked or empty response from review API."
            logger.error(f"Review blocked by API for session {session_id}, term {term_id}: {error_msg_detail}")
            return jsonify({"error": f"Blocked: {error_msg_detail}"}), 400

        cleaned_llm_response = clean_model_response(response.text)
        review_result = json.loads(cleaned_llm_response)
        logger.info(f"✅ Successfully reviewed modification for session {session_id}, term {term_id}.")
        return jsonify(review_result), 200
    except json.JSONDecodeError as je:
        logger.error(f"JSONDecodeError in /review_modification for session {session_id}, term {term_id}: {je}", exc_info=True)
        return jsonify({"error": f"فشل تحليل استجابة المراجعة: {str(je)}"}), 500
    except Exception as e: 
        logger.error(f"Error in /review_modification for session {session_id}, term {term_id}: {e}", exc_info=True)
        return jsonify({"error": f"خطأ في مراجعة التعديل: {str(e)}"}), 500

@app.route("/feedback/expert", methods=["POST"])
def submit_expert_feedback():
    if expert_feedback_collection is None or terms_collection is None:
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service is currently unavailable."}), 503
        
    if not request.is_json:
        logger.warning("Expert feedback request with non-JSON content type.")
        return jsonify({"error": "Unsupported Media Type: Expected application/json"}), 415
    
    data = request.get_json()
    session_id = request.cookies.get("session_id") or data.get("session_id")
    term_id = data.get("term_id")
    feedback_data = data.get("feedback_data")
    expert_user_id = "default_expert_id" 
    expert_username = "Default Expert"   

    if not all([session_id, term_id, feedback_data]):
        logger.warning(f"Missing data in expert feedback request for session {session_id}.")
        return jsonify({"error": "البيانات المطلوبة غير مكتملة (session_id, term_id, feedback_data)"}), 400
    
    logger.info(f"Submitting expert feedback for session {session_id}, term {term_id}.")
    original_term_doc = terms_collection.find_one({"session_id": session_id, "term_id": term_id})
    snapshot_ai_data = {}
    original_term_text_for_snapshot = ""
    if original_term_doc:
        original_term_text_for_snapshot = original_term_doc.get("term_text", "")
        snapshot_ai_data = {
            "original_ai_is_valid_sharia": original_term_doc.get("is_valid_sharia"),
            "original_ai_sharia_issue": original_term_doc.get("sharia_issue"),
            "original_ai_modified_term": original_term_doc.get("modified_term"),
            "original_ai_reference_number": original_term_doc.get("reference_number")
        }

    feedback_doc = {
        "session_id": session_id,
        "term_id": term_id,
        "original_term_text_snapshot": original_term_text_for_snapshot,
        "expert_user_id": expert_user_id, 
        "expert_username": expert_username, 
        "feedback_timestamp": datetime.datetime.now(datetime.timezone.utc),
        "ai_initial_analysis_assessment": { 
            "is_correct_compliance": feedback_data.get("aiAnalysisApproved"),
        },
        "expert_verdict_is_valid_sharia": feedback_data.get("expertIsValidSharia"),
        "expert_comment_on_term": feedback_data.get("expertComment"),
        "expert_corrected_sharia_issue": feedback_data.get("expertCorrectedShariaIssue"),
        "expert_corrected_reference": feedback_data.get("expertCorrectedReference"),
        "expert_final_suggestion_for_term": feedback_data.get("expertCorrectedSuggestion"),
        **snapshot_ai_data 
    }

    try:
        result = expert_feedback_collection.insert_one(feedback_doc)
        terms_collection.update_one(
            {"session_id": session_id, "term_id": term_id},
            {"$set": {
                "has_expert_feedback": True, 
                "last_expert_feedback_id": result.inserted_id, 
                "expert_override_is_valid_sharia": feedback_data.get("expertIsValidSharia") 
            }}
        )
        logger.info(f"✅ Successfully saved expert feedback for session {session_id}, term {term_id}. Feedback ID: {result.inserted_id}")
        return jsonify({"success": True, "message": "تم حفظ ملاحظات الخبير بنجاح.", "feedback_id": str(result.inserted_id)}), 201
    except Exception as e:
        logger.error(f"❌ Error saving expert feedback for session {session_id}: {e}", exc_info=True)
        return jsonify({"error": f"فشل حفظ ملاحظات الخبير: {str(e)}"}), 500


@app.route("/confirm_modification", methods=["POST"])
def confirm_modification():
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service is currently unavailable."}), 503

    data = request.get_json();
    if not data: 
        logger.warning("Confirm modification request with no JSON data.")
        return jsonify({"error": "لم يتم إرسال بيانات في الطلب"}), 400
        
    term_id_from_req = data.get("term_id"); modified_text_from_req = data.get("modified_text")
    session_id_from_req = request.cookies.get("session_id") or data.get("session_id")
    
    if term_id_from_req is None or modified_text_from_req is None or not session_id_from_req: 
        logger.warning(f"Missing data in confirm_modification request for session {session_id_from_req}.")
        return jsonify({"error": "البيانات المطلوبة غير مكتملة"}), 400
    
    logger.info(f"Confirming modification for session {session_id_from_req}, term {term_id_from_req}.")
    session_doc = contracts_collection.find_one({"_id": session_id_from_req})
    if not session_doc: 
        logger.warning(f"Session not found for ID: {session_id_from_req}")
        return jsonify({"error": "الجلسة غير موجودة"}), 404
    
    updated_confirmed_terms = session_doc.get("confirmed_terms", {})
    updated_confirmed_terms[str(term_id_from_req)] = modified_text_from_req
    
    try:
        contracts_collection.update_one(
            {"_id": session_id_from_req}, 
            {"$set": {"confirmed_terms": updated_confirmed_terms}}
        )
        terms_collection.update_one(
            {"session_id": session_id_from_req, "term_id": term_id_from_req},
            {"$set": {
                "is_confirmed_by_user": True, 
                "confirmed_modified_text": modified_text_from_req,
            }}
        )
        logger.info(f"✅ Successfully confirmed modification for session {session_id_from_req}, term {term_id_from_req}.")
        return jsonify({"success": True, "message": f"تم تأكيد التعديل للبند: {term_id_from_req}"})
    except Exception as e: 
        logger.error(f"❌ Error during confirm_modification for session {session_id_from_req}, term {term_id_from_req}: {e}", exc_info=True)
        return jsonify({"error": f"خطأ أثناء تأكيد التعديل: {str(e)}"}), 500


@app.route("/session/<session_id>", methods=["GET"])
def get_session_details(session_id):
    logger.info(f"Request for session details for ID: {session_id}")
    if contracts_collection is None : 
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service is currently unavailable."}), 503
        
    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc: 
        logger.warning(f"Session not found for ID: {session_id}")
        return jsonify({"error": "الجلسة غير موجودة"}), 404
    
    # Sanitize document for JSON response
    if '_id' in session_doc and isinstance(session_doc['_id'], ObjectId): 
        session_doc['_id'] = str(session_doc['_id'])
    for key, value in session_doc.items():
        if isinstance(value, datetime.datetime): 
            session_doc[key] = value.isoformat()
        if isinstance(value, dict): 
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, datetime.datetime):
                    value[sub_key] = sub_value.isoformat()
                if isinstance(sub_value, ObjectId):
                    value[sub_key] = str(sub_value)
                if isinstance(sub_value, dict): 
                    for ssub_key, ssub_value in sub_value.items():
                        if isinstance(ssub_value, ObjectId):
                            sub_value[ssub_key] = str(ssub_value)
                            
    logger.info(f"✅ Successfully retrieved session details for ID: {session_id}")
    return jsonify(session_doc), 200

@app.route("/terms/<session_id>", methods=["GET"])
def get_session_terms(session_id):
    logger.info(f"Request for session terms for ID: {session_id}")
    if terms_collection is None : 
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service is currently unavailable."}), 503
        
    terms_cursor = terms_collection.find({"session_id": session_id})
    terms_list = []
    for term in terms_cursor:
        if '_id' in term and isinstance(term['_id'], ObjectId):
            term['_id'] = str(term['_id'])
        if 'last_expert_feedback_id' in term and term['last_expert_feedback_id'] and isinstance(term['last_expert_feedback_id'], ObjectId):
            term['last_expert_feedback_id'] = str(term['last_expert_feedback_id'])
        terms_list.append(term)

    if not terms_list: 
        if contracts_collection.find_one({"_id": session_id}) is None:
            logger.warning(f"Session not found for ID: {session_id} when fetching terms.")
            return jsonify({"error": "الجلسة غير موجودة"}), 404
    
    logger.info(f"✅ Successfully retrieved {len(terms_list)} terms for session ID: {session_id}")
    return jsonify(terms_list), 200

@app.route("/api/stats/user", methods=["GET"])
def get_user_stats():
    logger.info("Request for user stats.")
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service is currently unavailable."}), 503

    try:
        total_sessions = contracts_collection.count_documents({})
        total_terms_analyzed = terms_collection.count_documents({})
        compliant_terms = terms_collection.count_documents({"is_valid_sharia": True})
        compliance_rate = (compliant_terms / total_terms_analyzed * 100) if total_terms_analyzed > 0 else 0
        average_processing_time = 15.5 # Placeholder

        stats = {
            "totalSessions": total_sessions,
            "totalTerms": total_terms_analyzed,
            "complianceRate": round(compliance_rate, 2),
            "averageProcessingTime": average_processing_time
        }
        logger.info(f"✅ Successfully calculated user stats: {stats}")
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"❌ Error in /api/stats/user: {e}", exc_info=True)
        return jsonify({"error": f"Failed to retrieve user stats: {str(e)}"}), 500

@app.route("/api/history", methods=["GET"])
def get_history():
    logger.info("Request for session history.")
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable.")
        return jsonify({"error": "Database service is currently unavailable."}), 503

    try:
        contracts_cursor = contracts_collection.find().sort("analysis_timestamp", -1)
        contracts = list(contracts_cursor)
        
        if not contracts:
            logger.info("No history found.")
            return jsonify([]), 200

        session_ids = [c["session_id"] for c in contracts]
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
            session_id = contract_doc["session_id"]
            session_terms = terms_by_session.get(session_id, [])
            total_terms = len(session_terms)
            valid_terms = sum(1 for term in session_terms if term.get("is_valid_sharia") is True)
            compliance_percentage = (valid_terms / total_terms * 100) if total_terms > 0 else 100

            if '_id' in contract_doc and isinstance(contract_doc['_id'], ObjectId):
                contract_doc['_id'] = str(contract_doc['_id'])
            if 'analysis_timestamp' in contract_doc and isinstance(contract_doc['analysis_timestamp'], datetime.datetime):
                contract_doc['analysis_timestamp'] = contract_doc['analysis_timestamp'].isoformat()
            
            enriched_session = {
                **contract_doc,
                "analysis_results": session_terms,
                "compliance_percentage": round(compliance_percentage, 2),
                "interactions_count": len(contract_doc.get("interactions", [])), 
                "modifications_made": len(contract_doc.get("confirmed_terms", {})),
                "generated_contracts": bool(contract_doc.get("modified_contract_info") or contract_doc.get("marked_contract_info")),
            }
            history_results.append(enriched_session)

        logger.info(f"✅ Successfully retrieved {len(history_results)} history entries.")
        return jsonify(history_results)

    except Exception as e:
        logger.error(f"❌ Error in /api/history: {e}", exc_info=True)
        return jsonify({"error": f"Failed to retrieve session history: {str(e)}"}), 500


if __name__ == "__main__":
    # This block is for local development, not for Gunicorn/Railway
    logger.info("Starting Flask development server...")
    # For production, Gunicorn will be used as defined in the Procfile
    # The PORT environment variable is automatically set by Railway
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
