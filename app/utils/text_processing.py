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


def normalize_text_for_matching(text: str) -> str:
    """
    Normalizes text for flexible matching by:
    - Removing markdown formatting (**bold**, *italic*, __underline__)
    - Collapsing multiple whitespace/newlines to single space
    - Stripping leading/trailing whitespace
    - Removing [[ID:...]] markers
    """
    if not text:
        return ""
    
    # Remove [[ID:...]] markers
    normalized = re.sub(r'\[\[ID:.*?\]\]\s*', '', text)
    
    # Remove markdown formatting
    normalized = re.sub(r'\*\*([^*]+)\*\*', r'\1', normalized)  # **bold**
    normalized = re.sub(r'\*([^*]+)\*', r'\1', normalized)      # *italic*
    normalized = re.sub(r'__([^_]+)__', r'\1', normalized)      # __underline__
    
    # Collapse whitespace and newlines
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return normalized.strip()


def flexible_text_replace(source_text: str, original_text: str, replacement_text: str) -> tuple[str, bool]:
    """
    Performs flexible text replacement that handles whitespace and formatting differences.
    Uses normalized text for matching but performs replacement on original text.
    
    SAFETY: If precise span mapping fails, returns original text unchanged rather than 
    risking wrong replacements.
    
    Args:
        source_text: The full text to search in
        original_text: The text to find and replace
        replacement_text: The text to replace with
    
    Returns:
        tuple: (modified_text, was_replaced)
    """
    if not original_text or not source_text:
        return source_text, False
    
    # Try exact match first (fastest and most reliable)
    if original_text in source_text:
        return source_text.replace(original_text, replacement_text, 1), True
    
    # Try with stripped whitespace on both sides
    stripped_original = original_text.strip()
    if stripped_original and stripped_original in source_text:
        return source_text.replace(stripped_original, replacement_text, 1), True
    
    # Normalize both texts for comparison
    normalized_original = normalize_text_for_matching(original_text)
    
    if not normalized_original or len(normalized_original) < 10:
        # Too short to safely match with normalization
        return source_text, False
    
    # Build position mapping from original to normalized
    # This allows us to find where the normalized match is in the original text
    match_result = _find_match_with_position_mapping(source_text, normalized_original)
    
    if match_result is not None:
        start_pos, end_pos = match_result
        result = source_text[:start_pos] + replacement_text + source_text[end_pos:]
        return result, True
    
    # SAFETY: If we can't find a precise match, skip this term
    # rather than risk corrupting the document with wrong replacements
    logger.debug(f"Could not find precise match for replacement: {original_text[:80]}...")
    return source_text, False


def _find_match_with_position_mapping(source_text: str, normalized_target: str) -> tuple[int, int] | None:
    """
    Find the exact span in source_text that corresponds to normalized_target.
    Uses position mapping to ensure we find the correct occurrence.
    
    Returns (start, end) positions or None if no precise match found.
    """
    if not normalized_target:
        return None
    
    # Build a mapping: for each position in source, track what normalized position it corresponds to
    # This ensures we correctly handle markdown/ID markers
    
    source_len = len(source_text)
    
    # Scan through source looking for match
    pos = 0
    while pos < source_len:
        # Skip leading markdown/ID markers
        skip_pos = _skip_markers(source_text, pos)
        if skip_pos > pos:
            pos = skip_pos
            continue
        
        # Try to match starting from this position
        match_end = _try_match_at_position(source_text, pos, normalized_target)
        if match_end is not None:
            return (pos, match_end)
        
        pos += 1
    
    return None


def _skip_markers(text: str, pos: int) -> int:
    """Skip markdown and ID markers, returning new position."""
    while pos < len(text):
        if text[pos:pos+2] == '[[':
            end_bracket = text.find(']]', pos)
            if end_bracket != -1:
                pos = end_bracket + 2
                continue
        if text[pos:pos+2] == '**' or text[pos:pos+2] == '__':
            pos += 2
            continue
        if text[pos] == '*' and (pos == 0 or text[pos-1] != '*') and (pos + 1 >= len(text) or text[pos+1] != '*'):
            pos += 1
            continue
        break
    return pos


