"""
Cloudinary Service

Cloud storage management for the Shariaa Contract Analyzer.
"""

import logging
import cloudinary
import cloudinary.uploader
import cloudinary.api

logger = logging.getLogger(__name__)


def init_cloudinary(app):
    """Initialize Cloudinary configuration."""
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