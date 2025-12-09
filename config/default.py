"""
Default Configuration

Configuration settings for the Shariaa Contract Analyzer.
Matches OldStrcturePerfectProject/config.py exactly.
"""

import os
import sys

def _load_prompt_from_file(filename: str, default: str = "") -> str:
    """Load prompt from file in prompts/ directory"""
    try:
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts')
        filepath = os.path.join(prompts_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return content if content else default
        return default
    except Exception as e:
        print(f"Error loading prompt {filename}: {e}", file=sys.stderr)
        return default


class DefaultConfig:
    """Default configuration settings."""
    
    SECRET_KEY: str = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG: bool = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # Note: Do NOT use GOOGLE_API_KEY - it conflicts with google-genai library auto-detection
    # Use only GEMINI_API_KEY for analysis and GEMINI_FILE_SEARCH_API_KEY for file search
    GEMINI_API_KEY: str | None = os.environ.get("GEMINI_API_KEY")
    MODEL_NAME: str = os.environ.get("MODEL_NAME", "gemini-2.5-flash")
    TEMPERATURE: int = int(os.environ.get("TEMPERATURE", "0"))
    
    MONGO_URI: str | None = os.environ.get("MONGO_URI")
    
    CLOUDINARY_CLOUD_NAME: str | None = os.environ.get("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY: str | None = os.environ.get("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET: str | None = os.environ.get("CLOUDINARY_API_SECRET")
    CLOUDINARY_BASE_FOLDER: str = "shariaa_analyzer_uploads"
    
    CLOUDINARY_UPLOAD_FOLDER: str = "contract_uploads"
    CLOUDINARY_ORIGINAL_UPLOADS_SUBFOLDER: str = "original_contracts"
    CLOUDINARY_ANALYSIS_RESULTS_SUBFOLDER: str = "analysis_results_json"
    CLOUDINARY_MODIFIED_CONTRACTS_SUBFOLDER: str = "modified_contracts"
    CLOUDINARY_MARKED_CONTRACTS_SUBFOLDER: str = "marked_contracts"
    CLOUDINARY_PDF_PREVIEWS_SUBFOLDER: str = "pdf_previews"
    
    LIBREOFFICE_PATH: str = os.environ.get("LIBREOFFICE_PATH", "")
    
    TEMP_PROCESSING_FOLDER: str = os.environ.get(
        "TEMP_PROCESSING_FOLDER",
        os.path.join(os.environ.get('TEMP', 'C:\\tmp') if os.name == 'nt' else '/tmp', 'shariaa_temp')
    )
    PDF_PREVIEW_FOLDER: str = os.environ.get(
        "PDF_PREVIEW_FOLDER",
        os.path.join(os.environ.get('TEMP', 'C:\\tmp') if os.name == 'nt' else '/tmp', 'pdf_previews')
    )
    
    GEMINI_FILE_SEARCH_API_KEY: str | None = os.environ.get("GEMINI_FILE_SEARCH_API_KEY")
    FILE_SEARCH_STORE_ID: str | None = os.environ.get("FILE_SEARCH_STORE_ID")
    TOP_K_CHUNKS: int = int(os.environ.get("TOP_K_CHUNKS", "15"))
    TOP_K_SENSITIVE: int = int(os.environ.get("TOP_K_SENSITIVE", "5"))
    
    # === PROMPTS - Loaded from prompts/ directory ===
    
    # Extraction Prompt
    EXTRACTION_PROMPT: str = _load_prompt_from_file(
        'EXTRACTION_PROMPT.txt',
        "Extract text accurately in Markdown format."
    )
    
    # === SHARIA Analysis Prompts ===
    SYS_PROMPT: str = _load_prompt_from_file(
        'SYS_PROMPT_SHARIA_ANALYSIS.txt',
        "Sharia compliance analyzer"
    )
    SYS_PROMPT_SHARIA: str = SYS_PROMPT  # Alias
    
    INTERACTION_PROMPT: str = _load_prompt_from_file(
        'INTERACTION_PROMPT_SHARIA.txt',
        "Expert consultation prompt"
    )
    INTERACTION_PROMPT_SHARIA: str = INTERACTION_PROMPT  # Alias
    
    REVIEW_MODIFICATION_PROMPT: str = _load_prompt_from_file(
        'REVIEW_MODIFICATION_PROMPT_SHARIA.txt',
        "Review modifications"
    )
    REVIEW_MODIFICATION_PROMPT_SHARIA: str = REVIEW_MODIFICATION_PROMPT  # Alias
    
    # === LEGAL Analysis Prompts (for future use) ===
    SYS_PROMPT_LEGAL: str = _load_prompt_from_file(
        'SYS_PROMPT_LEGAL_ANALYSIS.txt',
        "Legal compliance analyzer"
    )
    
    INTERACTION_PROMPT_LEGAL: str = _load_prompt_from_file(
        'INTERACTION_PROMPT_LEGAL.txt',
        "Legal expert consultation prompt"
    )
    
    REVIEW_MODIFICATION_PROMPT_LEGAL: str = _load_prompt_from_file(
        'REVIEW_MODIFICATION_PROMPT_LEGAL.txt',
        "Legal review modifications"
    )
    
    # === Contract Generation Prompts ===
    CONTRACT_REGENERATION_PROMPT: str = _load_prompt_from_file(
        'CONTRACT_REGENERATION_PROMPT.txt',
        "Regenerate contract"
    )
    
    CONTRACT_GENERATION_PROMPT: str = _load_prompt_from_file(
        'CONTRACT_GENERATION_PROMPT.txt',
        "Generate contract from brief"
    )
    
    # === File Search Prompts ===
    EXTRACT_KEY_TERMS_PROMPT: str = _load_prompt_from_file(
        'EXTRACT_KEY_TERMS_PROMPT.txt',
        "Extract key terms from contract"
    )
    
    FILE_SEARCH_PROMPT: str = _load_prompt_from_file(
        'FILE_SEARCH_PROMPT.txt',
        "Search AAOIFI standards"
    )
