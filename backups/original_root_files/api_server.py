# backend/api_server.py
import os
import uuid
import json
import datetime
import logging
from flask import Flask, request, jsonify, send_from_directory, Response, redirect
from werkzeug.utils import secure_filename
from pymongo import MongoClient, ReturnDocument
from bson import ObjectId
from flask_cors import CORS
from langdetect import detect, LangDetectException, DetectorFactory
import urllib.parse
import traceback
import tempfile
import re

# Cloudinary and requests imports
import cloudinary
import cloudinary.uploader
import cloudinary.api
import requests

from config import (
    MONGO_URI, GOOGLE_API_KEY,
    SYS_PROMPT, INTERACTION_PROMPT,
    REVIEW_MODIFICATION_PROMPT, CONTRACT_REGENERATION_PROMPT,
    LIBREOFFICE_PATH,
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET,
    CLOUDINARY_BASE_FOLDER,
    CLOUDINARY_ORIGINAL_UPLOADS_SUBFOLDER,
    CLOUDINARY_ANALYSIS_RESULTS_SUBFOLDER,
    CLOUDINARY_MODIFIED_CONTRACTS_SUBFOLDER,
    CLOUDINARY_MARKED_CONTRACTS_SUBFOLDER,
    CLOUDINARY_PDF_PREVIEWS_SUBFOLDER
)
from remote_api import send_text_to_remote_api, get_chat_session, extract_text_from_file
from doc_processing import (
    build_structured_text_for_analysis,
    create_docx_from_llm_markdown,
    convert_docx_to_pdf,
)
# Import from new utils file
from utils import ensure_dir, clean_filename, clean_model_response, download_file_from_url, upload_to_cloudinary_helper