def _try_match_at_position(source_text: str, start_pos: int, normalized_target: str) -> int | None:
    """
    Try to match normalized_target starting at start_pos in source_text.
    Returns the end position if matched, None otherwise.
    """
    source_len = len(source_text)
    target_len = len(normalized_target)
    
    src_pos = start_pos
    target_pos = 0
    
    # Track if we're in a space sequence in target
    target_in_space = False
    
    while target_pos < target_len and src_pos < source_len:
        # Skip markers in source
        new_src_pos = _skip_markers(source_text, src_pos)
        if new_src_pos > src_pos:
            src_pos = new_src_pos
            continue
        
        if src_pos >= source_len:
            break
        
        src_char = source_text[src_pos]
        target_char = normalized_target[target_pos]
        
        # Handle whitespace matching flexibly
        if target_char == ' ':
            target_in_space = True
            target_pos += 1
            continue
        
        if target_in_space:
            # We need to consume whitespace in source
            while src_pos < source_len and source_text[src_pos].isspace():
                src_pos += 1
            # Also skip any markers
            src_pos = _skip_markers(source_text, src_pos)
            if src_pos >= source_len:
                break
            src_char = source_text[src_pos]
            target_in_space = False
        
        # Now compare non-space characters
        if src_char.isspace():
            # Source has extra whitespace, skip it
            src_pos += 1
            continue
        
        if src_char != target_char:
            # No match
            return None
        
        src_pos += 1
        target_pos += 1
    
    # Check if we matched the entire target
    if target_pos >= target_len:
        return src_pos
    
    return None


def _is_arabic_language(contract_language: str) -> bool:
    """Check if the language string indicates Arabic."""
    if not contract_language:
        return True  # Default to Arabic
    lang_lower = contract_language.lower().strip()
    return lang_lower in ('ar', 'arabic', 'ar-sa', 'ar-eg', 'ar-ae', 'العربية')


def format_confirmed_text_with_proper_structure(confirmed_text: str, contract_language: str = 'ar') -> str:
    """
    Ensures confirmed text has proper structure with clause titles on separate lines.
    Detects if clause title and body are merged and separates them.
    """
    if not confirmed_text:
        return confirmed_text
    
    # Arabic clause title patterns that should be on their own line
    arabic_clause_patterns = [
        r'^(البند\s+(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|الحادي عشر|الثاني عشر|الثالث عشر|الرابع عشر|الخامس عشر|التمهيدي|الأخير))',
        r'^(المادة\s+\d+)',
    ]
    
    # English clause title patterns
    english_clause_patterns = [
        r'^(Clause\s+\d+)',
        r'^(Article\s+\d+)',
        r'^(Section\s+\d+)',
    ]
    
    patterns = arabic_clause_patterns if _is_arabic_language(contract_language) else english_clause_patterns
    
    lines = confirmed_text.split('\n')
    formatted_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            formatted_lines.append(line)
            continue
        
        # Check if line starts with a clause title that has content merged
        matched = False
        for pattern in patterns:
            match = re.match(pattern, line_stripped)
            if match:
                title = match.group(1)
                remaining = line_stripped[len(title):].strip()
                
                # If there's content after the title (not just punctuation), separate them
                if remaining and not re.match(r'^[:؟?!\.،,]*$', remaining):
                    formatted_lines.append(title)
                    formatted_lines.append(remaining)
                    matched = True
                    break
        
        if not matched:
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)


