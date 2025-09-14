"""
Text processing utilities for the Shariaa Contract Analyzer.
Consolidated from original utils.py and api_server.py
"""

import re
import uuid
import logging
from unidecode import unidecode

logger = logging.getLogger(__name__)

def clean_model_response(response_text: str | None) -> str:
    """
    Cleans the response text from the model, attempting to extract JSON
    content if it's wrapped in markdown code blocks or found directly.
    For contract text, removes unwanted analysis and commentary.
    """
    if not isinstance(response_text, str):
        return ""

    # Try to find JSON within ```json ... ```
    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
    if json_match:
        return json_match.group(1).strip()

    # Try to find JSON within ``` ... ``` (generic code block)
    code_match = re.search(r"```\s*([\s\S]*?)\s*```", response_text, re.DOTALL)
    if code_match:
        content = code_match.group(1).strip()
        # Check if the content looks like a JSON object or array
        if (content.startswith('{') and content.endswith('}')) or \
           (content.startswith('[') and content.endswith(']')):
            return content

    # If no markdown blocks, try to find the first occurrence of '{' or '['
    # and extract up to the matching '}' or ']'
    if '{' in response_text:
        start_idx = response_text.index('{')
        bracket_count = 0
        for i, char in enumerate(response_text[start_idx:], start_idx):
            if char == '{':
                bracket_count += 1
            elif char == '}':
                bracket_count -= 1
                if bracket_count == 0:
                    return response_text[start_idx:i+1]
    
    if '[' in response_text:
        start_idx = response_text.index('[')
        bracket_count = 0
        for i, char in enumerate(response_text[start_idx:], start_idx):
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    return response_text[start_idx:i+1]

    # If nothing else works, return the original text
    return response_text.strip()

def translate_arabic_to_english(arabic_text):
    """
    Translates Arabic contract names to English using simple transliteration.
    Falls back to generic name if translation fails.
    """
    try:
        # Simple transliteration mapping for common Arabic words in contracts
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

        # Clean and split the Arabic text
        words = arabic_text.strip().split()
        translated_words = []

        for word in words:
            # Remove common Arabic articles and prepositions
            clean_word = word.replace('ال', '').replace('و', '').replace('في', '').replace('من', '')

            # Look for direct translation
            translated = transliteration_map.get(clean_word.lower())
            if translated:
                translated_words.append(translated)
            else:
                # Fallback: use unidecode for transliteration
                transliterated = unidecode(clean_word)
                if transliterated and transliterated.strip():
                    translated_words.append(transliterated.lower())

        if translated_words:
            result = '_'.join(translated_words)[:50]  # Limit length
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
    """
    try:
        if not base_name:
            safe_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
            logger.debug(f"Generated safe public_id for empty base_name: {safe_id}")
            return safe_id

        # Detect if the name contains Arabic characters
        has_arabic = bool(re.search(r'[\u0600-\u06FF]', base_name))

        if has_arabic:
            logger.info(f"Detected Arabic in contract name: {base_name}")
            english_name = translate_arabic_to_english(base_name)
            clean_name = clean_filename(english_name)
        else:
            clean_name = clean_filename(base_name)

        # Ensure the name is not too long
        if len(clean_name) > max_length:
            clean_name = clean_name[:max_length]

        # Generate final public_id
        if prefix:
            safe_id = f"{prefix}_{clean_name}_{uuid.uuid4().hex[:6]}"
        else:
            safe_id = f"{clean_name}_{uuid.uuid4().hex[:6]}"

        # Final safety check - remove any remaining problematic characters
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', safe_id)

        logger.debug(f"Generated safe public_id: {safe_id} from base_name: {base_name}")
        return safe_id

    except Exception as e:
        logger.error(f"Error generating safe public_id for '{base_name}': {e}")
        fallback_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
        return fallback_id