from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT, WD_BREAK
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('shariaa_analyzer.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

DetectorFactory.seed = 0

app = Flask(__name__)
CORS(app, origins="*", supports_credentials=True)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def translate_arabic_to_english(arabic_text):
    """
    Translates Arabic contract names to English using simple transliteration.
    Falls back to generic name if translation fails.
    """
    try:
        # Simple transliteration mapping for common Arabic words in contracts
        transliteration_map = {
            'عقد': 'contract',
            'بيع': 'sale',
            'شراء': 'purchase',
            'إيجار': 'rental',
            'تأجير': 'lease',
            'عمل': 'work',
            'خدمات': 'services',
            'توريد': 'supply',
            'مقاولة': 'contracting',
            'شركة': 'company',
            'مؤسسة': 'institution',
            'الأول': 'first',
            'الثاني': 'second',
            'نهائي': 'final',
            'مبدئي': 'preliminary'
        }

        # Clean and split the Arabic text
        words = arabic_text.strip().split()
        translated_words = []

        for word in words:
            # Remove common Arabic articles and prepositions
            clean_word = word.replace('ال', '').replace('و', '').replace('في', '').replace('من', '')

            # Look for direct translation
            translated = transliteration_map.get(clean_word.lower())
            if translated:
                translated_words.append(translated)
            else:
                # Fallback: use unidecode for transliteration
                from unidecode import unidecode
                transliterated = unidecode(clean_word)
                if transliterated and transliterated.strip():
                    translated_words.append(transliterated.lower())

        if translated_words:
            result = '_'.join(translated_words)[:50]  # Limit length
            logger.info(f"Translated Arabic contract name '{arabic_text}' to '{result}'")
            return result
        else:
            fallback = f"contract_{uuid.uuid4().hex[:8]}"
            logger.warning(f"Could not translate Arabic name '{arabic_text}', using fallback: {fallback}")
            return fallback

    except Exception as e:
        logger.error(f"Error translating Arabic contract name '{arabic_text}': {e}")
        return f"contract_{uuid.uuid4().hex[:8]}"

def generate_safe_public_id(base_name, prefix="", max_length=50):
    """
    Generates a safe, short public_id for Cloudinary uploads.
    Handles Arabic names by translating them to English.
    """
    try:
        if not base_name:
            safe_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
            logger.debug(f"Generated safe public_id for empty base_name: {safe_id}")
            return safe_id

        # Detect if the name contains Arabic characters
        has_arabic = bool(re.search(r'[\u0600-\u06FF]', base_name))

        if has_arabic:
            logger.info(f"Detected Arabic in contract name: {base_name}")
            english_name = translate_arabic_to_english(base_name)
            clean_name = clean_filename(english_name)
        else:
            clean_name = clean_filename(base_name)

        # Ensure the name is not too long
        if len(clean_name) > max_length:
            clean_name = clean_name[:max_length]

        # Generate final public_id
        if prefix:
            safe_id = f"{prefix}_{clean_name}_{uuid.uuid4().hex[:6]}"
        else:
            safe_id = f"{clean_name}_{uuid.uuid4().hex[:6]}"

        # Final safety check - remove any remaining problematic characters
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', safe_id)

        logger.debug(f"Generated safe public_id: {safe_id} from base_name: {base_name}")
        return safe_id

    except Exception as e:
        logger.error(f"Error generating safe public_id for '{base_name}': {e}")
        fallback_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
        return fallback_id

try:
    cloudinary.config(
      cloud_name=CLOUDINARY_CLOUD_NAME,
      api_key=CLOUDINARY_API_KEY,
      api_secret=CLOUDINARY_API_SECRET,
      secure=True
    )
    logger.info("Cloudinary configured successfully")
except Exception as e:
    logger.error(f"Cloudinary configuration failed: {e}")
    traceback.print_exc()

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
    logger.info(f"Successfully connected to MongoDB: {DB_NAME}")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    traceback.print_exc()

@app.route("/analyze", methods=["POST"])
def analyze_file():
    session_id_local = str(uuid.uuid4())
    logger.info(f"Starting file analysis for session: {session_id_local}")

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

    original_upload_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id_local}/{CLOUDINARY_ORIGINAL_UPLOADS_SUBFOLDER}"
    analysis_results_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id_local}/{CLOUDINARY_ANALYSIS_RESULTS_SUBFOLDER}"

    original_cloudinary_info = None
    analysis_results_cloudinary_info = None
    temp_processing_file_path = None
    temp_analysis_results_path = None

    try:
        file_base, _ = os.path.splitext(original_filename)

        # Generate safe public_id for original file upload
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

        temp_processing_file_path = download_file_from_url(original_cloudinary_info["url"], original_filename, TEMP_PROCESSING_FOLDER)
        if not temp_processing_file_path:
            logger.error("Failed to download original file from Cloudinary for processing")
            raise Exception("Failed to download original file from Cloudinary for processing.")

        effective_ext = f".{original_cloudinary_info['format']}" if original_cloudinary_info['format'] else os.path.splitext(original_filename)[1].lower()

        detected_lang = 'ar'
        original_contract_plain = ""
        original_contract_markdown = None # For PDF/TXT originals
        generated_markdown_from_docx = None # For DOCX originals
        analysis_input_text = None
        original_format_to_store = effective_ext.replace(".", "") if effective_ext else "unknown"

        logger.info(f"Processing file with extension: {effective_ext}")

        if effective_ext == ".docx":
            logger.info("Processing DOCX file")
            doc = DocxDocument(temp_processing_file_path)
            # This now generates structured markdown with formatting preserved
            analysis_input_text, original_contract_plain = build_structured_text_for_analysis(doc)
            generated_markdown_from_docx = analysis_input_text # Store the generated markdown
            original_format_to_store = "docx"
            logger.info(f"Extracted {len(original_contract_plain)} characters from DOCX")
        elif effective_ext in [".pdf", ".txt"]:
            logger.info(f"Processing {effective_ext.upper()} file")
            extracted_markdown_from_llm = extract_text_from_file(temp_processing_file_path)
            if extracted_markdown_from_llm is None:
                logger.error(f"Text extraction failed for {effective_ext}")
                raise ValueError(f"Text extraction failed for {effective_ext}.")
            original_contract_markdown = extracted_markdown_from_llm
            analysis_input_text = original_contract_markdown
            if extracted_markdown_from_llm:
                original_contract_plain = re.sub(r'^#+\s*|\*\*|\*|__|`|\[\[.*?\]\]', '', extracted_markdown_from_llm, flags=re.MULTILINE).strip()
            original_format_to_store = effective_ext.replace(".", "")
            logger.info(f"Extracted {len(original_contract_plain)} characters from {effective_ext.upper()}")
        else:
            logger.error(f"Unsupported file type: {effective_ext}")
            return jsonify({"error": f"Unsupported file type after upload: {effective_ext}"}), 400

        if original_contract_plain and len(original_contract_plain) > 20:
            try:
                detected_lang = 'ar' if detect(original_contract_plain[:1000]) == 'ar' else 'en'
                logger.info(f"Detected contract language: {detected_lang}")
            except LangDetectException:
                logger.warning("Language detection failed, defaulting to Arabic")

        formatted_sys_prompt = SYS_PROMPT.format(output_language=detected_lang)
        if not analysis_input_text or not analysis_input_text.strip():
            logger.error("Analysis input text is empty")
            raise ValueError("Analysis input text is empty.")

        logger.info("Sending contract to LLM for analysis")
        external_response_text = send_text_to_remote_api(analysis_input_text, f"{session_id_local}_analysis_final", formatted_sys_prompt)
        if not external_response_text or external_response_text.startswith(("ERROR_PROMPT_BLOCKED", "ERROR_CONTENT_BLOCKED")):
            logger.error(f"Invalid/blocked response from analysis: {external_response_text}")
            raise ValueError(f"Invalid/blocked response from analysis: {external_response_text or 'No response'}")

        logger.info("Parsing LLM analysis results")
        analysis_results_list = json.loads(clean_model_response(external_response_text))
        if not isinstance(analysis_results_list, list):
            analysis_results_list = []

        logger.info(f"Analysis completed with {len(analysis_results_list)} terms identified")

        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', dir=TEMP_PROCESSING_FOLDER, delete=False) as tmp_json_file:
            json.dump(analysis_results_list, tmp_json_file, ensure_ascii=False, indent=2)
            temp_analysis_results_path = tmp_json_file.name

        if temp_analysis_results_path:
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
        logger.info(f"Contract document saved to database for session: {session_id_local}")

        terms_to_insert = [{"session_id": session_id_local, **term} for term in analysis_results_list if isinstance(term, dict) and "term_id" in term]
        if terms_to_insert:
            terms_collection.insert_many(terms_to_insert)
            logger.info(f"Inserted {len(terms_to_insert)} terms to database")

        response_payload = {
            "message": "Contract analyzed successfully.", "analysis_results": analysis_results_list,
            "session_id": session_id_local, "original_contract_plain": original_contract_plain,
            "detected_contract_language": detected_lang,
            "original_cloudinary_url": original_cloudinary_info["url"]
        }
        response = jsonify(response_payload)
        response.set_cookie("session_id", session_id_local, max_age=86400*30, httponly=True, samesite='Lax', secure=request.is_secure)

        logger.info(f"Analysis completed successfully for session: {session_id_local}")
        return response

    except Exception as e:
        logger.error(f"Analysis failed for session {session_id_local}: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500
    finally:
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

@app.route("/preview_contract/<session_id>/<contract_type>", methods=["GET"])
def preview_contract(session_id, contract_type):
    logger.info(f"Generating PDF preview for {contract_type} contract, session: {session_id}")

    if contracts_collection is None:
        logger.error("Database service unavailable for PDF preview")
        return jsonify({"error": "Database service unavailable."}), 503
    if contract_type not in ["modified", "marked"]:
        logger.warning(f"Invalid contract type requested: {contract_type}")
        return jsonify({"error": "Invalid contract type."}), 400

    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc:
        logger.warning(f"Session not found for PDF preview: {session_id}")
        return jsonify({"error": "Session not found."}), 404

    pdf_previews_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id}/{CLOUDINARY_PDF_PREVIEWS_SUBFOLDER}"

    existing_pdf_info = session_doc.get("pdf_preview_info", {}).get(contract_type)
    if existing_pdf_info and existing_pdf_info.get("url"):
        logger.info(f"Returning existing PDF preview URL for {contract_type}: {existing_pdf_info['url']}")
        return jsonify({"pdf_url": existing_pdf_info["url"]})

    source_docx_cloudinary_info = None
    if contract_type == "modified":
        source_docx_cloudinary_info = session_doc.get("modified_contract_info", {}).get("docx_cloudinary_info")
    elif contract_type == "marked":
        source_docx_cloudinary_info = session_doc.get("marked_contract_info", {}).get("docx_cloudinary_info")

    if not source_docx_cloudinary_info or not source_docx_cloudinary_info.get("url"):
        logger.warning(f"Source DOCX for {contract_type} contract not found on Cloudinary")
        return jsonify({"error": f"Source DOCX for {contract_type} contract not found on Cloudinary."}), 404

    temp_source_docx_path = None
    temp_pdf_preview_path_local = None
    try:
        original_filename_for_suffix = source_docx_cloudinary_info.get("user_facing_filename", f"{contract_type}_contract.docx")
        temp_source_docx_path = download_file_from_url(source_docx_cloudinary_info["url"], original_filename_for_suffix, TEMP_PROCESSING_FOLDER)
        if not temp_source_docx_path:
            logger.error("Failed to download source DOCX for preview")
            return jsonify({"error": "Failed to download source DOCX for preview."}), 500

        logger.info(f"Converting DOCX to PDF using LibreOffice, output folder: {PDF_PREVIEW_FOLDER}")
        temp_pdf_preview_path_local = convert_docx_to_pdf(temp_source_docx_path, PDF_PREVIEW_FOLDER)

        if not temp_pdf_preview_path_local or not os.path.exists(temp_pdf_preview_path_local):
            logger.error(f"PDF file was not created at {temp_pdf_preview_path_local}")
            raise Exception("PDF file not created by LibreOffice or path is incorrect.")
        else:
            logger.info(f"PDF successfully created locally at: {temp_pdf_preview_path_local}")

        # Generate safe public_id for PDF
        original_filename_base = os.path.splitext(original_filename_for_suffix)[0]
        pdf_safe_public_id = generate_safe_public_id(original_filename_base, f"{contract_type}_preview")

        pdf_upload_result = upload_to_cloudinary_helper(
            temp_pdf_preview_path_local,
            pdf_previews_cloudinary_folder,
            resource_type="raw",
            public_id_prefix=f"{contract_type}_preview",
            custom_public_id=pdf_safe_public_id
        )
        logger.info(f"Cloudinary upload result for PDF preview: {pdf_upload_result}")

        if not pdf_upload_result or not pdf_upload_result.get("secure_url"):
            logger.error(f"Failed to upload PDF preview to Cloudinary. Result: {pdf_upload_result}")
            return jsonify({"error": "Failed to upload PDF preview to Cloudinary."}), 500

        pdf_cloudinary_info = {
            "url": pdf_upload_result.get("secure_url"),
            "public_id": pdf_upload_result.get("public_id"),
            "format": pdf_upload_result.get("format", "pdf"),
            "user_facing_filename": f"{pdf_safe_public_id}.pdf"
        }

        contracts_collection.update_one(
            {"_id": session_id},
            {"$set": {f"pdf_preview_info.{contract_type}": pdf_cloudinary_info}}
        )
        logger.info(f"PDF preview for {contract_type} uploaded to Cloudinary: {pdf_cloudinary_info['url']}")

        return jsonify({"pdf_url": pdf_cloudinary_info["url"]})

    except Exception as e:
        logger.error(f"Error during PDF preview for {contract_type} ({session_id}): {e}")
        traceback.print_exc()
        return jsonify({"error": f"Could not generate PDF preview: {str(e)}"}), 500
    finally:
        if temp_source_docx_path and os.path.exists(temp_source_docx_path):
            os.remove(temp_source_docx_path)
            logger.debug("Cleaned up temporary source DOCX file")
        if temp_pdf_preview_path_local and os.path.exists(temp_pdf_preview_path_local):
            os.remove(temp_pdf_preview_path_local)
            logger.debug("Cleaned up temporary PDF file")