def apply_confirmed_terms_to_text(source_text: str, confirmed_terms: dict, contract_language: str = 'ar') -> tuple[str, int, int]:
    """
    Applies all confirmed term modifications to the source text using flexible matching.
    Formats each confirmed snippet to ensure proper clause title formatting.
    
    SAFETY: First identifies all match positions in the ORIGINAL source, then applies
    replacements in reverse order (end to start) to preserve position accuracy.
    Tracks claimed spans to prevent the same text region from being matched multiple times.
    
    Args:
        source_text: The original contract text
        confirmed_terms: Dict of term_id -> term_data with original_text and confirmed_text
        contract_language: Language of the contract ('ar' or 'en')
    
    Returns:
        tuple: (modified_text, successful_replacements_count, failed_replacements_count)
    """
    if not confirmed_terms or not source_text:
        logger.warning(f"apply_confirmed_terms_to_text: Empty input - confirmed_terms: {bool(confirmed_terms)}, source_text: {bool(source_text)}")
        return source_text, 0, 0
    
    logger.info(f"apply_confirmed_terms_to_text: Processing {len(confirmed_terms)} confirmed terms")
    logger.debug(f"Source text length: {len(source_text)} chars")
    
    # Phase 1: Find all match positions in the ORIGINAL source text
    # Store as list of (start_pos, end_pos, replacement_text, term_id)
    # Track claimed intervals to avoid matching the same region twice
    replacements_to_apply = []
    claimed_intervals = []  # List of (start, end) tuples for already matched regions
    successful = 0
    failed = 0
    
    for term_id, term_data in confirmed_terms.items():
        if not isinstance(term_data, dict):
            logger.warning(f"Term {term_id}: Invalid term_data type")
            continue
        
        original_text = term_data.get("original_text", "")
        confirmed_text = term_data.get("confirmed_text", "")
        
        logger.debug(f"Term {term_id}: original={len(original_text)} chars, confirmed={len(confirmed_text)} chars")
        
        # Skip if no change needed
        if not original_text or not confirmed_text:
            logger.warning(f"Term {term_id}: Skipping - empty text")
            continue
        if original_text.strip() == confirmed_text.strip():
            logger.info(f"Term {term_id}: Skipping - texts are identical")
            continue
        
        # Format the confirmed text
        formatted_confirmed_text = format_confirmed_text_with_proper_structure(confirmed_text, contract_language)
        
        # Try to find the match position in original source, excluding claimed intervals
        match_result = _find_term_in_source_excluding(source_text, original_text, claimed_intervals)
        
        if match_result:
            start_pos, end_pos = match_result
            # Check for overlap with existing claimed intervals
            is_overlapping = any(
                not (end_pos <= claimed_start or start_pos >= claimed_end)
                for claimed_start, claimed_end in claimed_intervals
            )
            if is_overlapping:
                logger.warning(f"Term {term_id}: Found match at {start_pos}-{end_pos} but overlaps with claimed region")
                failed += 1
            else:
                claimed_intervals.append((start_pos, end_pos))
                replacements_to_apply.append((start_pos, end_pos, formatted_confirmed_text, term_id))
                successful += 1
                logger.info(f"Term {term_id}: Found match at positions {start_pos}-{end_pos}")
        else:
            failed += 1
            logger.warning(f"Term {term_id}: Original text not found in source")
    
    # Phase 2: Apply replacements in reverse order (end to start) to preserve positions
    if not replacements_to_apply:
        logger.info(f"Applied confirmed terms: 0 successful, {failed} failed")
        return source_text, 0, failed
    
    # Sort by start position descending (apply from end to start)
    replacements_to_apply.sort(key=lambda x: x[0], reverse=True)
    
    modified_text = source_text
    for start_pos, end_pos, replacement_text, term_id in replacements_to_apply:
        modified_text = modified_text[:start_pos] + replacement_text + modified_text[end_pos:]
        logger.debug(f"Applied replacement for term {term_id}")
    
    logger.info(f"Applied confirmed terms: {successful} successful, {failed} failed out of {len(confirmed_terms)} total")
    return modified_text, successful, failed


