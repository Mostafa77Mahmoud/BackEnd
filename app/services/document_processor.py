"""
Document processing service for DOCX manipulation and conversion.
Matches OldStrcturePerfectProject/doc_processing.py exactly.
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
                            
                            md_line_cell = ""
                            for run in para_in_cell.runs:
                                text = run.text
                                if run.bold: text = f"**{text}**"
                                if run.italic: text = f"*{text}*"
                                if run.underline: text = f"__{text}__"
                                md_line_cell += text

                            # Add ID only to the first part of the cell content for clarity
                            if cell_para_idx_counter == 0:
                                cell_markdown_content += f"[[ID:{cell_para_id}]] {md_line_cell}"
                            else:
                                cell_markdown_content += f"\n[[ID:{cell_para_id}]] {md_line_cell}"
                            
                            cell_plain_content += para_in_cell.text + "\n"
                            cell_para_idx_counter += 1
                    
                    row_text_parts.append(cell_markdown_content.replace("\n", "<br>"))
                    row_plain_parts.append(cell_plain_content.strip())

                md_table.append("| " + " | ".join(row_text_parts) + " |")
                plain_text_parts.append(" | ".join(row_plain_parts))

                if r_idx == 0:
                    md_table.append("|" + " --- |" * len(row.cells))
            
            structured_markdown.extend(md_table)
            structured_markdown.append(f"[[TABLE_END:{table_id_prefix}]]")
            table_idx_counter_body += 1

    return "\n\n".join(structured_markdown), "\n".join(plain_text_parts)


def set_cell_direction_rtl(cell: _Cell):
    """Sets the visual direction of a table cell to RTL."""
    tcPr = cell._tc.get_or_add_tcPr() 
    bidiVisual = tcPr.find(qn('w:bidiVisual'))
    if bidiVisual is None:
        bidiVisual = OxmlElement('w:bidiVisual')
        tcPr.append(bidiVisual)


def _parse_markdown_to_parts_for_runs(text_line: str) -> list[dict]:
    """Helper to parse a line of markdown text for bold, italic, and underline into parts for runs."""
    parts_raw = re.split(r'(\*\*|\*|__)', text_line)
    
    parts = []
    is_bold = False
    is_italic = False
    is_underline = False
    
    for part in parts_raw:
        if part == '**': is_bold = not is_bold; continue
        if part == '*': is_italic = not is_italic; continue
        if part == '__': is_underline = not is_underline; continue
        
        if part:
            parts.append({
                "text": part,
                "bold": is_bold,
                "italic": is_italic,
                "underline": is_underline
            })
    return parts


def _add_paragraph_with_markdown_formatting(
    doc_or_cell, 
    style_name: str,
    text_content: str,
    contract_language: str,
    chosen_font: str,
    text_color: RGBColor | None = None,
    strike: bool = False, 
    is_list_item: bool = False,
    list_indent: Inches | None = None,
    first_line_indent_list: Inches | None = None 
):
    """
    Adds a new paragraph with specified text, parsing markdown for bold, italic, and underline.
    """
    if hasattr(doc_or_cell, 'add_paragraph'):
        p = doc_or_cell.add_paragraph(style=style_name)
    else: 
        if doc_or_cell.paragraphs:
            p = doc_or_cell.paragraphs[0]
            for run in list(p.runs): 
                p_element = run._element.getparent()
                if p_element is not None:
                    p_element.remove(run._element)
        else:
            p = doc_or_cell.add_paragraph()
        p.style = doc_or_cell.part.document.styles[style_name]

    if contract_language == 'ar':
        if style_name not in ['TitleStyle', 'BasmalaStyle', 'Heading2Style', 'Heading3Style']:
            p.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT 
        p.paragraph_format.rtl = True 
        if is_list_item and list_indent is not None:
            p.paragraph_format.left_indent = list_indent 
            if first_line_indent_list is not None: 
                 p.paragraph_format.first_line_indent = first_line_indent_list
    else: 
        if style_name not in ['TitleStyle', 'BasmalaStyle', 'Heading2Style', 'Heading3Style']:
            p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
        p.paragraph_format.rtl = False 
        if is_list_item and list_indent is not None:
            p.paragraph_format.left_indent = list_indent

    parts = _parse_markdown_to_parts_for_runs(text_content)

    for part_info in parts:
        run = p.add_run(part_info["text"])
        if part_info["bold"]: run.bold = True
        if part_info["italic"]: run.italic = True
        if part_info["underline"]: run.underline = True
        run.font.rtl = (contract_language == 'ar') 
        run.font.name = chosen_font
        
        style_font_size = p.style.font.size if p.style and p.style.font else None
        run.font.size = style_font_size if style_font_size else Pt(12) 

        if text_color:
            run.font.color.rgb = text_color
        elif p.style and p.style.font and p.style.font.color and p.style.font.color.rgb:
            run.font.color.rgb = p.style.font.color.rgb
        
        if strike and (not text_color or text_color.rgb != RGBColor(255,0,0).rgb):
            run.font.strike = True
    return p


def _determine_style_and_text(line: str, contract_language: str) -> tuple[str, str, bool, bool]:
    """Helper to determine paragraph style and clean text from a markdown line."""
    current_style_name = 'NormalStyle'
    is_main_title = False
    is_list_item_flag = False
    text_for_paragraph_content = line.strip() 

    if line.strip() == "بسم الله الرحمن الرحيم":
        current_style_name = 'BasmalaStyle'
        text_for_paragraph_content = line.strip()
        return current_style_name, text_for_paragraph_content, is_main_title, is_list_item_flag

    if line.startswith('# '): 
        current_style_name = 'TitleStyle'
        is_main_title = True
        text_for_paragraph_content = re.sub(r'^#\s*', '', line).strip()
    elif contract_language == 'ar' and (
        re.match(r'^(البند)\s+(الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|الحادي عشر|الثاني عشر|الأخير|التمهيدي)\s*[:]?\s*$', line.strip()) or
        re.match(r'^(المادة)\s+\d+\s*[:]?\s*$', line.strip()) 
    ):
        current_style_name = 'Heading2Style'
        text_for_paragraph_content = line.strip() 
    elif contract_language == 'en' and (
        re.match(r'^(Clause|Article|Section)\s+\d+\s*[:]?\s*$', line.strip(), re.IGNORECASE) or
        re.match(r'^(Preamble|Preliminary Clause)\s*[:]?\s*$', line.strip(), re.IGNORECASE)
    ):
        current_style_name = 'Heading2Style'
        text_for_paragraph_content = line.strip()
    elif contract_language == 'ar' and (
        re.match(r'^(أولاً|ثانياً|ثالثاً|رابعاً|خامساً|سادساً|سابعاً|ثامناً|تاسعاً|عاشراً)\s*[:]', line.strip()) or
        re.match(r'^[أ-ي]\.\s+', line.strip()) 
    ):
        current_style_name = 'Heading3Style'
        text_for_paragraph_content = line.strip() 
    elif contract_language == 'en' and (
        re.match(r'^(Firstly|Secondly|Thirdly|Fourthly|Fifthly)\s*[:]', line.strip(), re.IGNORECASE) or
        re.match(r'^[A-Z]\.\s+', line.strip()) 
    ):
        current_style_name = 'Heading3Style'
        text_for_paragraph_content = line.strip()
    elif line.startswith('## '): 
        current_style_name = 'Heading2Style' 
        text_for_paragraph_content = re.sub(r'^##\s*', '', line).strip()
    elif line.startswith('### '): 
        current_style_name = 'Heading3Style'
        text_for_paragraph_content = re.sub(r'^###\s*', '', line).strip()
    elif line.startswith(("* ", "- ", "+ ")) or re.match(r'^\d+\.\s+', line):
        current_style_name = 'ListBulletStyle'
        is_list_item_flag = True
        text_for_paragraph_content = re.sub(r'^\s*[\*\-\+]+\s*|^\s*\d+\.\s*', '', line).strip()
    else:
        text_for_paragraph_content = line.strip() 
        
    text_for_paragraph_content = re.sub(r'^\[\[ID:.*?\]\]\s*', '', text_for_paragraph_content).strip()
    return current_style_name, text_for_paragraph_content, is_main_title, is_list_item_flag


def create_docx_from_llm_markdown(
    original_markdown_text: str, 
    output_path: str, 
    contract_language: str = 'ar', 
    terms_for_marking: list[dict] | dict | None = None,
    confirmed_modifications: dict | None = None
):
    """
    Creates a professional DOCX document from markdown text with term highlighting.
    Matches OldStrcturePerfectProject/doc_processing.py exactly.
    """
    try:
        doc = DocxDocument()
        chosen_font = "Arial" 
        
        for section in doc.sections:
            section.page_width = Inches(8.27) 
            section.page_height = Inches(11.69)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)
            section.top_margin = Inches(0.75)
            section.bottom_margin = Inches(0.75)

        styles = doc.styles
        basmala_style = styles.add_style('BasmalaStyle', WD_STYLE_TYPE.PARAGRAPH)
        basmala_format = basmala_style.paragraph_format
        basmala_format.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        basmala_format.space_before = Pt(0) 
        basmala_format.space_after = Pt(12) 
        basmala_font = basmala_style.font
        basmala_font.rtl = True 
        basmala_font.name = chosen_font 
        basmala_font.size = Pt(18) 
        basmala_font.bold = True

        title_style = styles.add_style('TitleStyle', WD_STYLE_TYPE.PARAGRAPH)
        title_format = title_style.paragraph_format
        title_format.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        title_format.space_after = Pt(18) 
        title_font = title_style.font
        title_font.rtl = (contract_language == 'ar')
        title_font.name = chosen_font
        title_font.size = Pt(20) 
        title_font.bold = True
        title_font.color.rgb = RGBColor(0, 0, 0)

        heading2_style = styles.add_style('Heading2Style', WD_STYLE_TYPE.PARAGRAPH)
        heading2_format = heading2_style.paragraph_format
        heading2_format.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER if contract_language == 'ar' else WD_PARAGRAPH_ALIGNMENT.LEFT 
        heading2_format.space_before = Pt(12)
        heading2_format.space_after = Pt(6)
        heading2_font = heading2_style.font
        heading2_font.rtl = (contract_language == 'ar')
        heading2_font.name = chosen_font
        heading2_font.size = Pt(16) 
        heading2_font.bold = True
        heading2_font.underline = False 

        heading3_style = styles.add_style('Heading3Style', WD_STYLE_TYPE.PARAGRAPH)
        heading3_format = heading3_style.paragraph_format
        heading3_format.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT if contract_language == 'ar' else WD_PARAGRAPH_ALIGNMENT.LEFT
        heading3_format.space_before = Pt(10)
        heading3_format.space_after = Pt(4)
        heading3_font = heading3_style.font
        heading3_font.rtl = (contract_language == 'ar')
        heading3_font.name = chosen_font
        heading3_font.size = Pt(14) 
        heading3_font.bold = True 
        heading3_font.underline = False 

        normal_style = styles.add_style('NormalStyle', WD_STYLE_TYPE.PARAGRAPH)
        normal_format = normal_style.paragraph_format
        normal_format.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT if contract_language == 'ar' else WD_PARAGRAPH_ALIGNMENT.LEFT
        if contract_language == 'ar': 
            normal_format.alignment = WD_PARAGRAPH_ALIGNMENT.JUSTIFY_LOW 
        normal_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        normal_format.space_after = Pt(6) 
        normal_font = normal_style.font
        normal_font.rtl = (contract_language == 'ar')
        normal_font.name = chosen_font
        normal_font.size = Pt(12) 
        
        list_indent_val = Inches(0.5 if contract_language == 'ar' else 0.25)
        first_line_indent_val_list = Inches(-0.25) if contract_language == 'ar' else Inches(0) 
        
        list_style = styles.add_style('ListBulletStyle', WD_STYLE_TYPE.PARAGRAPH)
        list_format = list_style.paragraph_format
        list_format.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT if contract_language == 'ar' else WD_PARAGRAPH_ALIGNMENT.LEFT
        list_format.left_indent = list_indent_val 
        if contract_language == 'ar':
            list_format.first_line_indent = first_line_indent_val_list 
        list_format.space_after = Pt(4)
        list_font = list_style.font
        list_font.rtl = (contract_language == 'ar')
        list_font.name = chosen_font
        list_font.size = Pt(12)
        
        table_style = doc.styles.add_style('CustomTable', WD_STYLE_TYPE.TABLE)
        table_style.font.name = chosen_font
        table_style.font.size = Pt(10)

        lines = original_markdown_text.split('\n')
        processed_markdown_text = original_markdown_text
        if lines and lines[0].strip() == "بسم الله الرحمن الرحيم":
            _add_paragraph_with_markdown_formatting(doc, 'BasmalaStyle', lines[0].strip(), 'ar', chosen_font) 
            processed_markdown_text = "\n".join(lines[1:]) 
        
        if isinstance(terms_for_marking, list) and terms_for_marking: 
            logger.info(f"DOC_PROCESSING: Using new list-based term marking logic for PDF/TXT. {len(terms_for_marking)} terms.")
            current_markdown_pos = 0
            
            for term_idx, term_data in enumerate(terms_for_marking):
                term_text_original = term_data.get("term_text", "") 
                if not term_text_original.strip(): 
                    continue
                
                search_start_pos = current_markdown_pos
                term_text_pattern = re.escape(term_text_original).replace(r'\\n', r'\s*\\n\s*') 
                term_text_pattern = term_text_pattern.replace(r'\n', r'\s*\n\s*') 
                
                match = None
                try:
                    match = re.search(term_text_pattern, processed_markdown_text[search_start_pos:], re.DOTALL)
                except re.error as re_err:
                    logger.warning(f"Regex error for term '{term_data.get('term_id')}': {re_err}. Falling back to string find.")
                    _found_pos = processed_markdown_text.find(term_text_original, search_start_pos)
                    if _found_pos != -1:
                        class FallbackMatch:
                            def start(self): return _found_pos - search_start_pos
                            def group(self, _): return term_text_original
                        match = FallbackMatch()

                if match:
                    found_pos_relative = match.start()
                    found_pos_absolute = search_start_pos + found_pos_relative
                    matched_text_in_doc = match.group(0) 

                    inter_term_text = processed_markdown_text[current_markdown_pos:found_pos_absolute]
                    if inter_term_text.strip():
                        for line_in_inter_term in inter_term_text.splitlines(): 
                             if "[[TABLE_" in line_in_inter_term: 
                                 continue
                             l_style, l_text, _, l_is_list = _determine_style_and_text(line_in_inter_term, contract_language)
                             _add_paragraph_with_markdown_formatting(doc, l_style, l_text, contract_language, chosen_font, is_list_item=l_is_list, list_indent=list_indent_val if l_is_list else None, first_line_indent_list=first_line_indent_val_list if l_is_list and contract_language == 'ar' else None)
                    
                    logger.info(f"Found term '{term_data.get('term_id')}' at pos {found_pos_absolute}")
                    initial_is_valid = term_data.get("is_valid_sharia", True)
                    is_confirmed = term_data.get("is_confirmed_by_user", False)
                    confirmed_text_content = term_data.get("confirmed_modified_text") 
                    
                    term_lines_to_render_original = matched_text_in_doc.splitlines() 

                    if is_confirmed and confirmed_text_content and \
                       not initial_is_valid and confirmed_text_content.strip() != term_text_original.strip():
                        logger.info(f"Applying MARKING: Red original, Green new for term {term_data.get('term_id')}")
                        for line_in_term in term_lines_to_render_original:
                             if "[[TABLE_" in line_in_term: 
                                 continue
                             l_style, l_text, _, l_is_list = _determine_style_and_text(line_in_term, contract_language)
                             _add_paragraph_with_markdown_formatting(doc, l_style, l_text, contract_language, chosen_font, text_color=RGBColor(255,0,0), strike=False, is_list_item=l_is_list, list_indent=list_indent_val if l_is_list else None, first_line_indent_list=first_line_indent_val_list if l_is_list and contract_language == 'ar' else None) 
                        
                        sep_para = doc.add_paragraph(style='NormalStyle')
                        sep_para.paragraph_format.rtl = (contract_language == 'ar')
                        sep_para.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT if contract_language == 'ar' else WD_PARAGRAPH_ALIGNMENT.LEFT
                        sep_run = sep_para.add_run(("التعديل المؤكد: " if contract_language == 'ar' else "Confirmed Modification: "))
                        sep_run.font.size = Pt(10)
                        sep_run.italic = True
                        sep_run.font.name = chosen_font
                        sep_run.font.rtl = (contract_language == 'ar')
                        
                        for line_in_confirmed_text in confirmed_text_content.splitlines():
                            if "[[TABLE_" in line_in_confirmed_text: 
                                continue
                            l_style, l_text, _, l_is_list = _determine_style_and_text(line_in_confirmed_text, contract_language)
                            _add_paragraph_with_markdown_formatting(doc, l_style, l_text, contract_language, chosen_font, text_color=RGBColor(0,128,0), is_list_item=l_is_list, list_indent=list_indent_val if l_is_list else None, first_line_indent_list=first_line_indent_val_list if l_is_list and contract_language == 'ar' else None)
                    else:
                        text_to_render_for_term = matched_text_in_doc 
                        final_text_color_for_term = None
                        if is_confirmed and confirmed_text_content:
                            text_to_render_for_term = confirmed_text_content 
                            final_text_color_for_term = RGBColor(0,128,0) 
                            logger.info(f"Applying MARKING: Green (confirmed) for term {term_data.get('term_id')}")
                        elif not initial_is_valid:
                            final_text_color_for_term = RGBColor(255,0,0) 
                            logger.info(f"Applying MARKING: Red (initially invalid) for term {term_data.get('term_id')}")
                        
                        for line_in_term_render in text_to_render_for_term.splitlines():
                            if "[[TABLE_" in line_in_term_render: 
                                continue
                            l_style, l_text, _, l_is_list = _determine_style_and_text(line_in_term_render, contract_language)
                            _add_paragraph_with_markdown_formatting(doc, l_style, l_text, contract_language, chosen_font, text_color=final_text_color_for_term, strike=False, is_list_item=l_is_list, list_indent=list_indent_val if l_is_list else None, first_line_indent_list=first_line_indent_val_list if l_is_list and contract_language == 'ar' else None) 
                    
                    current_markdown_pos = found_pos_absolute + len(matched_text_in_doc)
                else:
                    logger.warning(f"Term '{term_data.get('term_id')}' text not found sequentially from pos {search_start_pos}")
            
            if current_markdown_pos < len(processed_markdown_text):
                remaining_text = processed_markdown_text[current_markdown_pos:]
                for line_in_remaining in remaining_text.splitlines():
                    if "[[TABLE_" in line_in_remaining: 
                        continue
                    l_style, l_text, _, l_is_list = _determine_style_and_text(line_in_remaining, contract_language)
                    _add_paragraph_with_markdown_formatting(doc, l_style, l_text, contract_language, chosen_font, is_list_item=l_is_list, list_indent=list_indent_val if l_is_list else None, first_line_indent_list=first_line_indent_val_list if l_is_list and contract_language == 'ar' else None)
        else:
            for line in processed_markdown_text.split('\n'):
                line = line.strip()
                if not line or "[[TABLE_" in line:
                    continue
                l_style, l_text, _, l_is_list = _determine_style_and_text(line, contract_language)
                _add_paragraph_with_markdown_formatting(doc, l_style, l_text, contract_language, chosen_font, is_list_item=l_is_list, list_indent=list_indent_val if l_is_list else None, first_line_indent_list=first_line_indent_val_list if l_is_list and contract_language == 'ar' else None)

        ensure_dir(os.path.dirname(output_path))
        doc.save(output_path)
        
        logger.info(f"DOCX document created successfully: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error creating DOCX document: {e}")
        traceback.print_exc()
        return None


def convert_docx_to_pdf(docx_file_path: str, output_folder: str) -> str | None:
    """Convert a DOCX file to PDF using LibreOffice."""
    try:
        ensure_dir(output_folder)
        
        libreoffice_path = current_app.config.get('LIBREOFFICE_PATH', 'libreoffice')
        
        logger.info(f"Converting DOCX to PDF: {docx_file_path} -> {output_folder}")
        
        command = [
            libreoffice_path,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", output_folder,
            docx_file_path
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
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