@app.route("/download_pdf_preview/<session_id>/<contract_type>", methods=["GET"])
def download_pdf_preview(session_id, contract_type):
    logger.info(f"PDF download requested for {contract_type} contract, session: {session_id}")

    if contracts_collection is None:
        logger.error("Database service unavailable for PDF download")
        return jsonify({"error": "Database service unavailable."}), 503
    if contract_type not in ["modified", "marked"]:
        logger.warning(f"Invalid contract type for download: {contract_type}")
        return jsonify({"error": "Invalid contract type."}), 400

    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc:
        logger.warning(f"Session not found for PDF download: {session_id}")
        return jsonify({"error": "Session not found."}), 404

    pdf_info = session_doc.get("pdf_preview_info", {}).get(contract_type)
    if not pdf_info or not pdf_info.get("url"):
        logger.warning(f"PDF preview URL for {contract_type} contract not available")
        return jsonify({"error": f"PDF preview URL for {contract_type} contract not yet available or generation failed. Please try previewing first."}), 404

    cloudinary_pdf_url = pdf_info["url"]
    user_facing_filename = pdf_info.get("user_facing_filename", f"{contract_type}_preview_{session_id[:8]}.pdf")

    try:
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
        logger.error(f"HTTP error fetching PDF from Cloudinary: {http_err.response.status_code} - {http_err.response.text}")
        return jsonify({"error": f"Cloudinary denied access to PDF (Status {http_err.response.status_code}). Check asset permissions."}), http_err.response.status_code if http_err.response.status_code >= 400 else 500
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching PDF from Cloudinary for download: {e}")
        return jsonify({"error": "Could not fetch PDF from cloud storage."}), 500
    except Exception as e:
        logger.error(f"Unexpected error during PDF download proxy: {e}")
        return jsonify({"error": "An unexpected error occurred during download."}), 500

