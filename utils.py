# NOTE: shim — kept for backward compatibility
# All functionality moved to app/utils/

from app.utils.file_helpers import ensure_dir, clean_filename, download_file_from_url
from app.utils.text_processing import clean_model_response
from app.services.cloudinary_service import upload_to_cloudinary_helper

__all__ = [
    'ensure_dir', 'clean_filename', 'clean_model_response', 
    'download_file_from_url', 'upload_to_cloudinary_helper'
]