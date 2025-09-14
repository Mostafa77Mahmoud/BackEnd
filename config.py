# NOTE: shim — kept for backward compatibility
# Configuration moved to config/default.py and prompts/ directory

import os
from config.default import DefaultConfig

# Re-export environment variables for compatibility
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

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
MODEL_NAME = "gemini-2.5-flash"
TEMPERATURE = 0
MONGO_URI = os.environ.get("MONGO_URI")
LIBREOFFICE_PATH = "libreoffice"
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "your_secret_key_here")

# Load prompts from files
def load_prompt(filename):
    """Load a prompt from the prompts directory."""
    try:
        with open(f'prompts/{filename}', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return f"ERROR: Prompt file {filename} not found"

EXTRACTION_PROMPT = load_prompt('EXTRACTION_PROMPT.txt')
SYS_PROMPT = load_prompt('SYS_PROMPT_SHARIA_ANALYSIS.txt')
INTERACTION_PROMPT = load_prompt('INTERACTION_PROMPT_SHARIA.txt')
REVIEW_MODIFICATION_PROMPT = load_prompt('REVIEW_MODIFICATION_PROMPT_SHARIA.txt')
CONTRACT_REGENERATION_PROMPT = load_prompt('CONTRACT_REGENERATION_PROMPT.txt')