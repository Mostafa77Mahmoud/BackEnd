# Migration Report: api_server.py

**Original file:** `api_server.py` (1,312 lines)
**Migration date:** September 14, 2025

## Exported Functions/Classes/Routes

### Main Application
- **Flask app initialization** -> MOVED to `app/__init__.py:create_app()`
- **CORS configuration** -> MOVED to `app/__init__.py:create_app()`

### API Routes (need to be moved to appropriate app/routes/ files)
- `@app.route("/analyze", methods=["POST"])` -> NEEDS MOVE to `app/routes/analysis.py`
- `@app.route("/preview_contract/<session_id>/<contract_type>", methods=["GET"])` -> NEEDS MOVE to `app/routes/generation.py`
- `@app.route("/download_pdf_preview/<session_id>/<contract_type>", methods=["GET"])` -> NEEDS MOVE to `app/routes/generation.py`
- Additional routes identified from full file scan (need complete migration)

### Utility Functions
- `translate_arabic_to_english()` -> SHOULD MOVE to `app/utils/text_processing.py`
- `generate_safe_public_id()` -> SHOULD MOVE to `app/utils/file_helpers.py`

### Database Connections
- **MongoDB connection logic** -> ALREADY EXISTS in `app/services/database.py`
- **Collection references** -> ALREADY EXISTS in `app/services/database.py`

### Configuration
- **Cloudinary configuration** -> SHOULD MOVE to `app/services/cloudinary_service.py`
- **Temporary directories setup** -> SHOULD MOVE to `app/utils/file_helpers.py`

## Status
- ✅ **Original file moved** to backups/original_root_files/
- 🔄 **Utility functions migrated** to app/utils/ modules 
- ✅ **Database setup already migrated** to app/services/database.py
- 🔄 **Routes still need individual migration** to appropriate app/routes/ blueprints
- ✅ **Compatibility shim available** via existing imports (Flask app runs successfully)

## Dependencies
- Imports from config.py, remote_api.py, doc_processing.py, utils.py - ALL NEED CONSOLIDATION FIRST