"""
File handling utilities for the Shariaa Contract Analyzer.
Matches OldStrcturePerfectProject/utils.py exactly.
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

    ascii_filename = unidecode(filename)
    
    safe_filename = ascii_filename.replace(" ", "_")
    
    safe_filename = re.sub(r'[^\w\s.-]', '', safe_filename).strip()

    if not safe_filename:
        return f"contract_{uuid.uuid4().hex[:8]}"

    max_len = 200 
    if len(safe_filename) > max_len:
        name, ext = os.path.splitext(safe_filename)
        safe_filename = name[:max_len - len(ext) - 1] + ext
    return safe_filename


def download_file_from_url(url, original_filename_for_suffix, temp_processing_folder):
    """
    Downloads a file from a URL to a temporary location.
    Matches OldStrcturePerfectProject/utils.py download_file_from_url exactly.
    """
    temp_file_path = None
    try:
        print(f"Attempting to download from URL: {url}")
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()
        
        file_extension = os.path.splitext(original_filename_for_suffix)[1] or '.tmp'
        
        ensure_dir(temp_processing_folder)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension, dir=temp_processing_folder, mode='wb') as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            temp_file_path = tmp_file.name
        print(f"File successfully downloaded to temporary path: {temp_file_path}")
        return temp_file_path
    except requests.exceptions.RequestException as e:
        print(f"ERROR downloading {url}: {e}")
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"ERROR during download of {url}: {e}")
        traceback.print_exc()
        return None
