# Sharia Contract Analyzer Backend

## Overview

Flask-based backend system for analyzing legal contracts for Sharia (Islamic law) compliance following AAOIFI standards. Uses Google Gemini 2.0 Flash for AI-powered analysis.

## Key Features

- Multi-format contract processing (DOCX, PDF, TXT)
- AI-powered Sharia compliance analysis
- Interactive user consultation with Q&A
- Expert review system integration
- Contract modification and regeneration
- Cloud document management (Cloudinary)
- Arabic and English language support

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | Flask |
| Database | MongoDB Atlas |
| AI | Google Gemini 2.0 Flash |
| Storage | Cloudinary |
| Documents | python-docx, LibreOffice |

## Project Structure

```
app/
  __init__.py              # Flask app factory
  routes/                  # API endpoints
    analysis_upload.py     # Contract upload and analysis
    interaction.py         # Q&A and modifications
    generation.py          # Contract generation
    analysis_session.py    # Session management
    analysis_terms.py      # Terms handling
    analysis_admin.py      # Admin and statistics
    file_search.py         # AAOIFI search
  services/
    ai_service.py          # Google Gemini integration
    database.py            # MongoDB operations
    file_search.py         # AAOIFI standards search
    cloudinary_service.py  # File storage
    document_processor.py  # DOCX/PDF processing
  utils/
    file_helpers.py        # File utilities
config/
  default.py               # Configuration and prompts
prompts/                   # AI system prompts
context/                   # AAOIFI standards documents
```

## API Endpoints (No /api prefix)

### Analysis
- `POST /analyze` - Upload and analyze contracts
- `GET /session/<session_id>` - Get session details
- `GET /terms/<session_id>` - Get analyzed terms
- `GET /sessions` - List all sessions
- `GET /history` - Analysis history

### Interaction
- `POST /interact` - Interactive Q&A consultation
- `POST /review_modification` - Review user modifications
- `POST /confirm_modification` - Confirm term changes

### Generation
- `POST /generate_from_brief` - Generate from brief
- `POST /generate_modified_contract` - Generate modified version
- `POST /generate_marked_contract` - Generate with highlights
- `GET /preview_contract/<session_id>/<type>` - Preview
- `GET /download_pdf_preview/<session_id>/<type>` - Download PDF

### Admin
- `GET /statistics` - System statistics
- `GET /stats/user` - User statistics
- `POST /feedback/expert` - Expert feedback
- `GET /health` - Health check

### File Search
- `POST /file_search/search` - Search AAOIFI standards
- `POST /file_search/extract_terms` - Extract terms
- `GET /file_search/health` - Service health

## Environment Variables

**Required Secrets:**
- `GEMINI_API_KEY` - Google Generative AI key
- `MONGODB_URI` - MongoDB connection string
- `CLOUDINARY_URL` - Cloudinary config

**Optional:**
- `FLASK_SECRET_KEY` - Session secret
- `GEMINI_FILE_SEARCH_API_KEY` - Dedicated file search key

## Running

```bash
python run.py
```

Server runs on port 5000.

## Analysis Flow

1. Contract uploaded/text submitted
2. Language detected (Arabic/English)
3. AAOIFI standards searched for relevant context
4. AI analyzes contract with AAOIFI context
5. Terms extracted with compliance status
6. Results stored in MongoDB
7. User can interact, modify, and generate new versions

## Recent Updates

### November 30, 2025 - File Search Service Improvements
- **file_search.py**: Added version checking for google-genai API compatibility
  - `check_file_search_support()` function to detect File Search API availability
  - Graceful degradation when API is not available (older google-genai versions)
  - Enhanced `__init__()` with `file_search_enabled` flag and safe client creation
  - Better error messages in `initialize_store()` when API is unavailable
- **requirements.txt**: Cleaned up duplicates, specified minimum versions (google-genai>=1.50.0)
- **Logging**: Fixed to work in all modes (Debug and Production) - connection status now visible

### November 30, 2025 - Complete Migration from Old Backend
- **document_processor.py**: Complete dict-based fallback with table handling, signature blocks for Arabic/English, convert_docx_to_pdf with 180s timeout and LibreOffice support
- **cloudinary_service.py**: Full upload_to_cloudinary_helper with PDF-specific access_mode="public" and debug logging
- **file_helpers.py**: download_file_from_url with tempfile.NamedTemporaryFile and 120s timeout
- **text_processing.py**: Full JSON extraction with balanced bracket counting, translate_arabic_to_english, generate_safe_public_id
- **generation.py routes**: Added /preview_contract, /download_pdf_preview, enhanced /generate_modified_contract with TXT generation and smart reconstruction, /generate_marked_contract with smart_sort_key
- **config/default.py**: Complete prompts matching old config.py (EXTRACTION_PROMPT, SYS_PROMPT, INTERACTION_PROMPT, REVIEW_MODIFICATION_PROMPT, CONTRACT_REGENERATION_PROMPT)
- All configuration values properly accessed via current_app.config.get()

### Earlier - Backend Realignment
- Fixed AI service to work with new google-genai SDK
- Rewrote /analyze endpoint to match old api_server.py response format
- Added /api/stats/user and /api/history endpoints
- Session cookies properly set on analyze response

## Architecture Notes

The backend uses Flask blueprints pattern:
- analysis_bp: Core analysis endpoints (/analyze, /session, /terms)
- interaction_bp: Q&A and modifications
- generation_bp: Contract generation
- api_bp: Statistics and history (/api/stats/user, /api/history)
- admin_bp: Administrative functions
- file_search_bp: AAOIFI standards search (new feature)

The old working code is preserved in OldStrcturePerfectProject/ for reference.
