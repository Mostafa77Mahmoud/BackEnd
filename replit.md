# Shariaa Contract Analyzer Backend

## Overview

The Shariaa Contract Analyzer is a sophisticated Flask-based backend system designed to analyze legal contracts for compliance with Islamic law (Sharia) principles, specifically following AAOIFI (Accounting and Auditing Organization for Islamic Financial Institutions) standards. The system also supports general legal compliance analysis for various jurisdictions.

**Key Features:**
- Multi-format contract processing (DOCX, PDF, TXT)
- AI-powered compliance analysis using Google Gemini 2.0 Flash
- Interactive user consultation with real-time Q&A
- Expert review system integration
- Automated contract modification and regeneration
- Cloud-based document management with Cloudinary
- Multi-language support (Arabic and English)
- Modular architecture with service-oriented design

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Application Framework
- **Flask Application Factory Pattern**: Modular Flask setup with blueprints for route organization
- **Service Layer Architecture**: Clear separation between routes, services, and utilities
- **Configuration Management**: Environment-based configuration with secure defaults

### Core Services
- **Database Service**: MongoDB Atlas integration for document storage with graceful fallback handling
- **AI Service**: Google Gemini 2.0 Flash integration for contract analysis and text processing
- **Cloud Storage Service**: Cloudinary integration for document management with automatic fallbacks
- **Document Processing Service**: LibreOffice headless conversion for DOCX to PDF transformation

### API Architecture
- **RESTful Design**: Well-structured endpoints following REST principles
- **Blueprint Organization**: Routes separated by functional areas (analysis, generation, interaction, admin)
- **Comprehensive Error Handling**: Graceful degradation when services are unavailable
- **CORS Configuration**: Configured for web client integration

### Data Architecture
- **Document Schema**: Structured storage for contracts, analysis results, and user interactions
- **Session Management**: UUID-based session tracking for multi-step processes
- **Term Extraction**: Structured term identification with unique IDs for precise modification tracking

### Processing Pipeline
- **File Upload Processing**: Multi-format support with secure filename handling
- **Text Extraction**: AI-powered text extraction preserving document structure
- **Compliance Analysis**: Dual-mode analysis (Sharia/Legal) with jurisdiction support
- **Interactive Consultation**: Real-time Q&A with context-aware responses
- **Contract Modification**: User-guided modification with expert review integration

### Prompt Management System
- **Structured Prompt Library**: Organized prompt files for different analysis types and languages
- **Template-based Approach**: Parameterized prompts for consistent AI interactions
- **Multi-language Support**: Language-specific prompts for Arabic and English analysis

### Security & Performance
- **Input Validation**: Comprehensive input sanitization and file type checking
- **Rate Limiting**: Built-in protection against abuse
- **Secure File Handling**: Temporary file management with automatic cleanup
- **Resource Management**: Optimized for cloud deployment with configurable workers

## External Dependencies

### AI Services
- **Google Generative AI (Gemini 2.0 Flash)**: Primary AI engine for contract analysis, text extraction, and natural language processing
- **Language Detection**: Automatic language detection for appropriate prompt selection

### Database
- **MongoDB Atlas**: Primary database for storing contracts, analysis results, terms, and expert feedback
- **Redis Cache**: Session storage and caching layer (referenced in architecture docs)

### Cloud Storage
- **Cloudinary**: Document storage and management with organized folder structure for different document types

### Document Processing
- **LibreOffice Headless**: Server-side document conversion (DOCX to PDF)
- **python-docx**: DOCX document manipulation and generation
- **unidecode**: Text normalization and filename sanitization

### Web Framework & Infrastructure
- **Flask**: Core web framework with CORS support
- **Gunicorn**: WSGI server for production deployment
- **Werkzeug**: Secure file upload handling

### Development & Monitoring
- **Logging Infrastructure**: Comprehensive logging system for debugging and monitoring
- **Replit Environment**: Optimized for Replit hosting with appropriate bindings and configurations

### Configuration Management
- **Environment Variables**: Secure credential management for API keys and database connections
- **Multi-environment Support**: Configuration classes for development, testing, and production