@app.route("/generate_modified_contract", methods=["POST"])
def generate_modified_contract():
    session_id = request.cookies.get("session_id") or (request.is_json and request.get_json().get("session_id"))
    logger.info(f"Generating modified contract for session: {session_id}")

    if contracts_collection is None:
        logger.error("Database service unavailable for contract generation")
        return jsonify({"error": "Database service unavailable."}), 503
    if not session_id:
        logger.warning("No session ID provided for contract generation")
        return jsonify({"error": "No session"}), 400

    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc:
        logger.warning(f"Session not found for contract generation: {session_id}")
        return jsonify({"error": "Session not found"}), 404

    original_filename_from_db = session_doc.get("original_filename", "contract.docx")
    contract_lang = session_doc.get("detected_contract_language", "ar")
    confirmed_terms = session_doc.get("confirmed_terms", {})

    logger.info(f"Contract language: {contract_lang}, Confirmed terms: {len(confirmed_terms)}")

    # UNIFIED LOGIC: Use markdown as the source of truth for all formats
    markdown_source = session_doc.get("generated_markdown_from_docx") or session_doc.get("original_contract_markdown")
    if not markdown_source:
        logger.error("Contract source text (markdown) not found for generation")
        return jsonify({"error": "Contract source text (markdown) not found for generation."}), 500

    modified_contracts_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id}/{CLOUDINARY_MODIFIED_CONTRACTS_SUBFOLDER}"
    user_facing_base, _ = os.path.splitext(original_filename_from_db)
    user_facing_clean_base = clean_filename(user_facing_base) or "contract"

    # Generate safe public IDs
    docx_safe_public_id = generate_safe_public_id(user_facing_clean_base, "modified")
    txt_safe_public_id = generate_safe_public_id(user_facing_clean_base, "modified_txt")

    temp_modified_docx_path = None
    temp_modified_txt_path = None

    final_docx_cloudinary_info = None
    final_txt_cloudinary_info = None

    try:
        temp_modified_docx_fd, temp_modified_docx_path = tempfile.mkstemp(suffix=".docx", prefix="mod_docx_", dir=TEMP_PROCESSING_FOLDER)
        os.close(temp_modified_docx_fd)
        temp_modified_txt_fd, temp_modified_txt_path = tempfile.mkstemp(suffix=".txt", prefix="mod_txt_", dir=TEMP_PROCESSING_FOLDER)
        os.close(temp_modified_txt_fd)

        # Generate the modified contract using direct reconstruction
        try:
            logger.info("Reconstructing contract with confirmed modifications")

            # Direct contract reconstruction without LLM for cleaner output
            final_text_content_for_output = markdown_source

            # Apply confirmed modifications directly to the contract text
            for term_id, term_data in confirmed_terms.items():
                if not isinstance(term_data, dict):
                    continue

                original_text = term_data.get("original_text", "")
                confirmed_text = term_data.get("confirmed_text", "")

                if original_text and confirmed_text and original_text != confirmed_text:
                    logger.info(f"Applying modification for term {term_id}")
                    # Replace original text with confirmed modification
                    final_text_content_for_output = final_text_content_for_output.replace(
                        original_text, confirmed_text
                    )

            # Clean any markdown artifacts that might exist
            final_text_content_for_output = re.sub(r'^\[\[ID:.*?\]\]\s*', '', final_text_content_for_output, flags=re.MULTILINE)
            final_text_content_for_output = re.sub(r'```.*?\n', '', final_text_content_for_output, flags=re.MULTILINE)
            final_text_content_for_output = re.sub(r'\n```', '', final_text_content_for_output)

            # Remove any analysis or commentary text that might have leaked in
            lines = final_text_content_for_output.split('\n')
            clean_lines = []
            for line in lines:
                line = line.strip()
                # Skip lines that look like analysis or commentary
                if any(keyword in line.lower() for keyword in [
                    'تحليل', 'ملاحظة', 'تعليق', 'analysis', 'note', 'comment',
                    'يجب أن', 'ينبغي', 'يمكن', 'should', 'must', 'can',
                    'هذا البند', 'this clause', 'المقترح', 'suggested'
                ]) and not any(legal_word in line for legal_word in [
                    'البند', 'المادة', 'الطرف', 'العقد', 'clause', 'article', 'party', 'contract'
                ]):
                    continue
                clean_lines.append(line)

            final_text_content_for_output = '\n'.join(clean_lines)

            if not final_text_content_for_output.strip():
                logger.error("Contract reconstruction resulted in empty content")
                raise ValueError("Contract reconstruction failed - empty result")

        except Exception as e:
            logger.error(f"Failed to reconstruct modified contract: {e}")
            raise ValueError("Contract reconstruction failed")


        logger.info("Creating DOCX and TXT versions of modified contract")
        # Create DOCX from the final regenerated text
        create_docx_from_llm_markdown(final_text_content_for_output, temp_modified_docx_path, contract_lang)

        # Save the plain text version
        with open(temp_modified_txt_path, "w", encoding="utf-8") as f:
            f.write(final_text_content_for_output)

        # Upload both versions to Cloudinary
        logger.info("Uploading modified contract files to Cloudinary")
        docx_upload_res = upload_to_cloudinary_helper(
            temp_modified_docx_path,
            modified_contracts_cloudinary_folder,
            public_id_prefix="modified",
            custom_public_id=docx_safe_public_id
        )
        if docx_upload_res:
            final_docx_cloudinary_info = {
                "url": docx_upload_res.get("secure_url"),
                "public_id": docx_upload_res.get("public_id"),
                "format": "docx",
                "user_facing_filename": f"{docx_safe_public_id}.docx"
            }
            logger.info(f"Modified DOCX uploaded: {final_docx_cloudinary_info['url']}")

        txt_upload_res = upload_to_cloudinary_helper(
            temp_modified_txt_path,
            modified_contracts_cloudinary_folder,
            resource_type="raw",
            public_id_prefix="modified_txt",
            custom_public_id=txt_safe_public_id
        )
        if txt_upload_res:
            final_txt_cloudinary_info = {
                "url": txt_upload_res.get("secure_url"),
                "public_id": txt_upload_res.get("public_id"),
                "format": "txt",
                "user_facing_filename": f"{txt_safe_public_id}.txt"
            }
            logger.info(f"Modified TXT uploaded: {final_txt_cloudinary_info['url']}")

        contracts_collection.update_one(
            {"_id": session_id},
            {"$set": {
                "modified_contract_info": {
                    "docx_cloudinary_info": final_docx_cloudinary_info,
                    "txt_cloudinary_info": final_txt_cloudinary_info,
                    "generation_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
            }}
        )

        logger.info(f"Modified contract generated successfully for session: {session_id}")
        return jsonify({
            "success": True,
            "message": "Modified contract generated.",
            "modified_docx_cloudinary_url": final_docx_cloudinary_info.get("url") if final_docx_cloudinary_info else None,
            "modified_txt_cloudinary_url": final_txt_cloudinary_info.get("url") if final_txt_cloudinary_info else None
        })
    except Exception as e:
        logger.error(f"Failed to generate modified contract for session {session_id}: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Failed: {str(e)}"}), 500
    finally:
        if temp_modified_docx_path and os.path.exists(temp_modified_docx_path):
            os.remove(temp_modified_docx_path)
            logger.debug("Cleaned up temporary modified DOCX file")
        if temp_modified_txt_path and os.path.exists(temp_modified_txt_path):
            os.remove(temp_modified_txt_path)
            logger.debug("Cleaned up temporary modified TXT file")

