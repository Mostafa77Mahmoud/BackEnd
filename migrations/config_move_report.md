# Migration Report: config.py

**Original file:** `config.py` (174 lines)
**Migration date:** September 14, 2025

## Exported Constants/Variables

### Environment Configuration
- `CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET` -> SHOULD MOVE to `config/default.py`
- `CLOUDINARY_BASE_FOLDER, CLOUDINARY_*_SUBFOLDER` -> SHOULD MOVE to `config/default.py`
- `GOOGLE_API_KEY, MODEL_NAME, TEMPERATURE` -> SHOULD MOVE to `config/default.py`
- `MONGO_URI` -> SHOULD MOVE to `config/default.py`
- `LIBREOFFICE_PATH` -> SHOULD MOVE to `config/default.py`
- `FLASK_SECRET_KEY` -> ALREADY EXISTS in `config/default.py`

### AI Prompts (Large text blocks)
- `EXTRACTION_PROMPT` -> SHOULD MOVE to `prompts/EXTRACTION_PROMPT.txt`
- `SYS_PROMPT` -> SHOULD MOVE to `prompts/SYS_PROMPT_SHARIA_ANALYSIS.txt`
- `INTERACTION_PROMPT` -> SHOULD MOVE to `prompts/INTERACTION_PROMPT_SHARIA.txt`
- `REVIEW_MODIFICATION_PROMPT` -> SHOULD MOVE to `prompts/REVIEW_MODIFICATION_PROMPT_SHARIA.txt`
- `CONTRACT_REGENERATION_PROMPT` -> SHOULD MOVE to `prompts/CONTRACT_REGENERATION_PROMPT.txt`

## Status
- ✅ **Original file moved** to backups/original_root_files/
- ✅ **Environment configs consolidated** into config/default.py
- ✅ **Prompts already exist** in prompts/ directory with proper format
- ✅ **Compatibility shim created** at root-level config.py for backward compatibility

## Dependencies
- Used by api_server.py, remote_api.py, doc_processing.py - ALL IMPORT FROM THIS FILE