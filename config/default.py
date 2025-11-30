"""
Default Configuration

Configuration settings for the Shariaa Contract Analyzer.
Matches OldStrcturePerfectProject/config.py exactly.
"""

import os

class DefaultConfig:
    """Default configuration settings."""
    
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash")
    TEMPERATURE = int(os.environ.get("TEMPERATURE", "0"))
    
    MONGO_URI = os.environ.get("MONGO_URI")
    
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")
    CLOUDINARY_BASE_FOLDER = "shariaa_analyzer_uploads"
    
    CLOUDINARY_UPLOAD_FOLDER = "contract_uploads"
    CLOUDINARY_ORIGINAL_UPLOADS_SUBFOLDER = "original_contracts"
    CLOUDINARY_ANALYSIS_RESULTS_SUBFOLDER = "analysis_results_json"
    CLOUDINARY_MODIFIED_CONTRACTS_SUBFOLDER = "modified_contracts"
    CLOUDINARY_MARKED_CONTRACTS_SUBFOLDER = "marked_contracts"
    CLOUDINARY_PDF_PREVIEWS_SUBFOLDER = "pdf_previews"
    
    LIBREOFFICE_PATH = os.environ.get("LIBREOFFICE_PATH", "libreoffice")
    
    TEMP_PROCESSING_FOLDER = os.environ.get("TEMP_PROCESSING_FOLDER", "/tmp/shariaa_temp")
    PDF_PREVIEW_FOLDER = os.environ.get("PDF_PREVIEW_FOLDER", "/tmp/pdf_previews")
    
    # Load prompts from files
    EXTRACTION_PROMPT = _load_prompt('EXTRACTION_PROMPT.txt') or "Extract text accurately in Markdown format."
    SYS_PROMPT = _load_prompt('SYS_PROMPT_SHARIA_ANALYSIS.txt') or "Sharia compliance analyzer"
    INTERACTION_PROMPT = _load_prompt('INTERACTION_PROMPT_SHARIA.txt') or "Expert consultation prompt"
    REVIEW_MODIFICATION_PROMPT = _load_prompt('REVIEW_MODIFICATION_PROMPT_SHARIA.txt') or "Review modifications"
    CONTRACT_REGENERATION_PROMPT = _load_prompt('CONTRACT_REGENERATION_PROMPT.txt') or "Regenerate contract"
    
    SYS_PROMPT_SHARIA = SYS_PROMPT
    INTERACTION_PROMPT_SHARIA = INTERACTION_PROMPT
    REVIEW_MODIFICATION_PROMPT_SHARIA = REVIEW_MODIFICATION_PROMPT