def sort_key_for_pdf_txt_terms(term):
    term_id_str = term.get("term_id", "")
    match = re.match(r"clause_(\d+)", term_id_str)
    if match:
        return int(match.group(1))
    return float('inf')

@app.route("/generate_marked_contract", methods=["POST"])
def generate_marked_contract():
    session_id = request.cookies.get("session_id") or (request.is_json and request.get_json().get("session_id"))
    logger.info(f"Generating marked contract for session: {session_id}")

    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for marked contract generation")
        return jsonify({"error": "Database service unavailable."}), 503
    if not session_id:
        logger.warning("No session ID provided for marked contract generation")
        return jsonify({"error": "No session"}), 400

    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc:
        logger.warning(f"Session not found for marked contract generation: {session_id}")
        return jsonify({"error": "Session not found"}), 404

    original_filename_from_db = session_doc.get("original_filename", "contract.docx")
    contract_lang = session_doc.get("detected_contract_language", "ar")

    # UNIFIED LOGIC: Use markdown as the source of truth for all formats
    markdown_source = session_doc.get("generated_markdown_from_docx") or session_doc.get("original_contract_markdown")
    if not markdown_source:
        logger.error("Contract source text (markdown) not found for marked contract generation")
        return jsonify({"error": "Contract source text (markdown) not found for generation."}), 500

    db_terms_list = list(terms_collection.find({"session_id": session_id}))
    logger.info(f"Found {len(db_terms_list)} terms for marking")

    marked_contracts_cloudinary_folder = f"{CLOUDINARY_BASE_FOLDER}/{session_id}/{CLOUDINARY_MARKED_CONTRACTS_SUBFOLDER}"
    user_facing_base, _ = os.path.splitext(original_filename_from_db)
    user_facing_clean_base = clean_filename(user_facing_base) or "contract"
    marked_docx_safe_public_id = generate_safe_public_id(user_facing_clean_base, "marked")

    temp_marked_docx_path = None
    final_marked_docx_cloudinary_info = None

    try:
        temp_marked_docx_fd, temp_marked_docx_path = tempfile.mkstemp(suffix=".docx", prefix="marked_", dir=TEMP_PROCESSING_FOLDER)
        os.close(temp_marked_docx_fd)

        # UNIFIED LOGIC: Use create_docx_from_llm_markdown for all formats
        # Sort terms to ensure correct order of application. This helps for both DOCX-derived and PDF-derived markdown.
        def smart_sort_key(term):
            term_id = term.get("term_id", "")
            if term_id.startswith("para_"):
                # Sort by para_1, para_10, etc. correctly
                parts = re.findall(r'[A-Za-z]+|\d+', term_id) # Split into text and number parts
                return tuple(int(p) if p.isdigit() else p for p in parts)
            elif term_id.startswith("clause_"):
                match = re.match(r"clause_(\d+)", term_id)
                return ('clause', int(match.group(1))) if match else ('clause', float('inf'))
            return ('z', float('inf')) # Put non-matching last

        sorted_db_terms = sorted(db_terms_list, key=smart_sort_key)
        logger.info(f"Sorted {len(sorted_db_terms)} terms for marking")

        logger.info("Creating marked DOCX from markdown with term highlighting")
        create_docx_from_llm_markdown(
            markdown_source,
            temp_marked_docx_path,
            contract_lang,
            terms_for_marking=sorted_db_terms
        )

        logger.info("Uploading marked contract to Cloudinary")
        marked_upload_res = upload_to_cloudinary_helper(
            temp_marked_docx_path,
            marked_contracts_cloudinary_folder,
            public_id_prefix="marked",
            custom_public_id=marked_docx_safe_public_id
        )
        if marked_upload_res:
            final_marked_docx_cloudinary_info = {
                "url": marked_upload_res.get("secure_url"),
                "public_id": marked_upload_res.get("public_id"),
                "format": "docx",
                "user_facing_filename": f"{marked_docx_safe_public_id}.docx"
            }
            logger.info(f"Marked contract uploaded: {final_marked_docx_cloudinary_info['url']}")

        contracts_collection.update_one(
            {"_id": session_id},
            {"$set": {
                "marked_contract_info": {
                    "docx_cloudinary_info": final_marked_docx_cloudinary_info,
                    "generation_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                 }
            }}
        )

        logger.info(f"Marked contract generated successfully for session: {session_id}")
        return jsonify({
            "success": True,
            "message": "Marked contract generated.",
            "marked_docx_cloudinary_url": final_marked_docx_cloudinary_info.get("url") if final_marked_docx_cloudinary_info else None
        })
    except Exception as e:
        logger.error(f"Failed to generate marked contract for session {session_id}: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Failed: {str(e)}"}), 500
    finally:
        if temp_marked_docx_path and os.path.exists(temp_marked_docx_path):
            os.remove(temp_marked_docx_path)
            logger.debug("Cleaned up temporary marked DOCX file")

