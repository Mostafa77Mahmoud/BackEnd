# Migration Report: utils.py

**Original file:** `utils.py` (231 lines)
**Migration date:** September 14, 2025

## Exported Functions/Classes

### Directory and File Utilities
- `ensure_dir(dir_path: str)` -> SHOULD MOVE to `app/utils/file_helpers.py`
- `clean_filename(filename: str) -> str` -> SHOULD MOVE to `app/utils/file_helpers.py`

### Text Processing Utilities  
- `clean_model_response(response_text: str) -> str` -> SHOULD MOVE to `app/utils/text_processing.py`

### Cloud Storage Utilities
- `download_file_from_url()` -> SHOULD MOVE to `app/utils/file_helpers.py`
- `upload_to_cloudinary_helper()` -> SHOULD MOVE to `app/services/cloudinary_service.py`

## Status
- ✅ **Original file moved** to backups/original_root_files/
- ✅ **File operations migrated** to `app/utils/file_helpers.py`
- ✅ **Text utilities migrated** to `app/utils/text_processing.py` 
- ✅ **Cloud functions migrated** to `app/services/cloudinary_service.py`
- ✅ **Compatibility shim created** at root-level utils.py

## Dependencies
- No external dependencies from other root files
- Used by api_server.py, doc_processing.py - WILL NEED IMPORT UPDATES AFTER MOVE