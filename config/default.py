"""
Default Configuration

Configuration settings for the Shariaa Contract Analyzer.
"""

import os

class DefaultConfig:
    """Default configuration settings."""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
    DEBUG = True
    
    @classmethod
    def validate_config(cls):
        """Validate required configuration values."""
        if not cls.SECRET_KEY:
            raise ValueError("FLASK_SECRET_KEY environment variable is required")
    
    # AI Service Configuration
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    MODEL_NAME = "gemini-2.5-flash"
    TEMPERATURE = 0
    
    # Database Configuration
    MONGO_URI = os.environ.get("MONGO_URI")
    
    # Cloud Storage Configuration
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")
    CLOUDINARY_BASE_FOLDER = "shariaa_analyzer_uploads"
    
    # Cloudinary Subfolder Structure
    CLOUDINARY_UPLOAD_FOLDER = "contract_uploads"
    CLOUDINARY_ORIGINAL_UPLOADS_SUBFOLDER = "original_contracts"
    CLOUDINARY_ANALYSIS_RESULTS_SUBFOLDER = "analysis_results_json"
    CLOUDINARY_MODIFIED_CONTRACTS_SUBFOLDER = "modified_contracts"
    CLOUDINARY_MARKED_CONTRACTS_SUBFOLDER = "marked_contracts"
    CLOUDINARY_PDF_PREVIEWS_SUBFOLDER = "pdf_previews"
    
    # External Tools
    LIBREOFFICE_PATH = "libreoffice"  # System-wide LibreOffice installation
    
    # Default Jurisdiction
    DEFAULT_JURISDICTION = "Egypt"