@app.route("/interact", methods=["POST"])
def interact():
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for interaction")
        return jsonify({"error": "Database service is currently unavailable."}), 503
    if not request.is_json:
        logger.warning("Non-JSON request received for interaction")
        return jsonify({"error": "Unsupported Media Type: Expected application/json"}), 415

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

    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc:
        logger.warning(f"Session not found for interaction: {session_id}")
        return jsonify({"error": "الجلسة غير موجودة أو منتهية الصلاحية"}), 404

    contract_lang = session_doc.get("detected_contract_language", "ar")
    try:
        formatted_interaction_prompt = INTERACTION_PROMPT.format(output_language=contract_lang)
    except KeyError as ke:
        logger.warning(f"KeyError formatting INTERACTION_PROMPT: {ke}. Using default language 'ar'")
        formatted_interaction_prompt = INTERACTION_PROMPT.format(output_language='ar')

    full_contract_context_for_llm = session_doc.get("original_contract_plain", session_doc.get("original_contract_markdown", ""))

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
        logger.info("Sending interaction to LLM")
        chat = get_chat_session(f"{session_id}_interaction", system_instruction=formatted_interaction_prompt, force_new=True)
        response = chat.send_message(interaction_payload_for_llm)
        external_response_text = response.text

        if external_response_text is None or external_response_text.startswith("ERROR_PROMPT_BLOCKED") or external_response_text.startswith("ERROR_CONTENT_BLOCKED"):
            error_msg_detail = external_response_text if external_response_text else "Blocked or empty response from API."
            logger.warning(f"Interaction blocked by API: {error_msg_detail}")
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
        logger.info(f"Interaction saved for session {session_id}, term: {term_id_context or 'general'}")

        resp = Response(external_response_text, status=200, mimetype='text/plain; charset=utf-8')
        resp.set_cookie("session_id", session_id, max_age=86400*30, httponly=True, samesite='Lax', secure=request.is_secure)
        return resp
    except Exception as e:
        logger.error(f"Error processing interaction for session {session_id}: {e}")
        traceback.print_exc()
        return jsonify({"error": f"فشل في معالجة التفاعل: {str(e)}"}), 500