def _find_term_in_source_excluding(source_text: str, search_text: str, excluded_intervals: list) -> tuple[int, int] | None:
    """
    Find the exact span of search_text in source_text, excluding already claimed intervals.
    Tries multiple matching strategies.
    
    Args:
        source_text: The full source text to search in
        search_text: The text to find
        excluded_intervals: List of (start, end) tuples representing already claimed regions
    
    Returns (start_pos, end_pos) or None.
    """
    if not search_text or not source_text:
        return None
    
    def is_excluded(start: int, end: int) -> bool:
        """Check if a span overlaps with any excluded interval."""
        for exc_start, exc_end in excluded_intervals:
            if not (end <= exc_start or start >= exc_end):
                return True
        return False
    
    def find_all_occurrences(text: str, pattern: str) -> list:
        """Find all occurrences of pattern in text."""
        occurrences = []
        start = 0
        while True:
            idx = text.find(pattern, start)
            if idx == -1:
                break
            occurrences.append((idx, idx + len(pattern)))
            start = idx + 1
        return occurrences
    
    # Strategy 1: Exact match - find first non-excluded occurrence
    for start, end in find_all_occurrences(source_text, search_text):
        if not is_excluded(start, end):
            return (start, end)
    
    # Strategy 2: Strip and try exact match
    stripped = search_text.strip()
    if stripped != search_text:
        for start, end in find_all_occurrences(source_text, stripped):
            if not is_excluded(start, end):
                return (start, end)
    
    # Strategy 3: Remove [[ID:...]] marker and try exact match
    cleaned = re.sub(r'^\[\[ID:.*?\]\]\s*', '', search_text.strip())
    if cleaned and cleaned != stripped:
        for start, end in find_all_occurrences(source_text, cleaned):
            if not is_excluded(start, end):
                return (start, end)
    
    # Strategy 4: Use normalized matching with position mapping
    normalized_search = normalize_text_for_matching(search_text)
    if normalized_search and len(normalized_search) >= 10:
        # Try to find matches using position mapping
        search_start = 0
        while search_start < len(source_text):
            match_result = _find_match_with_position_mapping(source_text[search_start:], normalized_search)
            if match_result:
                abs_start = search_start + match_result[0]
                abs_end = search_start + match_result[1]
                if not is_excluded(abs_start, abs_end):
                    return (abs_start, abs_end)
                search_start = abs_end
            else:
                break
    
    # Strategy 5: Try with cleaned text for normalized matching
    if cleaned and cleaned != search_text.strip():
        normalized_cleaned = normalize_text_for_matching(cleaned)
        if normalized_cleaned and len(normalized_cleaned) >= 10:
            search_start = 0
            while search_start < len(source_text):
                match_result = _find_match_with_position_mapping(source_text[search_start:], normalized_cleaned)
                if match_result:
                    abs_start = search_start + match_result[0]
                    abs_end = search_start + match_result[1]
                    if not is_excluded(abs_start, abs_end):
                        return (abs_start, abs_end)
                    search_start = abs_end
                else:
                    break
    
    return None


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


