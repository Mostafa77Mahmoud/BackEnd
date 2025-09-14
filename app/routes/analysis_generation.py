"""
Analysis Generation Routes

Contract generation and PDF handling endpoints.
"""

import os
import logging
import datetime
import tempfile
from flask import Blueprint, request, jsonify

# Import services
from app.services.database import get_contracts_collection

logger = logging.getLogger(__name__)

# Get blueprint from __init__.py
from . import analysis_bp


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
        
        logger.info(f"PDF preview generated successfully for {contract_type}, session: {session_id}")
        return jsonify({
            "pdf_url": pdf_cloudinary_result.get("url"),
            "filename": f"{contract_type}_preview_{session_id[:8]}.pdf"
        })
        
    except Exception as e:
        logger.error(f"Error generating PDF preview: {str(e)}")
        return jsonify({"error": "Failed to generate PDF preview."}), 500


@analysis_bp.route('/download_pdf_preview/<session_id>/<contract_type>', methods=['GET'])
def download_pdf_preview(session_id, contract_type):
    """Proxy PDF downloads from Cloudinary."""
    logger.info(f"Processing PDF download request for {contract_type}, session: {session_id}")
    
    contracts_collection = get_contracts_collection()
    
    if contracts_collection is None:
        return jsonify({"error": "Database service unavailable."}), 503
    
    if contract_type not in ["modified", "marked"]:
        return jsonify({"error": "Invalid contract type."}), 400
    
    try:
        session_doc = contracts_collection.find_one({"_id": session_id})
        if not session_doc:
            return jsonify({"error": "Session not found."}), 404
        
        # Get PDF info
        pdf_info = session_doc.get("pdf_preview_info", {}).get(contract_type)
        if not pdf_info or not pdf_info.get("url"):
            return jsonify({"error": "PDF preview not found. Generate preview first."}), 404
        
        # Return download info
        return jsonify({
            "download_url": pdf_info["url"],
            "filename": pdf_info.get("user_facing_filename", f"{contract_type}_preview.pdf"),
            "content_type": "application/pdf"
        })
        
    except Exception as e:
        logger.error(f"Error processing PDF download: {str(e)}")
        return jsonify({"error": "Failed to process PDF download."}), 500