@app.route("/review_modification", methods=["POST"])
def review_modification():
    if contracts_collection is None:
        logger.error("Database service unavailable for review modification")
        return jsonify({"error": "Database service is currently unavailable."}), 503
    if not request.is_json:
        logger.warning("Non-JSON request received for review modification")
        return jsonify({"error": "Unsupported Media Type"}), 415

    data = request.get_json();
    session_id = request.cookies.get("session_id") or data.get("session_id")
    term_id = data.get("term_id");
    user_modified_text = data.get("user_modified_text");
    original_term_text_from_req = data.get("original_term_text")

    logger.info(f"Reviewing modification for session: {session_id}, term: {term_id}")

    if not all([session_id, term_id, user_modified_text is not None, original_term_text_from_req is not None]):
        logger.warning("Incomplete data for review modification")
        return jsonify({"error": "بيانات ناقصة"}), 400

    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc:
        logger.warning(f"Session not found for review modification: {session_id}")
        return jsonify({"error": "الجلسة غير موجودة"}), 404

    contract_lang = session_doc.get("detected_contract_language", "ar")
    try:
        formatted_review_prompt = REVIEW_MODIFICATION_PROMPT.format(output_language=contract_lang)
    except KeyError as ke:
        logger.error(f"KeyError in REVIEW_MODIFICATION_PROMPT: {ke}")
        return jsonify({"error": f"Prompt format error: {ke}"}), 500

    review_payload_for_llm = json.dumps({
        "original_term_text": original_term_text_from_req,
        "user_modified_text": user_modified_text
    }, ensure_ascii=False, indent=2)

    try:
        logger.info("Sending modification review to LLM")
        chat = get_chat_session(f"{session_id}_review_{term_id}", system_instruction=formatted_review_prompt, force_new=True)
        response = chat.send_message(review_payload_for_llm)

        if response.text is None or response.text.startswith("ERROR_PROMPT_BLOCKED") or response.text.startswith("ERROR_CONTENT_BLOCKED"):
            error_msg_detail = response.text if response.text else "Blocked or empty response from review API."
            logger.warning(f"Review modification blocked: {error_msg_detail}")
            return jsonify({"error": f"Blocked: {error_msg_detail}"}), 400

        cleaned_llm_response = clean_model_response(response.text)
        review_result = json.loads(cleaned_llm_response)

        logger.info(f"Review modification completed for session {session_id}, term {term_id}")
        return jsonify(review_result), 200
    except json.JSONDecodeError as je:
        logger.error(f"JSONDecodeError in review modification for session {session_id}, term {term_id}: {je}")
        traceback.print_exc()
        return jsonify({"error": f"فشل تحليل استجابة المراجعة: {str(je)}"}), 500
    except Exception as e:
        logger.error(f"Error in review modification for session {session_id}, term {term_id}: {e}")
        traceback.print_exc()
        return jsonify({"error": f"خطأ في مراجعة التعديل: {str(e)}"}), 500

@app.route("/feedback/expert", methods=["POST"])
def submit_expert_feedback():
    if expert_feedback_collection is None or terms_collection is None:
        logger.error("Database service unavailable for expert feedback")
        return jsonify({"error": "Database service is currently unavailable."}), 503

    if not request.is_json:
        logger.warning("Non-JSON request received for expert feedback")
        return jsonify({"error": "Unsupported Media Type: Expected application/json"}), 415

    data = request.get_json()
    session_id = request.cookies.get("session_id") or data.get("session_id")
    term_id = data.get("term_id")
    feedback_data = data.get("feedback_data")
    expert_user_id = "default_expert_id"
    expert_username = "Default Expert"

    logger.info(f"Submitting expert feedback for session: {session_id}, term: {term_id}")

    if not all([session_id, term_id, feedback_data]):
        logger.warning("Incomplete data for expert feedback")
        return jsonify({"error": "البيانات المطلوبة غير مكتملة (session_id, term_id, feedback_data)"}), 400

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

        logger.info(f"Expert feedback saved for session {session_id}, term {term_id}")
        return jsonify({"success": True, "message": "تم حفظ ملاحظات الخبير بنجاح.", "feedback_id": str(result.inserted_id)}), 201
    except Exception as e:
        logger.error(f"Error saving expert feedback for session {session_id}, term {term_id}: {e}")
        traceback.print_exc()
        return jsonify({"error": f"فشل حفظ ملاحظات الخبير: {str(e)}"}), 500

@app.route("/confirm_modification", methods=["POST"])
def confirm_modification():
    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for confirm modification")
        return jsonify({"error": "Database service is currently unavailable."}), 503

    data = request.get_json()
    if not data:
        logger.warning("No data sent in confirm modification request")
        return jsonify({"error": "لم يتم إرسال بيانات في الطلب"}), 400

    term_id_from_req = data.get("term_id")
    modified_text_from_req = data.get("modified_text")
    session_id_from_req = request.cookies.get("session_id") or data.get("session_id")

    logger.info(f"Confirming modification for session: {session_id_from_req}, term: {term_id_from_req}")

    if term_id_from_req is None or modified_text_from_req is None or not session_id_from_req:
        logger.warning("Incomplete data for confirm modification")
        return jsonify({"error": "البيانات المطلوبة غير مكتملة"}), 400

    session_doc = contracts_collection.find_one({"_id": session_id_from_req})
    if not session_doc:
        logger.warning(f"Session not found for confirm modification: {session_id_from_req}")
        return jsonify({"error": "الجلسة غير موجودة"}), 404

    updated_confirmed_terms = session_doc.get("confirmed_terms", {})
    # Store the original text along with the confirmed text for reconstruction
    term_doc = terms_collection.find_one({"session_id": session_id_from_req, "term_id": term_id_from_req})
    if term_doc:
        updated_confirmed_terms[str(term_id_from_req)] = {
            "original_text": term_doc.get("term_text", ""),
            "confirmed_text": modified_text_from_req
        }
    else:
        logger.warning(f"Original term not found in DB for confirmation: {term_id_from_req}")
        updated_confirmed_terms[str(term_id_from_req)] = {
            "original_text": "", # Fallback if term not found
            "confirmed_text": modified_text_from_req
        }

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

        logger.info(f"Modification confirmed for session {session_id_from_req}, term {term_id_from_req}")
        return jsonify({"success": True, "message": f"تم تأكيد التعديل للبند: {term_id_from_req}"})
    except Exception as e:
        logger.error(f"Error confirming modification for session {session_id_from_req}, term {term_id_from_req}: {e}")
        traceback.print_exc()
        return jsonify({"error": f"خطأ أثناء تأكيد التعديل: {str(e)}"}), 500

