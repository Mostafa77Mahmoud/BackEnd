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

- Fixed AI service function signatures
- Integrated file search for AAOIFI context
- Added language detection for output formatting
- Improved JSON parsing for AI responses
- Created proper .gitignore for security