class OptimizedTextMatcher:
    """
    High-performance text matcher for Arabic/English contracts.
    Uses simple string-based search with caching to avoid repeated normalization.
    Preserves all structural markers (tables, IDs) for proper alignment.
    """
    
    def __init__(self, source_text: str):
        """Initialize with source text."""
        self.source_text = source_text
        self.source_len = len(source_text)
        self._normalized_cache: dict[str, str] = {}
    
    def find_term(self, search_text: str, start_pos: int = 0) -> tuple[int, int, str] | None:
        """
        Find term in source text starting from start_pos.
        Returns (start_pos, end_pos, matched_text) or None.
        
        Uses multiple search strategies with early termination for performance.
        Constrains matches to positions >= start_pos to maintain document order.
        """
        if not search_text or not search_text.strip() or start_pos >= self.source_len:
            return None
        
        # Try exact match first
        result = self._exact_search(search_text, start_pos)
        if result:
            logger.debug(f"TextMatcher: Found exact match at pos {result[0]}")
            return result
        
        # Try without [[ID:...]] markers if present in search_text
        cleaned_search = re.sub(r'^\[\[ID:.*?\]\]\s*', '', search_text.strip())
        if cleaned_search != search_text.strip() and cleaned_search:
            result = self._exact_search(cleaned_search, start_pos)
            if result:
                logger.debug(f"TextMatcher: Found match (no ID marker) at pos {result[0]}")
                return result
        
        # Try normalized search
        result = self._normalized_search(search_text, start_pos)
        if result:
            logger.debug(f"TextMatcher: Found normalized match at pos {result[0]}")
            return result
        
        # Also try normalized search on cleaned text
        if cleaned_search != search_text.strip() and cleaned_search:
            result = self._normalized_search(cleaned_search, start_pos)
            if result:
                logger.debug(f"TextMatcher: Found normalized match (cleaned) at pos {result[0]}")
                return result
        
        # Try prefix search as fallback
        result = self._prefix_search(search_text, start_pos)
        if result:
            logger.debug(f"TextMatcher: Found prefix match at pos {result[0]}")
            return result
        
        logger.debug(f"TextMatcher: No match found starting from pos {start_pos}")
        return None
    
    def _exact_search(self, search_text: str, start_pos: int) -> tuple[int, int, str] | None:
        """Try exact string match first (fastest)."""
        idx = self.source_text.find(search_text, start_pos)
        if idx != -1:
            return (idx, idx + len(search_text), search_text)
        
        stripped = search_text.strip()
        if stripped != search_text:
            idx = self.source_text.find(stripped, start_pos)
            if idx != -1:
                return (idx, idx + len(stripped), stripped)
        
        return None
    
    def _normalized_search(self, search_text: str, start_pos: int) -> tuple[int, int, str] | None:
        """Search using normalized text comparison."""
        search_normalized = self._normalize_for_matching(search_text)
        if not search_normalized or len(search_normalized) < 10:
            return None
        
        first_word = search_normalized.split()[0] if search_normalized.split() else ""
        if not first_word or len(first_word) < 3:
            return None
        
        pos = start_pos
        max_attempts = 100
        attempts = 0
        
        while pos < self.source_len and attempts < max_attempts:
            idx = self.source_text.find(first_word, pos)
            if idx == -1:
                break
            
            chunk_len = len(search_text) + 50
            chunk = self.source_text[idx:min(idx + chunk_len, self.source_len)]
            chunk_normalized = self._normalize_for_matching(chunk)
            
            if chunk_normalized.startswith(search_normalized):
                end_pos = self._find_match_end(idx, search_text, search_normalized)
                if end_pos > idx:
                    matched = self.source_text[idx:end_pos]
                    return (idx, end_pos, matched)
            
            pos = idx + 1
            attempts += 1
        
        return None
    
    def _prefix_search(self, search_text: str, start_pos: int) -> tuple[int, int, str] | None:
        """Fallback: search using first 50 characters."""
        prefix = search_text[:50].strip() if len(search_text) > 50 else search_text.strip()
        if not prefix:
            return None
        
        idx = self.source_text.find(prefix, start_pos)
        if idx != -1:
            end_pos = idx + len(search_text)
            if end_pos > self.source_len:
                end_pos = self.source_len
            matched = self.source_text[idx:end_pos]
            return (idx, end_pos, matched)
        
        return None
    
    def _find_match_end(self, start_idx: int, original_text: str, normalized_search: str) -> int:
        """Find the end position of a match in source text."""
        base_end = start_idx + len(original_text)
        
        for offset in range(0, 40):
            test_end = base_end + offset
            if test_end > self.source_len:
                break
            
            chunk = self.source_text[start_idx:test_end]
            chunk_normalized = self._normalize_for_matching(chunk)
            
            if chunk_normalized == normalized_search:
                return test_end
        
        return min(base_end, self.source_len)
    
    def _normalize_for_matching(self, text: str) -> str:
        """Normalize text for comparison. Uses cache for efficiency."""
        if not text:
            return ""
        
        cache_key = text[:100] if len(text) > 100 else text
        if cache_key in self._normalized_cache:
            return self._normalized_cache[cache_key]
        
        result = re.sub(r'\[\[ID:.*?\]\]\s*', '', text)
        result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
        result = re.sub(r'\*([^*]+)\*', r'\1', result)
        result = re.sub(r'__([^_]+)__', r'\1', result)
        result = ' '.join(result.split())
        
        if len(self._normalized_cache) < 1000:
            self._normalized_cache[cache_key] = result
        
        return result


def create_text_matcher(source_text: str) -> OptimizedTextMatcher:
    """Factory function to create an optimized text matcher."""
    return OptimizedTextMatcher(source_text)


def fast_normalize_text(text: str) -> str:
    """Quick text normalization for comparison purposes."""
    if not text:
        return ""
    result = re.sub(r'\[\[ID:.*?\]\]\s*', '', text)
    result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
    result = re.sub(r'\*([^*]+)\*', r'\1', result)
    result = re.sub(r'__([^_]+)__', r'\1', result)
    return ' '.join(result.split()).strip()