@app.route("/session/<session_id>", methods=["GET"])
def get_session_details(session_id):
    logger.info(f"Fetching session details for: {session_id}")

    if contracts_collection is None :
        logger.error("Database service unavailable for session details")
        return jsonify({"error": "Database service is currently unavailable."}), 503

    session_doc = contracts_collection.find_one({"_id": session_id})
    if not session_doc:
        logger.warning(f"Session not found: {session_id}")
        return jsonify({"error": "الجلسة غير موجودة"}), 404

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

    logger.info(f"Session details retrieved for: {session_id}")
    return jsonify(session_doc), 200

@app.route("/terms/<session_id>", methods=["GET"])
def get_session_terms(session_id):
    logger.info(f"Fetching terms for session: {session_id}")

    if terms_collection is None :
        logger.error("Database service unavailable for terms retrieval")
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
        if contracts_collection is None:
            logger.error("Database service unavailable for session validation")
            return jsonify({"error": "Database service is currently unavailable."}), 503
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            logger.warning(f"Session not found for terms retrieval: {session_id}")
            return jsonify({"error": "الجلسة غير موجودة"}), 404
        logger.info(f"No terms found for session: {session_id}")
        return jsonify([]), 200

    logger.info(f"Retrieved {len(terms_list)} terms for session: {session_id}")
    return jsonify(terms_list), 200

@app.route("/api/stats/user", methods=["GET"])
def get_user_stats():
    """
    Calculates and returns statistics for the user.
    This is a simplified example; in a real multi-user app, you'd filter by user ID.
    """
    logger.info("Calculating user statistics")

    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for user stats")
        return jsonify({"error": "Database service is currently unavailable."}), 503

    try:
        total_sessions = contracts_collection.count_documents({})
        total_terms_analyzed = terms_collection.count_documents({})

        # This is a simplified compliance rate. A more accurate calculation
        # would consider user overrides and expert feedback per session.
        compliant_terms = terms_collection.count_documents({"is_valid_sharia": True})
        compliance_rate = (compliant_terms / total_terms_analyzed * 100) if total_terms_analyzed > 0 else 0

        # This is a placeholder for average processing time.
        # A real implementation would require storing timestamps for analysis start/end.
        average_processing_time = 15.5 # Placeholder value in seconds

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

@app.route("/api/history", methods=["GET"])
def get_history():
    """
    Fetches all contract analysis sessions and enriches them with calculated stats
    for the mobile app's history screen.
    """
    logger.info("Fetching contract analysis history")

    if contracts_collection is None or terms_collection is None:
        logger.error("Database service unavailable for history")
        return jsonify({"error": "Database service is currently unavailable."}), 503

    try:
        # 1. Fetch all contracts, sorted by the most recent first
        contracts_cursor = contracts_collection.find().sort("analysis_timestamp", -1)
        contracts = list(contracts_cursor)

        if not contracts:
            logger.info("No contract history found")
            return jsonify([]), 200

        session_ids = [c["session_id"] for c in contracts]

        # 2. Fetch all relevant terms in a single efficient query
        terms_cursor = terms_collection.find({"session_id": {"$in": session_ids}})

        # 3. Group terms by session_id for easy lookup
        terms_by_session = {}
        for term in terms_cursor:
            session_id = term["session_id"]
            if session_id not in terms_by_session:
                terms_by_session[session_id] = []

            # Clean up ObjectId from term document
            if '_id' in term and isinstance(term['_id'], ObjectId):
                term['_id'] = str(term['_id'])
            if 'last_expert_feedback_id' in term and isinstance(term.get('last_expert_feedback_id'), ObjectId):
                 term['last_expert_feedback_id'] = str(term['last_expert_feedback_id'])

            terms_by_session[session_id].append(term)

        # 4. Process each contract and enrich it with calculated data
        history_results = []
        for contract_doc in contracts:
            session_id = contract_doc["session_id"]
            session_terms = terms_by_session.get(session_id, [])

            # Calculate compliance percentage
            total_terms = len(session_terms)
            valid_terms = sum(1 for term in session_terms if term.get("is_valid_sharia") is True)
            compliance_percentage = (valid_terms / total_terms * 100) if total_terms > 0 else 100

            # Get other stats directly from the contract document
            interactions_count = len(contract_doc.get("interactions", []))
            modifications_made = len(contract_doc.get("confirmed_terms", {}))
            generated_contracts = bool(contract_doc.get("modified_contract_info") or contract_doc.get("marked_contract_info"))

            # Clean up ObjectId and datetime objects for JSON serialization
            if '_id' in contract_doc and isinstance(contract_doc['_id'], ObjectId):
                contract_doc['_id'] = str(contract_doc['_id'])
            if 'analysis_timestamp' in contract_doc and isinstance(contract_doc['analysis_timestamp'], datetime.datetime):
                contract_doc['analysis_timestamp'] = contract_doc['analysis_timestamp'].isoformat()

            # Build the final response object for this session
            enriched_session = {
                **contract_doc,
                "analysis_results": session_terms, # Embed the terms as expected by the client
                "compliance_percentage": round(compliance_percentage, 2),
                # The frontend also calculates these, but providing them from the backend is more robust
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

if __name__ == "__main__":
    logger.info("Starting Shariaa Analyzer Flask server on 0.0.0.0:5000")
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)