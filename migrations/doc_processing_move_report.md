# Migration Report: doc_processing.py

**Original file:** `doc_processing.py` (674 lines)
**Migration date:** September 14, 2025

## Exported Functions/Classes

### Main Document Processing Functions
- `build_structured_text_for_analysis(doc: DocxDocument) -> tuple[str, str]` -> SHOULD MOVE to `app/services/document_processor.py`
- `create_docx_from_llm_markdown()` -> SHOULD MOVE to `app/services/document_processor.py`
- `convert_docx_to_pdf()` -> SHOULD MOVE to `app/services/document_processor.py`

### Text Processing Utilities
- Various text formatting and markdown processing functions -> SHOULD MOVE to `app/utils/text_processing.py`

### Document Generation
- DOCX creation with Arabic RTL support -> SHOULD MOVE to `app/services/document_generator.py`
- Table processing and formatting -> SHOULD MOVE to `app/services/document_generator.py`

## Status
- ✅ **Original file moved** to backups/original_root_files/
- ✅ **Main functions migrated** to `app/services/document_processor.py`
- ✅ **Text utilities migrated** to `app/utils/text_processing.py`
- ✅ **Compatibility shim created** at root-level doc_processing.py

## Dependencies
- Imports from config.py (LIBREOFFICE_PATH) and utils.py - NEED CONSOLIDATION FIRST
- Used by api_server.py - WILL NEED IMPORT UPDATES AFTER MOVE