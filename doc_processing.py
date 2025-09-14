# NOTE: shim — kept for backward compatibility
# All functionality moved to app/services/document_processor.py

from app.services.document_processor import (
    build_structured_text_for_analysis,
    create_docx_from_llm_markdown,
    convert_docx_to_pdf
)

__all__ = [
    'build_structured_text_for_analysis',
    'create_docx_from_llm_markdown', 
    'convert_docx_to_pdf'
]