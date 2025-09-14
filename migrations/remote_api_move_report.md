# Migration Report: remote_api.py

**Original file:** `remote_api.py` (217 lines)
**Migration date:** September 14, 2025

## Exported Functions/Classes

### Main AI Integration Functions
- `get_chat_session(session_id_key: str, system_instruction: str, force_new: bool)` -> SHOULD MOVE to `app/services/ai_service.py`
- `send_text_to_remote_api(text_payload: str, session_id_key: str, formatted_system_prompt: str)` -> SHOULD MOVE to `app/services/ai_service.py`
- `extract_text_from_file(file_path: str)` -> SHOULD MOVE to `app/services/ai_service.py`

### Global Variables
- `chat_sessions = {}` -> SHOULD MOVE to `app/services/ai_service.py`

### Configuration/Setup
- Google Generative AI configuration -> SHOULD MOVE to `app/services/ai_service.py:init_ai_service()`

## Status
- ✅ **Original file moved** to backups/original_root_files/
- ✅ **Functions migrated** to `app/services/ai_service.py` with all AI integration functions
- ✅ **Service initialization added** to `app/__init__.py:create_app()`
- ✅ **Compatibility shim created** at root-level remote_api.py

## Dependencies
- Imports from config.py (GOOGLE_API_KEY, MODEL_NAME, etc.) - NEED CONSOLIDATION FIRST  
- Used by api_server.py - WILL NEED IMPORT UPDATES AFTER MOVE