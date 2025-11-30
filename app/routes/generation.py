"""
Generation Routes

Contract generation and PDF preview endpoints.
Matches OldStrcturePerfectProject/api_server.py exactly.
"""

import os
import re
import json
import datetime
import logging
import tempfile
import traceback
import urllib.parse
import requests
from flask import Blueprint, request, jsonify, Response, current_app

from app.services.database import get_contracts_collection, get_terms_collection

logger = logging.getLogger(__name__)
generation_bp = Blueprint('generation', __name__)


def sort_key_for_pdf_txt_terms(term):
    """Sort key for terms from PDF/TXT contracts."""
    term_id_str = term.get("term_id", "")
    match = re.match(r"clause_(\d+)", term_id_str)
    if match:
        return int(match.group(1))
    return float('inf')


def smart_sort_key(term):
    """Smart sorting for terms - handles both para_ and clause_ formats."""
    term_id = term.get("term_id", "")
    if term_id.startswith("para_"):
        parts = re.findall(r'[A-Za-z]+|\d+', term_id)
        return tuple(int(p) if p.isdigit() else p for p in parts)
    elif term_id.startswith("clause_"):
        match = re.match(r"clause_(\d+)", term_id)
        return ('clause', int(match.group(1))) if match else ('clause', float('inf'))
    return ('z', float('inf'))


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
        from app.services.ai_service import send_text_to_remote_api
        
        generation_prompt = f"""
        Generate a Sharia-compliant contract based on the following brief:
        
        Brief: {brief}
        Contract Type: {contract_type}
        Jurisdiction: {jurisdiction}
        
        Please provide a complete contract in Arabic that follows Islamic law principles.
        """
        
        response = send_text_to_remote_api(generation_prompt)
        
        if not response:
            return jsonify({"error": "Failed to generate contract."}), 500
        
        session_id = f"gen_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
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


@generation_bp.route('/preview_contract/<session_id>/<contract_type>', methods=['GET'])
def preview_contract(session_id, contract_type):
    """Generate PDF preview of contract."""
    logger.info(f"Generating PDF preview for {contract_type} contract, session: {session_id}")

    contracts_collection = get_contracts_collection()
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

    cloudinary_base_folder = current_app.config.get('CLOUDINARY_BASE_FOLDER', 'shariaa_analyzer')
    pdf_previews_subfolder = current_app.config.get('CLOUDINARY_PDF_PREVIEWS_SUBFOLDER', 'pdf_previews')
    pdf_previews_cloudinary_folder = f"{cloudinary_base_folder}/{session_id}/{pdf_previews_subfolder}"
    temp_processing_folder = current_app.config.get('TEMP_PROCESSING_FOLDER', '/tmp/shariaa_temp')
    pdf_preview_folder = current_app.config.get('PDF_PREVIEW_FOLDER', '/tmp/pdf_previews')

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
        from app.utils.file_helpers import download_file_from_url, ensure_dir
        from app.services.document_processor import convert_docx_to_pdf
        from app.services.cloudinary_service import upload_to_cloudinary_helper
        from app.utils.text_processing import generate_safe_public_id
        
        ensure_dir(temp_processing_folder)
        ensure_dir(pdf_preview_folder)
        
        original_filename_for_suffix = source_docx_cloudinary_info.get("user_facing_filename", f"{contract_type}_contract.docx")
        temp_source_docx_path = download_file_from_url(source_docx_cloudinary_info["url"], original_filename_for_suffix, temp_processing_folder)
        if not temp_source_docx_path:
            logger.error("Failed to download source DOCX for preview")
            return jsonify({"error": "Failed to download source DOCX for preview."}), 500

        logger.info(f"Converting DOCX to PDF using LibreOffice, output folder: {pdf_preview_folder}")
        temp_pdf_preview_path_local = convert_docx_to_pdf(temp_source_docx_path, pdf_preview_folder)

        if not temp_pdf_preview_path_local or not os.path.exists(temp_pdf_preview_path_local):
            logger.error(f"PDF file was not created at {temp_pdf_preview_path_local}")
            raise Exception("PDF file not created by LibreOffice or path is incorrect.")
        else:
            logger.info(f"PDF successfully created locally at: {temp_pdf_preview_path_local}")

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


@generation_bp.route('/download_pdf_preview/<session_id>/<contract_type>', methods=['GET'])
def download_pdf_preview(session_id, contract_type):
    """Download PDF preview of contract."""
    logger.info(f"PDF download requested for {contract_type} contract, session: {session_id}")

    contracts_collection = get_contracts_collection()
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
        from app.utils.file_helpers import clean_filename
        
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


