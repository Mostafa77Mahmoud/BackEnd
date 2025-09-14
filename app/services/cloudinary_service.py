"""
Cloudinary Service

Cloud storage management for the Shariaa Contract Analyzer.
"""

import logging

logger = logging.getLogger(__name__)

# Import cloudinary with graceful fallback
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
    """Upload a file to Cloudinary with helper options."""
    if not CLOUDINARY_AVAILABLE:
        logger.error("Cloudinary not available for upload")
        return None
        
    try:
        import uuid
        import traceback
        
        upload_options = {
            "folder": cloudinary_folder,
            "resource_type": resource_type,
            "overwrite": True
        }
        
        if custom_public_id:
            upload_options["public_id"] = custom_public_id
        elif public_id_prefix:
            upload_options["public_id"] = f"{public_id_prefix}_{uuid.uuid4().hex[:8]}"
            
        result = cloudinary.uploader.upload(local_file_path, **upload_options)
        
        if result and result.get("secure_url"):
            logger.info(f"File uploaded to Cloudinary: {result['secure_url']}")
            return result
        else:
            logger.error("Cloudinary upload failed - no secure URL returned")
            return None
            
    except Exception as e:
        logger.error(f"Error uploading to Cloudinary: {e}")
        traceback.print_exc()
        return None