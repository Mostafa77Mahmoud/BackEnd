# backend/utils.py
import os
import uuid
import re
import traceback
from unidecode import unidecode # For clean_filename
import tempfile # Added for download_file_from_url

# --- Directory and File Utilities ---
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

# --- Text Processing Utilities ---
def clean_model_response(response_text: str | None) -> str:
    """
    Cleans the response text from the model, attempting to extract JSON
    content if it's wrapped in markdown code blocks or found directly.
    For contract text, removes unwanted analysis and commentary.
    """
    if not isinstance(response_text, str):
        return ""

    # Try to find JSON within ```json ... ```
    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
    if json_match:
        return json_match.group(1).strip()

    # Try to find JSON within ``` ... ``` (generic code block)
    code_match = re.search(r"```\s*([\s\S]*?)\s*```", response_text, re.DOTALL)
    if code_match:
        content = code_match.group(1).strip()
        # Check if the content looks like a JSON object or array
        if (content.startswith('{') and content.endswith('}')) or \
           (content.startswith('[') and content.endswith(']')):
            return content

    # If no markdown blocks, try to find the first occurrence of '{' or '['
    # and extract up to the matching '}' or ']'
    first_bracket = response_text.find("[")
    first_curly = response_text.find("{")

    start_index = -1
    end_char = None

    # Determine if an array or object starts first
    if first_bracket != -1 and (first_curly == -1 or first_bracket < first_curly):
        start_index = first_bracket
        end_char = "]"
    elif first_curly != -1:
        start_index = first_curly
        end_char = "}"

    if start_index != -1 and end_char:
        open_braces = 0
        last_index = -1
        for i in range(start_index, len(response_text)):
            if response_text[i] == ('[' if end_char == ']' else '{'):
                open_braces += 1
            elif response_text[i] == end_char:
                open_braces -= 1
                if open_braces == 0:
                    last_index = i
                    break
        
        if last_index > start_index:
            potential_json = response_text[start_index : last_index + 1].strip()
            # Validate if it's actual JSON before returning
            try:
                import json # Local import to keep utils self-contained for this function
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                # Not valid JSON, so proceed to return the stripped original (or part of it)
                pass 

    # For contract text, clean unwanted analysis and commentary
    cleaned_text = response_text.strip()
    
    # Remove markdown code blocks
    cleaned_text = re.sub(r'^```.*?\n', '', cleaned_text, flags=re.MULTILINE)
    cleaned_text = re.sub(r'\n```$', '', cleaned_text)
    
    # Remove analysis lines and commentary
    lines = cleaned_text.split('\n')
    contract_lines = []
    
    for line in lines:
        line = line.strip()
        # Skip empty lines and analysis/commentary
        if not line:
            contract_lines.append('')
            continue
            
        # Skip lines that appear to be analysis or commentary
        if any(keyword in line.lower() for keyword in [
            'تحليل:', 'ملاحظة:', 'تعليق:', 'analysis:', 'note:', 'comment:',
            'يجب ملاحظة', 'من المهم', 'ينبغي الانتباه', 'it should be noted',
            'it is important', 'please note', 'النتيجة:', 'result:', 'الخلاصة:'
        ]):
            continue
            
        # Skip lines that look like instructions or metadata
        if line.startswith(('تعليمات:', 'instructions:', 'metadata:', 'معلومات:')):
            continue
            
        contract_lines.append(line)
    
    # If all else fails, return the cleaned text
    return '\n'.join(contract_lines).strip()


# --- Cloudinary/Network Utilities ---
# Note: These were previously in api_server.py. Moved here for better organization.
# Ensure 'requests' and 'cloudinary' are available in the environment where this utils.py is used.
import requests # Requires 'requests' to be installed
import cloudinary # Requires 'cloudinary' to be installed
import cloudinary.uploader
import cloudinary.api

def download_file_from_url(url, original_filename_for_suffix, temp_processing_folder):
    """Downloads a file from a URL to a temporary location."""
    temp_file_path = None
    try:
        print(f"Attempting to download from URL: {url}")
        response = requests.get(url, stream=True, timeout=120) # Increased timeout
        response.raise_for_status() # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
        
        # Determine file extension
        file_extension = os.path.splitext(original_filename_for_suffix)[1] or '.tmp'
        
        # Create a temporary file in the specified folder
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension, dir=temp_processing_folder, mode='wb') as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            temp_file_path = tmp_file.name
        print(f"File successfully downloaded to temporary path: {temp_file_path}")
        return temp_file_path
    except requests.exceptions.RequestException as e: # More specific exception
        print(f"ERROR downloading {url}: {e}")
        traceback.print_exc()
        return None
    except Exception as e: # Catch other potential errors
        print(f"ERROR during download of {url}: {e}")
        traceback.print_exc()
        return None


def upload_to_cloudinary_helper(local_file_path: str, cloudinary_folder: str, resource_type: str = "auto", public_id_prefix: str = "", custom_public_id: str = None):
    """Uploads a local file to Cloudinary."""
    try:
        if not isinstance(local_file_path, str):
            raise TypeError(f"upload_to_cloudinary_helper expects a string file path, got {type(local_file_path)}")

        # Use custom public_id if provided, otherwise generate one
        if custom_public_id:
            public_id = custom_public_id
        else:
            filename = os.path.basename(local_file_path)
            base_name = filename.rsplit('.', 1)[0]
            public_id_suffix = clean_filename(base_name) # Use cleaned filename for public ID
            # Construct a more unique, and guaranteed short, public_id
            public_id = f"{public_id_prefix}_{uuid.uuid4().hex}"

        upload_options = {
            "folder": cloudinary_folder,
            "public_id": public_id,
            "resource_type": resource_type,
            "overwrite": True # Overwrite if a file with the same public_id exists
        }
        
        # Set access mode for PDF previews for direct linking
        # Assuming CLOUDINARY_PDF_PREVIEWS_SUBFOLDER is part of cloudinary_folder string
        if "pdf_previews" in cloudinary_folder or local_file_path.lower().endswith(".pdf"):
            upload_options["access_mode"] = "public" 
            print(f"Attempting to upload PDF with access_mode: public, resource_type: {resource_type}")

        print(f"DEBUG: Attempting to upload to Cloudinary. File: {local_file_path}, Options: {upload_options}")
        upload_result = cloudinary.uploader.upload(local_file_path, **upload_options)
        print(f"DEBUG: Raw Cloudinary upload_result for {local_file_path}: {upload_result}")
        
        if not upload_result or not upload_result.get("secure_url"):
            print(f"ERROR_DEBUG: Cloudinary upload for {local_file_path} returned problematic result: {upload_result}")
            return None
            
        print(f"Cloudinary upload successful. URL: {upload_result.get('secure_url')}")
        return upload_result
    except cloudinary.exceptions.Error as e: # More specific Cloudinary exception
        print(f"ERROR_DEBUG: Cloudinary API Error during upload for {local_file_path}: {e}")
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"ERROR_DEBUG: Cloudinary upload EXCEPTION for {local_file_path}: {e}")
        traceback.print_exc()
        return None