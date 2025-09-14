
# Shariaa Contract Analyzer Backend Documentation

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Technology Stack](#technology-stack)
4. [Core Components](#core-components)
5. [API Endpoints](#api-endpoints)
6. [Database Schema](#database-schema)
7. [File Processing Pipeline](#file-processing-pipeline)
8. [Configuration Management](#configuration-management)
9. [Error Handling & Logging](#error-handling--logging)
10. [Security Considerations](#security-considerations)
11. [Deployment Architecture](#deployment-architecture)
12. [Performance Optimization](#performance-optimization)
13. [Monitoring & Maintenance](#monitoring--maintenance)

## System Overview

The Shariaa Contract Analyzer is a sophisticated backend system designed to analyze legal contracts for compliance with Islamic law (Sharia) principles, specifically following AAOIFI (Accounting and Auditing Organization for Islamic Financial Institutions) standards. The system leverages advanced AI capabilities through Google's Generative AI models to provide intelligent contract analysis, modification suggestions, and expert review capabilities.

### Key Features

- **Multi-format Contract Processing**: Supports DOCX, PDF, and TXT formats
- **AI-Powered Sharia Compliance Analysis**: Uses Google Gemini 2.0 Flash for intelligent analysis
- **Interactive User Consultation**: Real-time Q&A about contract terms
- **Expert Review System**: Professional expert feedback integration
- **Contract Modification**: Automated generation of compliant contract versions
- **Document Management**: Cloud-based storage with Cloudinary integration
- **Multi-language Support**: Primarily Arabic with English support

## Architecture

### High-Level Architecture Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Client]
        MOBILE[Mobile App]
    end
    
    subgraph "API Gateway"
        FLASK[Flask Server<br/>Port 5000]
    end
    
    subgraph "Core Services"
        AUTH[Authentication<br/>Session Management]
        ANALYZER[Contract Analyzer<br/>Service]
        PROCESSOR[Document Processor]
        GENERATOR[Contract Generator]
    end
    
    subgraph "AI Services"
        GEMINI[Google Gemini AI<br/>Text Analysis]
        EXTRACT[Document Extraction<br/>AI Service]
    end
    
    subgraph "Storage Layer"
        MONGO[(MongoDB Atlas<br/>Contract Data)]
        CLOUDINARY[Cloudinary<br/>File Storage]
        TEMP[Temporary Storage<br/>Local Processing]
    end
    
    subgraph "External Libraries"
        DOCX[python-docx<br/>Document Processing]
        LIBRE[LibreOffice<br/>PDF Conversion]
    end
    
    WEB --> FLASK
    MOBILE --> FLASK
    FLASK --> AUTH
    FLASK --> ANALYZER
    FLASK --> PROCESSOR
    FLASK --> GENERATOR
    
    ANALYZER --> GEMINI
    PROCESSOR --> EXTRACT
    PROCESSOR --> DOCX
    PROCESSOR --> LIBRE
    
    FLASK --> MONGO
    FLASK --> CLOUDINARY
    PROCESSOR --> TEMP
    
    GEMINI --> ANALYZER
    EXTRACT --> PROCESSOR
```

### Data Flow Architecture

```mermaid
sequenceDiagram
    participant Client
    participant Flask
    participant Processor
    participant AI
    participant Storage
    participant Generator
    
    Client->>Flask: Upload Contract
    Flask->>Storage: Store Original File
    Flask->>Processor: Extract Text
    Processor->>AI: Send for Analysis
    AI-->>Processor: Analysis Results
    Processor->>Storage: Store Analysis
    Storage-->>Flask: Confirmation
    Flask-->>Client: Analysis Response
    
    Client->>Flask: Request Modifications
    Flask->>Generator: Generate Modified Contract
    Generator->>Storage: Store Modified Files
    Storage-->>Flask: File URLs
    Flask-->>Client: Download Links
```

## Technology Stack

### Core Framework
- **Flask 2.3+**: Python web framework for RESTful API
- **Python 3.12**: Primary programming language
- **WSGI**: Web Server Gateway Interface

### AI & Machine Learning
- **Google Generative AI**: Gemini 2.0 Flash Thinking model
- **google-generativeai**: Python SDK for Google AI services
- **Temperature Control**: Configurable AI response variability

### Document Processing
- **python-docx**: Microsoft Word document manipulation
- **LibreOffice**: PDF conversion and document processing
- **unidecode**: Unicode transliteration for filename safety
- **langdetect**: Automatic language detection

### Database & Storage
- **MongoDB Atlas**: Primary database for contract and term storage
- **PyMongo**: MongoDB Python driver
- **Cloudinary**: Cloud-based file storage and management
- **Temporary Storage**: Local file system for processing

### Security & Validation
- **Flask-CORS**: Cross-Origin Resource Sharing
- **Werkzeug**: Security utilities and file handling
- **Input Validation**: Custom validation for all endpoints

### Utilities
- **requests**: HTTP client for external API calls
- **pathlib**: Modern path handling
- **traceback**: Error tracking and debugging
- **datetime**: Timezone-aware timestamp management

## Core Components

### 1. API Server (`api_server.py`)

The main Flask application that orchestrates all backend operations.

**Key Responsibilities:**
- HTTP request handling and routing
- Session management and user state
- Integration with external services
- Response formatting and error handling

**Critical Functions:**
```python
@app.route("/analyze", methods=["POST"])
def analyze_file():
    """
    Main contract analysis endpoint
    - Accepts multi-format file uploads
    - Processes documents through AI pipeline
    - Stores results in database
    - Returns structured analysis
    """

@app.route("/generate_modified_contract", methods=["POST"])
def generate_modified_contract():
    """
    Generates modified compliant contracts
    - Applies user-confirmed modifications
    - Creates DOCX and TXT versions
    - Uploads to cloud storage
    """
```

### 2. Document Processing (`doc_processing.py`)

Sophisticated document manipulation and conversion system.

**Core Capabilities:**
- **Text Extraction**: Converts DOCX to structured markdown with ID preservation
- **Document Generation**: Creates professional DOCX files with Arabic RTL support
- **PDF Conversion**: LibreOffice integration for PDF generation
- **Formatting Preservation**: Maintains bold, italic, underline, and table structures

**Processing Pipeline:**
```python
def build_structured_text_for_analysis(doc: DocxDocument) -> tuple[str, str]:
    """
    Extracts text with unique paragraph/table IDs
    Returns: (structured_markdown, plain_text)
    """

def create_docx_from_llm_markdown(
    original_markdown_text: str,
    output_path: str,
    contract_language: str = 'ar',
    terms_for_marking: list[dict] | dict | None = None
):
    """
    Creates professional DOCX with term highlighting
    Supports Arabic RTL layout and color coding
    """
```

### 3. Remote API Integration (`remote_api.py`)

Manages all interactions with Google's Generative AI services.

**Features:**
- **Session Management**: Persistent chat sessions for context
- **File Processing**: Direct AI-based text extraction from PDFs
- **Error Handling**: Robust retry logic and safety filtering
- **Response Cleaning**: Intelligent JSON extraction from AI responses

### 4. Utility Functions (`utils.py`)

Essential helper functions for file operations and data processing.

**Key Utilities:**
- **Filename Sanitization**: Arabic text transliteration and safety
- **Cloud Storage**: Cloudinary upload helpers
- **Response Cleaning**: AI response parsing and validation

## API Endpoints

### Contract Analysis Endpoints

#### POST `/analyze`
**Purpose**: Upload and analyze contracts for Sharia compliance

**Request Format:**
```http
POST /analyze
Content-Type: multipart/form-data

file: [Contract file - DOCX/PDF/TXT]
```

**Response Format:**
```json
{
    "message": "Contract analyzed successfully.",
    "analysis_results": [
        {
            "term_id": "clause_1",
            "term_text": "Contract clause text...",
            "is_valid_sharia": false,
            "sharia_issue": "Interest-based transaction detected",
            "reference_number": "AAOIFI Standard 5",
            "modified_term": "Suggested compliant alternative..."
        }
    ],
    "session_id": "uuid-session-identifier",
    "detected_contract_language": "ar",
    "original_cloudinary_url": "https://cloudinary.com/..."
}
```

#### GET `/terms/<session_id>`
**Purpose**: Retrieve all analyzed terms for a session

**Response Format:**
```json
[
    {
        "_id": "mongodb-object-id",
        "session_id": "session-uuid",
        "term_id": "clause_1",
        "term_text": "Original clause text",
        "is_valid_sharia": false,
        "sharia_issue": "Compliance issue description",
        "modified_term": "Suggested modification",
        "is_confirmed_by_user": true,
        "confirmed_modified_text": "User-approved text"
    }
]
```

### Contract Generation Endpoints

#### POST `/generate_modified_contract`
**Purpose**: Generate compliant contract versions

**Request Format:**
```json
{
    "session_id": "session-uuid"
}
```

**Response Format:**
```json
{
    "success": true,
    "message": "Modified contract generated.",
    "modified_docx_cloudinary_url": "https://cloudinary.com/docx",
    "modified_txt_cloudinary_url": "https://cloudinary.com/txt"
}
```

#### POST `/generate_marked_contract`
**Purpose**: Generate contract with highlighted terms

**Response Format:**
```json
{
    "success": true,
    "message": "Marked contract generated.",
    "marked_docx_cloudinary_url": "https://cloudinary.com/marked.docx"
}
```

### Interactive Consultation Endpoints

#### POST `/interact`
**Purpose**: Real-time Q&A about contract terms

**Request Format:**
```json
{
    "question": "User question about contract",
    "term_id": "clause_1",
    "term_text": "Specific clause text",
    "session_id": "session-uuid"
}
```

**Response**: Plain text response from AI consultant

#### POST `/review_modification`
**Purpose**: Expert review of user modifications

**Request Format:**
```json
{
    "term_id": "clause_1",
    "user_modified_text": "User's proposed changes",
    "original_term_text": "Original clause text",
    "session_id": "session-uuid"
}
```

**Response Format:**
```json
{
    "reviewed_text": "Expert-reviewed text",
    "is_still_valid_sharia": true,
    "new_sharia_issue": null,
    "new_reference_number": null
}
```

### Document Preview Endpoints

#### GET `/preview_contract/<session_id>/<contract_type>`
**Purpose**: Generate PDF previews of contracts

**Parameters:**
- `contract_type`: "modified" or "marked"

**Response Format:**
```json
{
    "pdf_url": "https://cloudinary.com/preview.pdf"
}
```

#### GET `/download_pdf_preview/<session_id>/<contract_type>`
**Purpose**: Direct PDF download proxy

**Response**: Binary PDF stream with appropriate headers

### Expert Feedback System

#### POST `/feedback/expert`
**Purpose**: Submit expert evaluation of AI analysis

**Request Format:**
```json
{
    "session_id": "session-uuid",
    "term_id": "clause_1",
    "feedback_data": {
        "aiAnalysisApproved": false,
        "expertIsValidSharia": true,
        "expertComment": "Expert analysis...",
        "expertCorrectedShariaIssue": "Corrected issue",
        "expertCorrectedReference": "Correct AAOIFI reference",
        "expertCorrectedSuggestion": "Expert suggestion"
    }
}
```

### Statistics and History

#### GET `/api/stats/user`
**Purpose**: User analytics and statistics

**Response Format:**
```json
{
    "totalSessions": 25,
    "totalTerms": 150,
    "complianceRate": 78.5,
    "averageProcessingTime": 15.5
}
```

#### GET `/api/history`
**Purpose**: Complete analysis history with enriched data

**Response**: Array of session objects with calculated metrics

## Database Schema

### MongoDB Collections

#### 1. `contracts` Collection
**Purpose**: Main contract session storage

```javascript
{
    _id: ObjectId | String,
    session_id: String,
    original_filename: String,
    original_cloudinary_info: {
        url: String,
        public_id: String,
        format: String,
        user_facing_filename: String
    },
    analysis_results_cloudinary_info: Object,
    original_format: String, // "docx", "pdf", "txt"
    original_contract_plain: String,
    original_contract_markdown: String,
    generated_markdown_from_docx: String,
    detected_contract_language: String, // "ar" or "en"
    analysis_timestamp: Date,
    confirmed_terms: {
        [term_id]: {
            original_text: String,
            confirmed_text: String
        }
    },
    interactions: [{
        user_question: String,
        term_id: String,
        term_text: String,
        response: String,
        timestamp: Date
    }],
    modified_contract_info: {
        docx_cloudinary_info: Object,
        txt_cloudinary_info: Object,
        generation_timestamp: String
    },
    marked_contract_info: {
        docx_cloudinary_info: Object,
        generation_timestamp: String
    },
    pdf_preview_info: {
        modified: Object,
        marked: Object
    }
}
```

#### 2. `terms` Collection
**Purpose**: Individual term analysis storage

```javascript
{
    _id: ObjectId,
    session_id: String,
    term_id: String,
    term_text: String,
    is_valid_sharia: Boolean,
    sharia_issue: String | null,
    reference_number: String | null,
    modified_term: String | null,
    is_confirmed_by_user: Boolean,
    confirmed_modified_text: String,
    has_expert_feedback: Boolean,
    last_expert_feedback_id: ObjectId,
    expert_override_is_valid_sharia: Boolean
}
```

#### 3. `expert_feedback` Collection
**Purpose**: Expert review and validation

```javascript
{
    _id: ObjectId,
    session_id: String,
    term_id: String,
    original_term_text_snapshot: String,
    expert_user_id: String,
    expert_username: String,
    feedback_timestamp: Date,
    ai_initial_analysis_assessment: {
        is_correct_compliance: Boolean
    },
    expert_verdict_is_valid_sharia: Boolean,
    expert_comment_on_term: String,
    expert_corrected_sharia_issue: String,
    expert_corrected_reference: String,
    expert_final_suggestion_for_term: String,
    // Snapshot of original AI analysis
    original_ai_is_valid_sharia: Boolean,
    original_ai_sharia_issue: String,
    original_ai_modified_term: String,
    original_ai_reference_number: String
}
```

## File Processing Pipeline

### Document Processing Flow

```mermaid
graph TD
    A[File Upload] --> B{File Type?}
    B -->|DOCX| C[Extract with python-docx]
    B -->|PDF| D[AI Text Extraction]
    B -->|TXT| E[Direct Processing]
    
    C --> F[Generate Structured Markdown]
    D --> G[Process Extracted Text]
    E --> G
    
    F --> H[Language Detection]
    G --> H
    
    H --> I[AI Analysis with Gemini]
    I --> J[Parse JSON Results]
    J --> K[Store in Database]
    
    K --> L[Upload to Cloudinary]
    L --> M[Return Analysis Results]
    
    subgraph "Structured Text Generation"
        F --> F1[Preserve Formatting]
        F --> F2[Assign Unique IDs]
        F --> F3[Table Processing]
        F --> F4[Markdown Conversion]
    end
    
    subgraph "AI Processing"
        I --> I1[System Prompt Formatting]
        I --> I2[Safety Settings]
        I --> I3[Response Validation]
        I --> I4[Retry Logic]
    end
```

### Document Generation Pipeline

```mermaid
graph TD
    A[Modification Request] --> B[Retrieve Original Markdown]
    B --> C[Apply Confirmed Changes]
    C --> D[Generate DOCX]
    C --> E[Generate TXT]
    
    D --> F[RTL Language Support]
    F --> G[Professional Styling]
    G --> H[Term Highlighting]
    
    H --> I[Upload to Cloudinary]
    E --> I
    
    I --> J[PDF Conversion]
    J --> K[LibreOffice Processing]
    K --> L[Cloud Storage]
    
    subgraph "DOCX Generation Features"
        G --> G1[Arabic Font Support]
        G --> G2[Proper Alignment]
        G --> G3[Color Coding]
        G --> G4[Signature Blocks]
    end
    
    subgraph "PDF Processing"
        K --> K1[Headless Conversion]
        K --> K2[Error Handling]
        K --> K3[File Validation]
    end
```

## Configuration Management

### Environment Variables

The system uses a centralized configuration approach in `config.py`:

```python
# Cloud Storage Configuration
CLOUDINARY_CLOUD_NAME = "your-cloud-name"
CLOUDINARY_API_KEY = "your-api-key"
CLOUDINARY_API_SECRET = "your-api-secret"
CLOUDINARY_BASE_FOLDER = "shariaa_analyzer_uploads"

# AI Service Configuration
GOOGLE_API_KEY = "your-google-api-key"
MODEL_NAME = "gemini-2.0-flash-thinking-exp-01-21"
TEMPERATURE = 0  # Deterministic responses

# Database Configuration
MONGO_URI = "mongodb+srv://username:password@cluster.mongodb.net/database"

# External Tools
LIBREOFFICE_PATH = "/path/to/libreoffice/soffice"

# Security
FLASK_SECRET_KEY = "your-secret-key"
```

### Cloudinary Folder Structure

```
shariaa_analyzer_uploads/
├── {session_id}/
    ├── original_contracts/
    │   └── original_file.{ext}
    ├── analysis_results_json/
    │   └── analysis_results.json
    ├── modified_contracts/
    │   ├── modified_contract.docx
    │   └── modified_contract.txt
    ├── marked_contracts/
    │   └── marked_contract.docx
    └── pdf_previews/
        ├── modified_preview.pdf
        └── marked_preview.pdf
```

## Error Handling & Logging

### Logging Architecture

The system implements comprehensive logging across all components:

```python
import logging

# Configure centralized logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('shariaa_analyzer.log', encoding='utf-8')
    ]
)
```

### Error Categories

1. **Input Validation Errors**
   - Invalid file formats
   - Missing required parameters
   - Malformed JSON requests

2. **Processing Errors**
   - AI service failures
   - Document conversion issues
   - Database connectivity problems

3. **External Service Errors**
   - Cloudinary upload failures
   - MongoDB connection issues
   - LibreOffice conversion errors

### Error Response Format

```json
{
    "error": "Descriptive error message",
    "error_code": "ERROR_CATEGORY_SPECIFIC",
    "timestamp": "2024-01-15T10:30:00Z",
    "session_id": "uuid-if-available"
}
```

## Security Considerations

### Input Validation

1. **File Upload Security**
   - File type validation
   - Size limitations (16MB max)
   - Secure filename generation
   - Virus scanning considerations

2. **Data Sanitization**
   - SQL injection prevention (MongoDB parameterized queries)
   - XSS prevention in responses
   - Path traversal protection

### Authentication & Authorization

1. **Session Management**
   - Secure session cookies
   - Session timeout implementation
   - CSRF protection considerations

2. **API Security**
   - Rate limiting recommendations
   - Input parameter validation
   - Response data filtering

### Data Protection

1. **Sensitive Data Handling**
   - Contract content encryption at rest
   - Secure temporary file handling
   - Automatic cleanup procedures

2. **Privacy Compliance**
   - Data retention policies
   - User consent tracking
   - Audit trail maintenance

## Performance Optimization

### Caching Strategy

```mermaid
graph LR
    A[Request] --> B{Cache Check}
    B -->|Hit| C[Return Cached Result]
    B -->|Miss| D[Process Request]
    D --> E[Store in Cache]
    E --> F[Return Result]
    
    subgraph "Cache Layers"
        G[Session Cache]
        H[Analysis Results Cache]
        I[Generated Documents Cache]
    end
```

### Database Optimization

1. **Indexing Strategy**
   ```javascript
   // Recommended indexes
   db.contracts.createIndex({ "session_id": 1 })
   db.terms.createIndex({ "session_id": 1, "term_id": 1 })
   db.expert_feedback.createIndex({ "session_id": 1, "term_id": 1 })
   ```

2. **Query Optimization**
   - Efficient aggregation pipelines
   - Projection optimization
   - Connection pooling

### File Processing Optimization

1. **Temporary File Management**
   - Automatic cleanup procedures
   - Memory-efficient streaming
   - Parallel processing capabilities

2. **Cloud Storage Optimization**
   - Optimized upload parameters
   - CDN utilization
   - Bandwidth management

## Deployment Architecture

### Replit Deployment Configuration

```toml
# .replit configuration
modules = ["python-3.12"]
run = "python api_server.py"

[nix]
channel = "stable-25_05"

[deployment]
run = ["sh", "-c", "python api_server.py"]

[workflows]
runButton = "Run Server"

[[workflows.workflow]]
name = "Run Server"
author = 46224424
mode = "sequential"

[[workflows.workflow.tasks]]
task = "shell.exec"
args = "python api_server.py"
```

### Production Considerations

1. **Scalability**
   - Horizontal scaling capabilities
   - Load balancing recommendations
   - Resource monitoring

2. **Availability**
   - Health check endpoints
   - Graceful shutdown procedures
   - Error recovery mechanisms

### Environment Setup

1. **Dependencies Management**
   ```txt
   # Key requirements.txt entries
   Flask>=2.3.0
   pymongo>=4.3.0
   google-generativeai>=0.3.0
   python-docx>=0.8.11
   cloudinary>=1.34.0
   flask-cors>=4.0.0
   ```

2. **System Dependencies**
   - LibreOffice installation
   - Python 3.12+ runtime
   - UTF-8 locale support

## Monitoring & Maintenance

### Health Monitoring

1. **Application Metrics**
   - Request response times
   - Error rates by endpoint
   - Processing queue lengths
   - Memory usage patterns

2. **External Service Monitoring**
   - AI service availability
   - Database connection health
   - Cloud storage accessibility

### Maintenance Procedures

1. **Regular Tasks**
   - Log file rotation
   - Temporary file cleanup
   - Database optimization
   - Security updates

2. **Backup Strategies**
   - Database backup procedures
   - Configuration backup
   - Disaster recovery planning

### Performance Metrics

```mermaid
graph TD
    A[Performance Monitoring] --> B[Response Time Metrics]
    A --> C[Error Rate Tracking]
    A --> D[Resource Utilization]
    
    B --> B1[API Endpoint Times]
    B --> B2[AI Processing Duration]
    B --> B3[Document Generation Speed]
    
    C --> C1[HTTP Error Codes]
    C --> C2[AI Service Failures]
    C --> C3[Database Errors]
    
    D --> D1[Memory Usage]
    D --> D2[CPU Utilization]
    D --> D3[Storage Consumption]
```

## Conclusion

This Shariaa Contract Analyzer backend represents a sophisticated integration of modern web technologies, AI capabilities, and document processing systems. The architecture prioritizes scalability, maintainability, and security while providing comprehensive functionality for Islamic law compliance analysis.

The system's modular design allows for easy extension and modification, while the comprehensive logging and error handling ensure reliable operation in production environments. The integration with cloud services provides scalability and reliability, making it suitable for enterprise-level deployments.

Regular monitoring and maintenance procedures ensure optimal performance and reliability, while the comprehensive API design supports both web and mobile client applications.
