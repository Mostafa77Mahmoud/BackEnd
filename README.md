# Sharia Contract Analyzer - Backend

A Flask-based backend system for analyzing legal contracts for compliance with Islamic law (Sharia) principles, following AAOIFI standards.

## Features

- Multi-format contract processing (DOCX, PDF, TXT)
- AI-powered Sharia compliance analysis using Google Gemini 2.0 Flash
- Interactive Q&A consultation
- Expert review system
- Contract modification and regeneration
- Cloud-based document management (Cloudinary)
- Multi-language support (Arabic and English)

## Tech Stack

- **Framework**: Flask
- **Database**: MongoDB Atlas
- **AI**: Google Generative AI (Gemini 2.0 Flash)
- **Storage**: Cloudinary
- **Document Processing**: python-docx, LibreOffice

## API Endpoints

### Analysis
- `POST /analyze` - Upload and analyze contracts
- `GET /session/<session_id>` - Get session details
- `GET /terms/<session_id>` - Get analyzed terms

### Interaction
- `POST /interact` - Interactive Q&A
- `POST /review_modification` - Review modifications
- `POST /confirm_modification` - Confirm changes

### Generation
- `POST /generate_from_brief` - Generate contract from brief
- `POST /generate_modified_contract` - Generate modified contract
- `POST /generate_marked_contract` - Generate highlighted contract

### Admin
- `GET /statistics` - System statistics
- `POST /feedback/expert` - Submit expert feedback
- `GET /health` - Health check

## Environment Variables

Required secrets (set in Replit Secrets):
- `GEMINI_API_KEY` - Google Generative AI API key
- `MONGODB_URI` - MongoDB connection string
- `CLOUDINARY_URL` - Cloudinary configuration

Optional:
- `FLASK_SECRET_KEY` - Flask session secret
- `GEMINI_FILE_SEARCH_API_KEY` - Separate key for file search

## Running the Application

```bash
python run.py
```

The server runs on port 5000.

## Project Structure

```
app/
  __init__.py          # Flask app factory
  routes/              # API endpoints
    analysis_upload.py
    interaction.py
    generation.py
    ...
  services/            # Business logic
    ai_service.py
    database.py
    file_search.py
    ...
  utils/               # Helpers
config/                # Configuration
# Sharia Contract Analyzer - Backend

A Flask-based backend system for analyzing legal contracts for compliance with Islamic law (Sharia) principles, following AAOIFI standards.

## Features

- Multi-format contract processing (DOCX, PDF, TXT)
- AI-powered Sharia compliance analysis using Google Gemini 2.0 Flash
- Interactive Q&A consultation
- Expert review system
- Contract modification and regeneration
- Cloud-based document management (Cloudinary)
- Multi-language support (Arabic and English)

## Tech Stack

- **Framework**: Flask
- **Database**: MongoDB Atlas
- **AI**: Google Generative AI (Gemini 2.0 Flash)
- **Storage**: Cloudinary
- **Document Processing**: python-docx, LibreOffice

## API Endpoints

### Analysis
- `POST /analyze` - Upload and analyze contracts
- `GET /session/<session_id>` - Get session details
- `GET /terms/<session_id>` - Get analyzed terms

### Interaction
- `POST /interact` - Interactive Q&A
- `POST /review_modification` - Review modifications
- `POST /confirm_modification` - Confirm changes

### Generation
- `POST /generate_from_brief` - Generate contract from brief
- `POST /generate_modified_contract` - Generate modified contract
- `POST /generate_marked_contract` - Generate highlighted contract

### Admin
- `GET /statistics` - System statistics
- `POST /feedback/expert` - Submit expert feedback
- `GET /health` - Health check

## Environment Variables

Required secrets (set in Replit Secrets):
- `GEMINI_API_KEY` - Google Generative AI API key
- `MONGODB_URI` - MongoDB connection string
- `CLOUDINARY_URL` - Cloudinary configuration

Optional:
- `FLASK_SECRET_KEY` - Flask session secret
- `GEMINI_FILE_SEARCH_API_KEY` - Separate key for file search

## Running the Application

```bash
python run.py
```

The server runs on port 5000.

## Project Structure

```
app/
  __init__.py          # Flask app factory
  routes/              # API endpoints
    analysis_upload.py
    interaction.py
    generation.py
    ...
  services/            # Business logic
    ai_service.py
    database.py
    file_search.py
    ...
  utils/               # Helpers
config/                # Configuration
prompts/               # AI prompts
context/               # AAOIFI standards
```

## Documentation

- **[Backend Documentation](BACKEND_DOCUMENTATION.md)**: System overview and architecture.
- **[API Routes](ROUTES_DOCUMENTATION.md)**: Detailed API endpoint reference.
- **[Services](SERVICES_DOCUMENTATION.md)**: Core services documentation.
- `DATA_FLOW.md` - System data flow diagrams
- `TECHNICAL_DIAGRAMS.md` - Architecture diagrams
- `GITHUB.md` - Git commands reference
