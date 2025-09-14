"""
Document processing service for DOCX manipulation and conversion.
Consolidated from original doc_processing.py
"""

import os
import uuid
import re
import traceback
import subprocess
import tempfile
from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT, WD_LINE_SPACING, WD_BREAK 
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_DIRECTION, WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl, CT_TcPr
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell
import logging
from flask import current_app

from app.utils.file_helpers import ensure_dir, clean_filename
from app.utils.text_processing import clean_model_response

logger = logging.getLogger(__name__)

def build_structured_text_for_analysis(doc: DocxDocument) -> tuple[str, str]:
    """
    Extracts text from a DOCX document, converting it to a markdown-like format
    that preserves bold, italic, and underline formatting, while also assigning
    unique IDs to paragraphs and table cell content for precise term identification.
    Returns a structured markdown string with IDs and a plain text version.
    """
    structured_markdown = []
    plain_text_parts = []
    para_idx_counter_body = 0
    table_idx_counter_body = 0

    for element in doc.element.body:
        if isinstance(element, CT_P):
            para = Paragraph(element, doc)
            if para.text.strip():
                para_id = f"para_{para_idx_counter_body}"
                
                # Convert paragraph to markdown while preserving formatting
                markdown_line = ""
                for run in para.runs:
                    text = run.text
                    if run.bold: text = f"**{text}**"
                    if run.italic: text = f"*{text}*"
                    if run.underline: text = f"__{text}__"
                    markdown_line += text
                
                structured_markdown.append(f"[[ID:{para_id}]]\n{markdown_line}")
                plain_text_parts.append(para.text)
                para_idx_counter_body += 1

        elif isinstance(element, CT_Tbl):
            table = Table(element, doc)
            table_id_prefix = f"table_{table_idx_counter_body}"
            structured_markdown.append(f"[[TABLE_START:{table_id_prefix}]]")
            plain_text_parts.append(f"[جدول {table_idx_counter_body+1}]")

            # Convert table to markdown table format
            md_table = []
            for r_idx, row in enumerate(table.rows):
                row_text_parts = []
                row_plain_parts = []
                for c_idx, cell in enumerate(row.cells):
                    cell_id_prefix = f"{table_id_prefix}_r{r_idx}_c{c_idx}"
                    cell_para_idx_counter = 0
                    cell_markdown_content = ""
                    cell_plain_content = ""

                    for para_in_cell in cell.paragraphs:
                        if para_in_cell.text.strip():
                            cell_para_id = f"{cell_id_prefix}_p{cell_para_idx_counter}"
                            
                            # Convert cell paragraph to markdown
                            cell_markdown_line = ""
                            for run in para_in_cell.runs:
                                text = run.text
                                if run.bold: text = f"**{text}**"
                                if run.italic: text = f"*{text}*"
                                if run.underline: text = f"__{text}__"
                                cell_markdown_line += text
                            
                            cell_markdown_content += f"[[ID:{cell_para_id}]] {cell_markdown_line} "
                            cell_plain_content += para_in_cell.text + " "
                            cell_para_idx_counter += 1

                    row_text_parts.append(cell_markdown_content.strip())
                    row_plain_parts.append(cell_plain_content.strip())

                md_table.append("| " + " | ".join(row_text_parts) + " |")
                plain_text_parts.extend(row_plain_parts)

            structured_markdown.extend(md_table)
            structured_markdown.append(f"[[TABLE_END:{table_id_prefix}]]")
            table_idx_counter_body += 1

    return "\n".join(structured_markdown), "\n".join(plain_text_parts)

