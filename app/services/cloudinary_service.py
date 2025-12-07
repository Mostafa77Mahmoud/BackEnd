"""
Cloudinary Service

Cloud storage management for the Shariaa Contract Analyzer.
Matches OldStrcturePerfectProject/utils.py upload_to_cloudinary_helper exactly.
"""

import os
import uuid
import time
import logging
import traceback
from app.utils.logging_utils import get_request_tracer

logger = logging.getLogger(__name__)

try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    CLOUDINARY_AVAILABLE = True
except ImportError:
    logger.warning("Cloudinary package not available. File upload features will be limited.")
    CLOUDINARY_AVAILABLE = False


def init_cloudinary(app):
    """Initialize Cloudinary configuration."""
    if not CLOUDINARY_AVAILABLE:
        logger.warning("Cloudinary package not installed - file storage services will be unavailable")
        return
    
    try:
        cloud_name = app.config.get('CLOUDINARY_CLOUD_NAME')
        api_key = app.config.get('CLOUDINARY_API_KEY')
        api_secret = app.config.get('CLOUDINARY_API_SECRET')
        
        if not all([cloud_name, api_key, api_secret]):
            logger.warning("Cloudinary credentials not fully configured - file storage services will be limited")
            return
            
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        logger.info("Cloudinary configured successfully")
    except Exception as e:
        logger.error(f"Cloudinary configuration failed: {e}")
        logger.warning("Cloudinary services will be unavailable")


def upload_to_cloudinary_helper(
    local_file_path: str,
    cloudinary_folder: str,
    resource_type: str = "auto",
    public_id_prefix: str = "",
    custom_public_id: str = None
):
    """
    Uploads a local file to Cloudinary.
    Matches OldStrcturePerfectProject/utils.py upload_to_cloudinary_helper exactly.
    """
    if not CLOUDINARY_AVAILABLE:
        logger.error("Cloudinary not available for upload")
        return None
        
    try:
        if not isinstance(local_file_path, str):
            raise TypeError(f"upload_to_cloudinary_helper expects a string file path, got {type(local_file_path)}")

        from app.utils.file_helpers import clean_filename
        
        if custom_public_id:
            public_id = custom_public_id
        else:
            filename = os.path.basename(local_file_path)
            base_name = filename.rsplit('.', 1)[0]
            public_id_suffix = clean_filename(base_name)
            public_id = f"{public_id_prefix}_{uuid.uuid4().hex}"

        upload_options = {
            "folder": cloudinary_folder,
            "public_id": public_id,
            "resource_type": resource_type,
            "overwrite": True
        }
        
        if "pdf_previews" in cloudinary_folder or local_file_path.lower().endswith(".pdf"):
            upload_options["access_mode"] = "public" 
            logger.info(f"Attempting to upload PDF with access_mode: public, resource_type: {resource_type}")

        logger.debug(f"DEBUG: Attempting to upload to Cloudinary. File: {local_file_path}, Options: {upload_options}")
        
        tracer = get_request_tracer()
        api_start_time = time.time()
        
        upload_result = cloudinary.uploader.upload(local_file_path, **upload_options)
        
        api_duration = time.time() - api_start_time
        
        if tracer:
            tracer.record_api_call(
                service="cloudinary",
                method="upload",
                endpoint="cloudinary.uploader.upload",
                request_data={"file_path": local_file_path, "folder": cloudinary_folder, "resource_type": resource_type},
                response_data={"success": bool(upload_result and upload_result.get("secure_url")), "public_id": upload_result.get("public_id") if upload_result else None},
                duration=api_duration
            )
        
        logger.debug(f"DEBUG: Raw Cloudinary upload_result for {local_file_path}: {upload_result}")
        
        if not upload_result or not upload_result.get("secure_url"):
            logger.error(f"ERROR_DEBUG: Cloudinary upload for {local_file_path} returned problematic result: {upload_result}")
            return None
            
        logger.info(f"Cloudinary upload successful. URL: {upload_result.get('secure_url')}")
        return upload_result
        
    except cloudinary.exceptions.Error as e:
        logger.error(f"ERROR_DEBUG: Cloudinary API Error during upload for {local_file_path}: {e}")
        traceback.print_exc()
        return None
    except Exception as e:
        logger.error(f"ERROR_DEBUG: Cloudinary upload EXCEPTION for {local_file_path}: {e}")
        traceback.print_exc()
        return None