@generation_bp.route('/generate_modified_contract', methods=['POST'])
def generate_modified_contract():
    """Generate modified contract with confirmed modifications applied."""
    session_id = request.cookies.get("session_id") or (request.is_json and request.get_json().get("session_id"))
    logger.info(f"Generating modified contract for session: {session_id}")

    contracts_collection = get_contracts_collection()
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

    markdown_source = session_doc.get("generated_markdown_from_docx") or session_doc.get("original_contract_markdown")
    if not markdown_source:
        logger.error("Contract source text (markdown) not found for generation")
        return jsonify({"error": "Contract source text (markdown) not found for generation."}), 500

    cloudinary_base_folder = current_app.config.get('CLOUDINARY_BASE_FOLDER', 'shariaa_analyzer')
    modified_contracts_subfolder = current_app.config.get('CLOUDINARY_MODIFIED_CONTRACTS_SUBFOLDER', 'modified_contracts')
    modified_contracts_cloudinary_folder = f"{cloudinary_base_folder}/{session_id}/{modified_contracts_subfolder}"
    temp_processing_folder = current_app.config.get('TEMP_PROCESSING_FOLDER', '/tmp/shariaa_temp')
    
    from app.utils.file_helpers import clean_filename, ensure_dir
    from app.utils.text_processing import generate_safe_public_id
    from app.services.document_processor import create_docx_from_llm_markdown
    from app.services.cloudinary_service import upload_to_cloudinary_helper
    
    ensure_dir(temp_processing_folder)
    
    user_facing_base, _ = os.path.splitext(original_filename_from_db)
    user_facing_clean_base = clean_filename(user_facing_base) or "contract"

    docx_safe_public_id = generate_safe_public_id(user_facing_clean_base, "modified")
    txt_safe_public_id = generate_safe_public_id(user_facing_clean_base, "modified_txt")

    temp_modified_docx_path = None
    temp_modified_txt_path = None

    final_docx_cloudinary_info = None
    final_txt_cloudinary_info = None

    try:
        temp_modified_docx_fd, temp_modified_docx_path = tempfile.mkstemp(suffix=".docx", prefix="mod_docx_", dir=temp_processing_folder)
        os.close(temp_modified_docx_fd)
        temp_modified_txt_fd, temp_modified_txt_path = tempfile.mkstemp(suffix=".txt", prefix="mod_txt_", dir=temp_processing_folder)
        os.close(temp_modified_txt_fd)

        try:
            logger.info("Reconstructing contract with confirmed modifications")

            final_text_content_for_output = markdown_source

            for term_id, term_data in confirmed_terms.items():
                if not isinstance(term_data, dict):
                    continue

                original_text = term_data.get("original_text", "")
                confirmed_text = term_data.get("confirmed_text", "")

                if original_text and confirmed_text and original_text != confirmed_text:
                    logger.info(f"Applying modification for term {term_id}")
                    final_text_content_for_output = final_text_content_for_output.replace(
                        original_text, confirmed_text
                    )

            final_text_content_for_output = re.sub(r'^\[\[ID:.*?\]\]\s*', '', final_text_content_for_output, flags=re.MULTILINE)
            final_text_content_for_output = re.sub(r'```.*?\n', '', final_text_content_for_output, flags=re.MULTILINE)
            final_text_content_for_output = re.sub(r'\n```', '', final_text_content_for_output)

            lines = final_text_content_for_output.split('\n')
            clean_lines = []
            for line in lines:
                line = line.strip()
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
        create_docx_from_llm_markdown(final_text_content_for_output, temp_modified_docx_path, contract_lang)

        with open(temp_modified_txt_path, "w", encoding="utf-8") as f:
            f.write(final_text_content_for_output)

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


@generation_bp.route('/generate_marked_contract', methods=['POST'])
def generate_marked_contract():
    """Generate marked contract with highlighted terms."""
    session_id = request.cookies.get("session_id") or (request.is_json and request.get_json().get("session_id"))
    logger.info(f"Generating marked contract for session: {session_id}")

    contracts_collection = get_contracts_collection()
    terms_collection = get_terms_collection()
    
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

    markdown_source = session_doc.get("generated_markdown_from_docx") or session_doc.get("original_contract_markdown")
    if not markdown_source:
        logger.error("Contract source text (markdown) not found for marked contract generation")
        return jsonify({"error": "Contract source text (markdown) not found for generation."}), 500

    db_terms_list = list(terms_collection.find({"session_id": session_id}))
    logger.info(f"Found {len(db_terms_list)} terms for marking")

    cloudinary_base_folder = current_app.config.get('CLOUDINARY_BASE_FOLDER', 'shariaa_analyzer')
    marked_contracts_subfolder = current_app.config.get('CLOUDINARY_MARKED_CONTRACTS_SUBFOLDER', 'marked_contracts')
    marked_contracts_cloudinary_folder = f"{cloudinary_base_folder}/{session_id}/{marked_contracts_subfolder}"
    temp_processing_folder = current_app.config.get('TEMP_PROCESSING_FOLDER', '/tmp/shariaa_temp')
    
    from app.utils.file_helpers import clean_filename, ensure_dir
    from app.utils.text_processing import generate_safe_public_id
    from app.services.document_processor import create_docx_from_llm_markdown
    from app.services.cloudinary_service import upload_to_cloudinary_helper
    
    ensure_dir(temp_processing_folder)
    
    user_facing_base, _ = os.path.splitext(original_filename_from_db)
    user_facing_clean_base = clean_filename(user_facing_base) or "contract"
    marked_docx_safe_public_id = generate_safe_public_id(user_facing_clean_base, "marked")

    temp_marked_docx_path = None
    final_marked_docx_cloudinary_info = None

    try:
        temp_marked_docx_fd, temp_marked_docx_path = tempfile.mkstemp(suffix=".docx", prefix="marked_", dir=temp_processing_folder)
        os.close(temp_marked_docx_fd)

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
