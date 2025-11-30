from flask import Blueprint, request, jsonify, current_app
from app.services.file_search import FileSearchService
from app.utils.logging_utils import get_logger

logger = get_logger(__name__)
file_search_bp = Blueprint('file_search', __name__)

def get_service():
    """Helper to get initialized service."""
    return FileSearchService()

@file_search_bp.route('/file_search/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    logger.info("Health check endpoint called")
    return jsonify({
        "status": "healthy",
        "message": "File Search API is running"
    })

@file_search_bp.route('/file_search/store-info', methods=['GET'])
def store_info():
    """Get File Search Store information"""
    logger.info("Store info endpoint called")
    try:
        service = get_service()
        info = service.get_store_info()
        logger.info(f"Store info retrieved: {info.get('status')}")
        return jsonify(info)
    except Exception as e:
        logger.error(f"Error in store_info: {e}")
        return jsonify({"error": str(e)}), 500

@file_search_bp.route('/file_search/extract_terms', methods=['POST'])
def extract_terms():
    """Extract key terms endpoint - extracts important clauses from contract"""
    logger.info("Extract terms endpoint called")
    try:
        service = get_service()
        data = request.get_json()
        
        if not data or 'contract_text' not in data:
            logger.warning("Missing 'contract_text' in request body")
            return jsonify({
                "error": "Missing 'contract_text' in request body"
            }), 400
        
        contract_text = data['contract_text']
        
        if not contract_text.strip():
            logger.warning("Contract text is empty")
            return jsonify({
                "error": "Contract text cannot be empty"
            }), 400
        
        logger.info(f"Extracting terms for contract of length {len(contract_text)}")
        extracted_terms = service.extract_key_terms(contract_text)
        logger.info(f"Extracted {len(extracted_terms)} terms")
        
        response = {
            "contract_text": contract_text,
            "extracted_terms": extracted_terms,
            "total_terms": len(extracted_terms)
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in extract_terms: {e}")
        return jsonify({
            "error": str(e)
        }), 500

@file_search_bp.route('/file_search/search', methods=['POST'])
def file_search():
    """
    File Search endpoint - two-step process:
    1. Extracts key terms from contract
    2. Searches for relevant chunks using extracted terms
    """
    logger.info("File search endpoint called")
    try:
        service = get_service()
        data = request.get_json()
        
        if not data or 'contract_text' not in data:
            logger.warning("Missing 'contract_text' in request body")
            return jsonify({
                "error": "Missing 'contract_text' in request body"
            }), 400
        
        contract_text = data['contract_text']
        top_k = data.get('top_k', current_app.config.get('TOP_K_CHUNKS', 10))
        
        if not contract_text.strip():
            logger.warning("Contract text is empty")
            return jsonify({
                "error": "Contract text cannot be empty"
            }), 400
        
        logger.info(f"Starting file search with top_k={top_k}")
        chunks, extracted_terms = service.search_chunks(contract_text, top_k)
        logger.info(f"Search completed. Found {len(chunks)} chunks.")
        
        response = {
            "contract_text": contract_text,
            "extracted_terms": extracted_terms,
            "chunks": chunks,
            "total_chunks": len(chunks),
            "top_k": top_k,
            "message": "Two-step process: extracted key terms then searched File Search"
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in file_search: {e}")
        return jsonify({
            "error": str(e)
        }), 500
