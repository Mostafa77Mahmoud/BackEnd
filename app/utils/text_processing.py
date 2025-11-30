"""
Text processing utilities for the Shariaa Contract Analyzer.
Matches OldStrcturePerfectProject/utils.py and api_server.py exactly.
"""

import re
import uuid
import json
import logging
from unidecode import unidecode

logger = logging.getLogger(__name__)


def clean_model_response(response_text: str | None) -> str:
    """
    Cleans the response text from the model, attempting to extract JSON
    content if it's wrapped in markdown code blocks or found directly.
    For contract text, removes unwanted analysis and commentary.
    Matches OldStrcturePerfectProject/utils.py clean_model_response exactly.
    """
    if not isinstance(response_text, str):
        return ""

    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
    if json_match:
        return json_match.group(1).strip()

    code_match = re.search(r"```\s*([\s\S]*?)\s*```", response_text, re.DOTALL)
    if code_match:
        content = code_match.group(1).strip()
        if (content.startswith('{') and content.endswith('}')) or \
           (content.startswith('[') and content.endswith(']')):
            return content

    first_bracket = response_text.find("[")
    first_curly = response_text.find("{")

    start_index = -1
    end_char = None

    if first_bracket != -1 and (first_curly == -1 or first_bracket < first_curly):
        start_index = first_bracket
        end_char = "]"
    elif first_curly != -1:
        start_index = first_curly
        end_char = "}"

    if start_index != -1 and end_char:
        open_braces = 0
        last_index = -1
        for i in range(start_index, len(response_text)):
            if response_text[i] == ('[' if end_char == ']' else '{'):
                open_braces += 1
            elif response_text[i] == end_char:
                open_braces -= 1
                if open_braces == 0:
                    last_index = i
                    break
        
        if last_index > start_index:
            potential_json = response_text[start_index : last_index + 1].strip()
            try:
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                pass 

    cleaned_text = response_text.strip()
    
    cleaned_text = re.sub(r'^```.*?\n', '', cleaned_text, flags=re.MULTILINE)
    cleaned_text = re.sub(r'\n```$', '', cleaned_text)
    
    lines = cleaned_text.split('\n')
    contract_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            contract_lines.append('')
            continue
            
        if any(keyword in line.lower() for keyword in [
            'تحليل:', 'ملاحظة:', 'تعليق:', 'analysis:', 'note:', 'comment:',
            'يجب ملاحظة', 'من المهم', 'ينبغي الانتباه', 'it should be noted',
            'it is important', 'please note', 'النتيجة:', 'result:', 'الخلاصة:'
        ]):
            continue
            
        if line.startswith(('تعليمات:', 'instructions:', 'metadata:', 'معلومات:')):
            continue
            
        contract_lines.append(line)
    
    return '\n'.join(contract_lines).strip()


def translate_arabic_to_english(arabic_text):
    """
    Translates Arabic contract names to English using simple transliteration.
    Falls back to generic name if translation fails.
    Matches OldStrcturePerfectProject/api_server.py translate_arabic_to_english exactly.
    """
    try:
        transliteration_map = {
            'عقد': 'contract',
            'بيع': 'sale',
            'شراء': 'purchase',
            'إيجار': 'rental',
            'تأجير': 'lease',
            'عمل': 'work',
            'خدمات': 'services',
            'توريد': 'supply',
            'مقاولة': 'contracting',
            'شركة': 'company',
            'مؤسسة': 'institution',
            'الأول': 'first',
            'الثاني': 'second',
            'نهائي': 'final',
            'مبدئي': 'preliminary'
        }

        words = arabic_text.strip().split()
        translated_words = []

        for word in words:
            clean_word = word.replace('ال', '').replace('و', '').replace('في', '').replace('من', '')

            translated = transliteration_map.get(clean_word.lower())
            if translated:
                translated_words.append(translated)
            else:
                transliterated = unidecode(clean_word)
                if transliterated and transliterated.strip():
                    translated_words.append(transliterated.lower())

        if translated_words:
            result = '_'.join(translated_words)[:50]
            logger.info(f"Translated Arabic contract name '{arabic_text}' to '{result}'")
            return result
        else:
            fallback = f"contract_{uuid.uuid4().hex[:8]}"
            logger.warning(f"Could not translate Arabic name '{arabic_text}', using fallback: {fallback}")
            return fallback

    except Exception as e:
        logger.error(f"Error translating Arabic contract name '{arabic_text}': {e}")
        return f"contract_{uuid.uuid4().hex[:8]}"


def generate_safe_public_id(base_name, prefix="", max_length=50):
    """
    Generates a safe, short public_id for Cloudinary uploads.
    Handles Arabic names by translating them to English.
    Matches OldStrcturePerfectProject/api_server.py generate_safe_public_id exactly.
    """
    try:
        from app.utils.file_helpers import clean_filename
        
        if not base_name:
            safe_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
            logger.debug(f"Generated safe public_id for empty base_name: {safe_id}")
            return safe_id

        has_arabic = bool(re.search(r'[\u0600-\u06FF]', base_name))

        if has_arabic:
            logger.info(f"Detected Arabic in contract name: {base_name}")
            english_name = translate_arabic_to_english(base_name)
            clean_name = clean_filename(english_name)
        else:
            clean_name = clean_filename(base_name)

        if len(clean_name) > max_length:
            clean_name = clean_name[:max_length]

        if prefix:
            safe_id = f"{prefix}_{clean_name}_{uuid.uuid4().hex[:6]}"
        else:
            safe_id = f"{clean_name}_{uuid.uuid4().hex[:6]}"

        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', safe_id)

        logger.debug(f"Generated safe public_id: {safe_id} from base_name: {base_name}")
        return safe_id

    except Exception as e:
        logger.error(f"Error generating safe public_id for '{base_name}': {e}")
        fallback_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
        return fallback_id