def convert_docx_to_pdf(docx_file_path: str, output_folder: str) -> str | None:
    """Convert a DOCX file to PDF using LibreOffice."""
    try:
        ensure_dir(output_folder)
        
        libreoffice_path = current_app.config.get('LIBREOFFICE_PATH', 'libreoffice')
        
        logger.info(f"Converting DOCX to PDF: {docx_file_path} -> {output_folder}")
        
        # Run LibreOffice headless conversion
        command = [
            libreoffice_path,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", output_folder,
            docx_file_path
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            # Find the generated PDF file
            docx_basename = os.path.splitext(os.path.basename(docx_file_path))[0]
            pdf_path = os.path.join(output_folder, f"{docx_basename}.pdf")
            
            if os.path.exists(pdf_path):
                logger.info(f"PDF conversion successful: {pdf_path}")
                return pdf_path
            else:
                logger.error(f"PDF file not found after conversion: {pdf_path}")
                return None
        else:
            logger.error(f"LibreOffice conversion failed: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error("LibreOffice conversion timed out")
        return None
    except Exception as e:
        logger.error(f"Error during PDF conversion: {e}")
        traceback.print_exc()
        return None

def create_docx_from_llm_markdown(
    original_markdown_text: str,
    output_path: str,
    contract_language: str = 'ar',
    terms_for_marking: list[dict] | dict | None = None
):
    """
    Creates a professional DOCX document from markdown text with term highlighting.
    Supports Arabic RTL layout and color coding for terms.
    """
    try:
        logger.info(f"Creating DOCX from markdown: {output_path}")
        
        # Create new document
        doc = DocxDocument()
        
        # Set up styles for Arabic/RTL support
        if contract_language == 'ar':
            _setup_arabic_styles(doc)
        
        # Process the markdown text and create document content
        _process_markdown_to_docx(doc, original_markdown_text, terms_for_marking, contract_language)
        
        # Save the document
        ensure_dir(os.path.dirname(output_path))
        doc.save(output_path)
        
        logger.info(f"DOCX document created successfully: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error creating DOCX document: {e}")
        traceback.print_exc()
        return None

def _setup_arabic_styles(doc):
    """Set up Arabic RTL styles for the document."""
    # Add Arabic font style
    styles = doc.styles
    
    # Create Arabic paragraph style
    try:
        arabic_style = styles.add_style('Arabic Text', WD_STYLE_TYPE.PARAGRAPH)
        arabic_style.font.name = 'Arabic Typesetting'
        arabic_style.font.size = Pt(12)
        arabic_style.paragraph_format.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
    except:
        pass  # Style may already exist

def _process_markdown_to_docx(doc, markdown_text: str, terms_for_marking, contract_language: str):
    """Process markdown text and add to DOCX document with formatting."""
    lines = markdown_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Handle ID markers
        if line.startswith('[[ID:') and line.endswith(']]'):
            continue  # Skip ID-only lines
            
        # Handle table markers
        if line.startswith('[[TABLE_START:') or line.startswith('[[TABLE_END:'):
            continue  # Skip table markers for now
            
        # Process regular text lines
        para = doc.add_paragraph()
        
        if contract_language == 'ar':
            para.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
            
        # Add text with basic formatting
        _add_formatted_text_to_paragraph(para, line, terms_for_marking)

def _add_formatted_text_to_paragraph(para, text: str, terms_for_marking):
    """Add formatted text to a paragraph, handling markdown formatting."""
    # Simple markdown processing for bold, italic, underline
    # This is a simplified version - could be expanded for full markdown support
    
    # Remove ID markers if present
    text = re.sub(r'\[\[ID:[^\]]+\]\]\s*', '', text)
    
    run = para.add_run(text)
    
    # Apply highlighting if this text matches terms for marking
    if terms_for_marking:
        _apply_term_highlighting(run, text, terms_for_marking)

def _apply_term_highlighting(run, text: str, terms_for_marking):
    """Apply highlighting to terms that need to be marked."""
    if not terms_for_marking:
        return
        
    # Convert terms_for_marking to a list if it's a dict
    if isinstance(terms_for_marking, dict):
        terms_list = list(terms_for_marking.values())
    else:
        terms_list = terms_for_marking
        
    # Simple highlighting for terms
    for term in terms_list:
        if isinstance(term, dict) and 'term_text' in term:
            if term['term_text'].strip() in text:
                # Highlight non-compliant terms in red
                if not term.get('is_valid_sharia', True):
                    run.font.color.rgb = RGBColor(255, 0, 0)  # Red
                else:
                    run.font.color.rgb = RGBColor(0, 128, 0)  # Green