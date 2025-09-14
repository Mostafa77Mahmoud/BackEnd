"""
Analysis Helper Functions

Common utilities shared across analysis route modules.
"""

import os
import tempfile

# Temporary folder setup
APP_TEMP_BASE_DIR = os.path.join(tempfile.gettempdir(), "shariaa_analyzer_temp")
TEMP_PROCESSING_FOLDER = os.path.join(APP_TEMP_BASE_DIR, "processing_files")

# Ensure directories exist
os.makedirs(TEMP_PROCESSING_FOLDER, exist_ok=True)