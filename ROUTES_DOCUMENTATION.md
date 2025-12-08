# API Routes Documentation

This document provides detailed documentation for all API endpoints in the application.

## Base URL
The application runs on port 5000 by default.
Base URL: `http://localhost:5000`

## Analysis Routes
**Blueprint**: `analysis_bp`
**Prefix**: None (Root)

### `POST /analyze`
Upload and analyze a contract file.
- **Content-Type**: `multipart/form-data`
- **Parameters**:
    - `file`: The contract file (DOCX, PDF, TXT).
- **Response**: JSON containing analysis results, session ID, and original file URL.

### `GET /sessions`
List recent analysis sessions with pagination.
- **Parameters**:
    - `page`: Page number (default: 1).
    - `limit`: Items per page (default: 10).
- **Response**: JSON list of sessions and pagination info.

### `GET /history`
Retrieve completed analysis history.
- **Response**: JSON list of completed sessions.

### `GET /analysis/<analysis_id>`
Get detailed analysis results by ID.
- **Response**: JSON containing session info and analyzed terms.

### `GET /session/<session_id>`
Fetch session details including contract info.
- **Response**: JSON session document.

### `GET /terms/<session_id>`
Retrieve all analyzed terms for a specific session.
- **Response**: JSON list of terms.

### `GET /statistics`
Provide system-wide statistics.
- **Response**: JSON containing total sessions, success rate, analysis types, etc.

### `GET /stats/user`
Provide user-specific statistics (currently aggregate).
- **Response**: JSON containing recent sessions and monthly counts.

### `POST /feedback/expert`
Submit expert feedback on an analysis.
- **Content-Type**: `application/json`
- **Body**:
    ```json
    {
        "session_id": "string",
        "expert_name": "string",
        "feedback_text": "string",
        "rating": "number (optional)"
    }
    ```
- **Response**: JSON confirmation.

### `GET /health`
System health check.
- **Response**: JSON status.

## Generation Routes
**Blueprint**: `generation_bp`
**Prefix**: None (Root)

### `POST /generate_from_brief`
Generate a new contract from a text brief.
- **Content-Type**: `application/json`
- **Body**:
    ```json
    {
        "brief": "string",
        "contract_type": "string (optional)",
        "jurisdiction": "string (optional)"
    }
    ```
- **Response**: JSON containing generated contract text.

### `GET /preview_contract/<session_id>/<contract_type>`
Generate a PDF preview URL for a contract.
- **Parameters**:
    - `contract_type`: `modified` or `marked`.
- **Response**: JSON containing PDF URL.

### `GET /download_pdf_preview/<session_id>/<contract_type>`
Download the PDF preview directly.
- **Response**: Binary PDF file.

### `POST /generate_modified_contract`
Generate a modified contract based on confirmed user changes.
- **Content-Type**: `application/json`
- **Body**:
    ```json
    {
        "session_id": "string"
    }
    ```
- **Response**: JSON containing URLs for modified DOCX and TXT files.

### `POST /generate_marked_contract`
Generate a contract with highlighted terms.
- **Content-Type**: `application/json`
- **Body**:
    ```json
    {
        "session_id": "string"
    }
    ```
- **Response**: JSON containing URL for marked DOCX file.

## Interaction Routes
**Blueprint**: `interaction_bp`
**Prefix**: None (Root)

### `POST /interact`
Ask a question about the contract or a specific term.
- **Content-Type**: `application/json`
- **Body**:
    ```json
    {
        "question": "string",
        "term_id": "string (optional)",
        "term_text": "string (optional)",
        "session_id": "string"
    }
    ```
- **Response**: JSON answer from AI.

### `POST /review_modification`
Review a user's proposed modification for Sharia compliance.
- **Content-Type**: `application/json`
- **Body**:
    ```json
    {
        "session_id": "string",
        "term_id": "string",
        "user_modified_text": "string",
        "original_term_text": "string"
    }
    ```
- **Response**: JSON review result.

### `POST /confirm_modification`
Confirm a modification to be included in the final contract.
- **Content-Type**: `application/json`
- **Body**:
    ```json
    {
        "session_id": "string",
        "term_id": "string",
        "modified_text": "string"
    }
    ```
- **Response**: JSON confirmation.

## Admin Routes
**Blueprint**: `admin_bp`
**Prefix**: `/admin`

### `GET /admin/health`
Admin service health check.

### `GET /admin/traces`
List all trace files (Debug mode or Access Key required).

### `GET /admin/traces/<filename>`
Get content of a specific trace file.

### `GET /admin/traces/<filename>/download`
Download a trace file.

### `GET /admin/rules` (Coming Soon)
### `POST /admin/rules` (Coming Soon)
### `PUT /admin/rules/<rule_id>` (Coming Soon)
### `DELETE /admin/rules/<rule_id>` (Coming Soon)

## File Search Routes
**Blueprint**: `file_search_bp`
**Prefix**: None (Root)

### `GET /file_search/health`
File search service health check.

### `GET /file_search/store-info`
Get information about the vector store.

### `POST /file_search/extract_terms`
Extract key terms from a contract text.
- **Body**: `{"contract_text": "..."}`

### `POST /file_search/search`
Search for relevant AAOIFI standards based on contract text.
- **Body**: `{"contract_text": "...", "top_k": 10}`

## API Statistics Routes
**Blueprint**: `api_bp`
**Prefix**: `/api`

### `GET /api/stats/user`
Get user statistics (matches legacy format).

### `GET /api/history`
Get analysis history (matches legacy format).
