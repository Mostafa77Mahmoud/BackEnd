# Analysis.py Split Plan

## Overview
Split `app/routes/analysis.py` (862 lines) into 5 focused modules based on functional responsibility.

## Proposed File Structure

### 1. `app/routes/analysis_upload.py` (~300 lines)
**Responsibility**: File upload and main analysis entry point
- `POST /api/analyze` - analyze_contract() (lines 32-323)
- Contains the main contract analysis workflow including file handling, text extraction, and AI analysis

### 2. `app/routes/analysis_terms.py` (~150 lines)  
**Responsibility**: Term-related endpoints and session data
- `GET /api/analysis/<analysis_id>` - get_analysis_results() (lines 325-383)
- `GET /api/session/<session_id>` - get_session_details() (lines 385-423)
- `GET /api/terms/<session_id>` - get_session_terms() (lines 425-456)

### 3. `app/routes/analysis_session.py` (~100 lines)
**Responsibility**: Session management and history
- `GET /api/sessions` - get_sessions() (lines 458-490)
- `GET /api/history` - get_analysis_history() (lines 492-524)

### 4. `app/routes/analysis_admin.py` (~120 lines)
**Responsibility**: Administrative endpoints and statistics
- `GET /api/statistics` - get_statistics() (lines 526-569)
- `GET /api/stats/user` - get_user_stats() (lines 571-614)
- `POST /api/feedback/expert` - submit_expert_feedback() (lines 777-855)
- `GET /api/health` - health_check() (lines 857-862)

### 5. `app/routes/analysis_generation.py` (~200 lines)
**Responsibility**: Contract generation and PDF handling
- `GET /api/preview_contract/<session_id>/<contract_type>` - preview_contract() (lines 616-711)
- `GET /api/download_pdf_preview/<session_id>/<contract_type>` - download_pdf_preview() (lines 713-775)

## Common Utilities to Extract

### `app/utils/analysis_helpers.py`
- File processing utilities
- Text normalization functions
- Common error handling patterns
- Database query helpers
- Cloudinary upload wrappers

## Blueprint Management

### `app/routes/__init__.py`
- Import all analysis modules
- Ensure single `analysis_bp` blueprint is registered
- Maintain `url_prefix='/api'` behavior

## Migration Strategy
1. Create new files with appropriate imports
2. Move functions preserving docstrings and decorators
3. Extract common helpers to utils
4. Update imports and fix circular dependencies
5. Test all endpoints maintain exact same behavior

## Validation Criteria
- All 12 endpoints remain accessible at same URLs
- No behavioral changes to request/response handling
- All docstrings preserved
- Import dependencies resolved
- Tests pass without modification