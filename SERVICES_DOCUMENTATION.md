# Backend Services Documentation

This document provides detailed documentation for the core services used in the application.

## AI Service (`app/services/ai_service.py`)
**Purpose**: Manages all interactions with the Google Generative AI (Gemini) API.

### Key Functions
- **`init_ai_service(app)`**: Initializes the AI service with the API key from the app configuration.
- **`get_client()`**: Returns the configured GenAI client.
- **`get_chat_session(session_id_key)`**: Retrieves or creates a chat session for a specific user/session ID.
- **`send_text_to_remote_api(text_payload, session_id_key, formatted_system_prompt)`**: Sends a text prompt to the AI model and returns the response. Handles retries and error logging.
- **`extract_text_from_file(file_path)`**: Uses the AI model to extract text content from PDF or TXT files.
- **`send_file_to_remote_api(file_path, mime_type)`**: Uploads a file to the GenAI API for processing.

## Cloudinary Service (`app/services/cloudinary_service.py`)
**Purpose**: Handles file storage and management using Cloudinary.

### Key Functions
- **`init_cloudinary(app)`**: Initializes the Cloudinary configuration.
- **`upload_to_cloudinary_helper(local_file_path, cloudinary_folder, resource_type, ...)`**: Uploads a local file to a specified Cloudinary folder. Returns the upload result including the secure URL.
    - Supports PDF previews with public access.
    - Generates unique public IDs.

## Database Service (`app/services/database.py`)
**Purpose**: Manages MongoDB connections and provides access to collections.

### Key Functions
- **`init_db(app)`**: Connects to the MongoDB database using the URI from the configuration.
- **`get_contracts_collection()`**: Returns the `contracts` collection object.
- **`get_terms_collection()`**: Returns the `terms` collection object.
- **`get_expert_feedback_collection()`**: Returns the `expert_feedback` collection object.

## Document Processor (`app/services/document_processor.py`)
**Purpose**: Handles the creation, manipulation, and conversion of document files (DOCX, PDF).

### Key Functions
- **`build_structured_text_for_analysis(doc)`**: Extracts text from a DOCX file, preserving formatting (bold, italic, underline) and structure (tables), and assigns IDs to paragraphs for analysis.
- **`create_docx_from_llm_markdown(original_markdown_text, output_path, ...)`**: Generates a professional DOCX file from markdown text.
    - Supports Arabic (RTL) and English (LTR) layouts.
    - Applies formatting (bold, italic, headers).
    - Highlights terms based on compliance status (Red/Green).
    - Adds signature and witness tables.
- **`convert_docx_to_pdf(docx_path, output_folder)`**: Converts a DOCX file to PDF using LibreOffice (headless mode).

## File Search Service (`app/services/file_search.py`)
**Purpose**: Implements a RAG (Retrieval-Augmented Generation) pipeline using Google Gemini's File Search API to retrieve relevant AAOIFI standards.

### Key Functions
- **`initialize_store()`**: Creates or connects to a Gemini File Search Store and uploads context files (AAOIFI standards).
- **`extract_key_terms(contract_text)`**: Uses the AI model to extract key legal/Sharia terms from the contract text.
- **`search_chunks(contract_text, top_k)`**: Performs a two-step search:
    1.  **General Search**: Searches for relevant standards based on the extracted terms/contract summary.
    2.  **Sensitive Search**: Filters for "sensitive" clauses (e.g., Riba, Gharar) and performs a targeted search for those specific issues.
    - Merges and returns unique chunks from both searches.
- **`get_store_info()`**: Returns the status of the File Search Store.
