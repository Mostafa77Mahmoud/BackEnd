"""
Default Configuration

Configuration settings for the Shariaa Contract Analyzer.
"""

import os

class DefaultConfig:
    """Default configuration settings."""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
    DEBUG = False  # Secure default
    
    @classmethod
    def validate_config(cls):
        """Validate required configuration values."""
        if not cls.SECRET_KEY:
            raise ValueError("FLASK_SECRET_KEY environment variable is required")
    
    # AI Service Configuration
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    GEMINI_FILE_SEARCH_API_KEY = os.environ.get("GEMINI_FILE_SEARCH_API_KEY") # Dedicated key for file search
    MODEL_NAME = "gemini-2.5-flash"
    TEMPERATURE = 0
    
    # File Search Configuration
    FILE_SEARCH_STORE_ID = os.environ.get("FILE_SEARCH_STORE_ID")
    TOP_K_CHUNKS = int(os.environ.get("TOP_K_CHUNKS", "10"))
    
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
    LIBREOFFICE_PATH = os.environ.get("LIBREOFFICE_PATH", "libreoffice")  # System-wide LibreOffice installation
    
    # Default Jurisdiction
    DEFAULT_JURISDICTION = "Egypt"
    
    # AI Prompts (read from prompts/ directory)
    @classmethod
    def load_prompt(cls, filename):
        """Load a prompt from the prompts directory."""
        try:
            prompt_path = os.path.join('prompts', filename)
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            return f"ERROR: Prompt file {filename} not found"
    
    @property
    def EXTRACTION_PROMPT(self):
        """Load extraction prompt from file."""
        return self.load_prompt('EXTRACTION_PROMPT.txt')
    
    @property
    def SYS_PROMPT_SHARIA(self):
        """Load Sharia analysis prompt from file."""
        return self.load_prompt('SYS_PROMPT_SHARIA_ANALYSIS.txt')
    
    # @property
    # def SYS_PROMPT_LEGAL(self):
    #     """Load Legal analysis prompt from file."""
    #     return self.load_prompt('SYS_PROMPT_LEGAL_ANALYSIS.txt')
    
    @property
    def INTERACTION_PROMPT_SHARIA(self):
        """Load Sharia interaction prompt from file."""
        return self.load_prompt('INTERACTION_PROMPT_SHARIA.txt')
    
    @property
    def REVIEW_MODIFICATION_PROMPT_SHARIA(self):
        """Load Sharia review modification prompt from file."""
        return self.load_prompt('REVIEW_MODIFICATION_PROMPT_SHARIA.txt')
    
    @property
    def CONTRACT_REGENERATION_PROMPT(self):
        """Load contract regeneration prompt from file."""
        return self.load_prompt('CONTRACT_REGENERATION_PROMPT.txt')
    
    @property
    def CONTRACT_GENERATION_PROMPT(self):
        """Load contract generation prompt from file."""
        return self.load_prompt('CONTRACT_GENERATION_PROMPT.txt')
    
    # @property
    # def INTERACTION_PROMPT_LEGAL(self):
    #     """Load Legal interaction prompt from file."""
    #     return self.load_prompt('INTERACTION_PROMPT_LEGAL.txt')
    
    # @property
    # def REVIEW_MODIFICATION_PROMPT_LEGAL(self):
    #     """Load Legal review modification prompt from file."""
    #     return self.load_prompt('REVIEW_MODIFICATION_PROMPT_LEGAL.txt')

    @property
    def EXTRACT_KEY_TERMS_PROMPT(self):
        """Load extract key terms prompt from file."""
        return self.load_prompt('EXTRACT_KEY_TERMS_PROMPT.txt')

    @property
    def FILE_SEARCH_PROMPT(self):
        """Load file search prompt from file."""
        return self.load_prompt('FILE_SEARCH_PROMPT.txt')