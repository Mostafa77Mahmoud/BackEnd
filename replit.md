# Sharia Contract Analyzer Backend

## Overview
The Sharia Contract Analyzer Backend is a Flask-based system designed to analyze legal contracts for compliance with Sharia (Islamic law) principles, specifically following AAOIFI standards. Leveraging Google Gemini 2.0 Flash for AI-powered analysis, the system processes multi-format contracts (DOCX, PDF, TXT), provides interactive user consultation, supports expert review, and facilitates contract modification and regeneration. It integrates cloud document management via Cloudinary and supports both Arabic and English languages. The project aims to provide a robust, AI-driven solution for ensuring Sharia compliance in legal documentation.

## User Preferences
I want iterative development.
Ask before making major changes.
I prefer detailed explanations.
Do not make changes to the folder `Z`.
Do not make changes to the file `Y`.

## System Architecture
The backend is built with Flask, utilizing a blueprint pattern for modularity. Key architectural components and design decisions include:

-   **UI/UX Decisions**: Not specified in detail, but the system supports contract previews and PDF downloads, implying a need for accurate rendering of legal documents.
-   **Technical Implementations**:
    *   **AI Service**: Integration with Google Gemini 2.5 Flash for core Sharia compliance analysis, term extraction, and interactive Q&A. Dedicated API keys are used for general AI and file search functionalities.
    *   **Thinking Mode**: Gemini 2.5+ thinking mode enabled for deep analysis and reasoning. Configurable via `ENABLE_THINKING_MODE`, `THINKING_BUDGET` (default: 4096 tokens), and `INCLUDE_THINKING_SUMMARY` environment variables.
    *   **Chunk Binding Verification**: Comprehensive monitoring ensures AAOIFI chunks from File Search are reliably bound to contract text for analysis. Includes validation reports tracking valid/empty/structured chunks.
    *   **Document Processing**: Handles various formats (DOCX, PDF, TXT) using libraries like `python-docx` and `LibreOffice` for conversions and text extraction. Includes robust text matching and replacement logic for contract modifications, handling formatting differences and preserving structural markers.
    *   **Cloud Storage**: Cloudinary is used for storing and managing uploaded documents, with specific configurations for PDF access.
    *   **Database**: MongoDB Atlas serves as the primary database for storing analysis results, session details, extracted terms, and expert feedback.
    *   **Configuration**: Prompts and system configurations are managed centrally in `config/default.py`, ensuring consistent AI behavior.
    *   **Modular API Endpoints**: Organized into blueprints for `analysis`, `interaction`, `generation`, `admin`, and `file_search` to ensure a clear separation of concerns.
    *   **Performance Optimization**: Implements `OptimizedTextMatcher` for efficient searching and replacement within documents, significantly reducing processing times for marked contract generation. Includes retry mechanisms with exponential backoff for external service calls (e.g., file search) to enhance reliability.
    *   **Expert Feedback System**: A dedicated `expert_feedback` MongoDB collection stores comprehensive expert reviews, allowing for detailed tracking and management of compliance assessments.
    *   **File Search Optimization**: AAOIFI standards search is executed once per session and its context is persistently stored in the database, reducing redundant API calls and ensuring consistent context across user interactions.

-   **Feature Specifications**:
    *   **Contract Analysis**: Upload, language detection, AI analysis against AAOIFI standards, term extraction with compliance status.
    *   **Interactive Consultation**: Q&A with the AI, review and confirmation of user modifications.
    *   **Contract Generation**: Generate new contracts from briefs, modified versions, and marked-up contracts with highlights. PDF generation and preview capabilities.
    *   **Admin & Statistics**: Endpoints for system statistics, user statistics, and expert feedback submission.
    *   **AAOIFI Standards Search**: Search and extract relevant context from AAOIFI documents to inform AI analysis.

-   **System Design Choices**:
    *   **Flask Blueprints**: Provides a scalable and organized structure for API endpoints.
    *   **Environment Variables**: Secure management of API keys and sensitive configurations.
    *   **Graceful Degradation**: Services like file search are designed to handle missing API keys or partial failures gracefully, ensuring core analysis can proceed.
    *   **Logging**: Enhanced logging for performance monitoring and debugging, with suppression of noisy third-party logs.

## External Dependencies
-   **Database**: MongoDB Atlas
-   **AI**: Google Gemini 2.0 Flash (including specific APIs for file search)
-   **Cloud Storage**: Cloudinary
-   **Document Processing**: `python-docx`, LibreOffice (for PDF conversion)