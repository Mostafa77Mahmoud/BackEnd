"""
File handling utilities for the Shariaa Contract Analyzer.
Consolidated from original utils.py and api_server.py
"""

import os
import uuid
import re
import traceback
import tempfile
import requests
from unidecode import unidecode

def ensure_dir(dir_path: str):
    """Ensures that a directory exists, creating it if necessary."""
    try:
        os.makedirs(dir_path, exist_ok=True)
    except OSError as e:
        print(f"ERROR: Could not create directory '{dir_path}': {e}")
        traceback.print_exc()
        raise

def clean_filename(filename: str) -> str:
    """
    Cleans a filename by removing potentially problematic characters and
    ensuring it's a valid name for most filesystems.
    Uses unidecode for broader character support before basic sanitization.
    """
    if not filename:
        return f"contract_{uuid.uuid4().hex[:8]}"

    # Transliterate Unicode characters to ASCII equivalents
    ascii_filename = unidecode(filename)
    
    # Replace spaces with underscores
    safe_filename = ascii_filename.replace(" ", "_")
    
    # Remove any character that is not a word character, whitespace (though spaces are gone), a hyphen, or a period.
    safe_filename = re.sub(r'[^\w\s.-]', '', safe_filename).strip()

    # If the cleaning results in an empty filename, generate a unique one.
    if not safe_filename:
        return f"contract_{uuid.uuid4().hex[:8]}"

    # Truncate to a maximum length to avoid issues with filesystem limits.
    # Ensure extension is preserved if possible.
    max_len = 200 
    if len(safe_filename) > max_len:
        name, ext = os.path.splitext(safe_filename)
        # Truncate the name part, then append extension
        safe_filename = name[:max_len - len(ext) -1] + ext # -1 for the dot
    return safe_filename

def download_file_from_url(file_url: str, suggested_filename: str, destination_folder: str) -> str | None:
    """Downloads a file from URL to local destination folder. Returns local file path or None."""
    try:
        response = requests.get(file_url, stream=True, timeout=30)
        response.raise_for_status()
        
        ensure_dir(destination_folder)
        local_file_path = os.path.join(destination_folder, clean_filename(suggested_filename))
        
        with open(local_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return local_file_path
    except Exception as e:
        print(f"Error downloading file from {file_url}: {e}")
        return None