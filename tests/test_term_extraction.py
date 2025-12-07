"""
Test for Term Extraction JSON Validation

This test validates that the term extraction prompt produces valid JSON.
Run with: python -m pytest tests/test_term_extraction.py -v
"""

import json
import re
import pytest


def validate_json_response(response_text: str, expected_type: str = "array"):
    """Validate JSON response from model."""
    if not response_text or not response_text.strip():
        return False, None, "Empty response"
    
    cleaned = response_text.strip()
    
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    
    if expected_type == "array":
        json_match = re.search(r'\[[\s\S]*\]', cleaned)
        if json_match:
            cleaned = json_match.group(0)
    elif expected_type == "object":
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            cleaned = json_match.group(0)
    
    try:
        parsed = json.loads(cleaned)
        
        if expected_type == "array" and not isinstance(parsed, list):
            return False, None, f"Expected array, got {type(parsed).__name__}"
        if expected_type == "object" and not isinstance(parsed, dict):
            return False, None, f"Expected object, got {type(parsed).__name__}"
        
        return True, parsed, "Valid JSON"
        
    except json.JSONDecodeError as e:
        return False, None, f"JSON parse error: {e.msg}"


def validate_term_structure(term: dict):
    """Validate extracted term structure."""
    required_fields = ["term_id", "term_text"]
    
    for field in required_fields:
        if field not in term:
            return False, f"Missing required field: {field}"
        if not isinstance(term[field], str):
            return False, f"Field {field} must be string"
    
    if "potential_issues" in term:
        if not isinstance(term["potential_issues"], list):
            return False, "potential_issues must be a list"
    
    return True, "Valid term structure"


class TestTermExtractionValidation:
    """Tests for term extraction JSON validation."""
    
    def test_valid_json_array(self):
        """Test valid JSON array parsing."""
        response = '''[
            {
                "term_id": "clause_1",
                "term_text": "نص البند",
                "potential_issues": ["الربا"],
                "relevance_reason": "سبب"
            }
        ]'''
        
        is_valid, parsed, msg = validate_json_response(response, "array")
        assert is_valid is True
        assert isinstance(parsed, list)
        assert len(parsed) == 1
    
    def test_json_with_markdown_wrapper(self):
        """Test JSON wrapped in markdown code blocks."""
        response = '''```json
        [
            {
                "term_id": "clause_1",
                "term_text": "نص"
            }
        ]
        ```'''
        
        is_valid, parsed, msg = validate_json_response(response, "array")
        assert is_valid is True
        assert len(parsed) == 1
    
    def test_json_with_extra_text(self):
        """Test JSON extraction from response with extra text."""
        response = '''Here are the extracted terms:
        
        [
            {
                "term_id": "clause_1",
                "term_text": "نص البند"
            }
        ]
        
        These are the key clauses found.'''
        
        is_valid, parsed, msg = validate_json_response(response, "array")
        assert is_valid is True
        assert len(parsed) == 1
    
    def test_invalid_json(self):
        """Test invalid JSON detection."""
        response = '''[
            {
                "term_id": "clause_1"
                "term_text": "missing comma"
            }
        ]'''
        
        is_valid, parsed, msg = validate_json_response(response, "array")
        assert is_valid is False
        assert "parse error" in msg.lower()
    
    def test_empty_response(self):
        """Test empty response handling."""
        is_valid, parsed, msg = validate_json_response("", "array")
        assert is_valid is False
        assert "empty" in msg.lower()
    
    def test_valid_term_structure(self):
        """Test valid term structure validation."""
        term = {
            "term_id": "clause_1",
            "term_text": "نص البند",
            "potential_issues": ["الربا", "الغرر"],
            "relevance_reason": "سبب الأهمية"
        }
        
        is_valid, msg = validate_term_structure(term)
        assert is_valid is True
    
    def test_missing_required_field(self):
        """Test detection of missing required field."""
        term = {
            "term_id": "clause_1"
        }
        
        is_valid, msg = validate_term_structure(term)
        assert is_valid is False
        assert "term_text" in msg
    
    def test_invalid_potential_issues_type(self):
        """Test detection of invalid potential_issues type."""
        term = {
            "term_id": "clause_1",
            "term_text": "نص",
            "potential_issues": "should be array"
        }
        
        is_valid, msg = validate_term_structure(term)
        assert is_valid is False
        assert "list" in msg.lower()
    
    def test_prompt_format_escaping(self):
        """Test that prompt template properly escapes JSON example braces."""
        prompt_template = """مثال على الصيغة المطلوبة:
[
  {{
    "term_id": "clause_1",
    "term_text": "نص البند هنا"
  }}
]

نص العقد:
{contract_text}"""
        
        formatted = prompt_template.format(contract_text="عقد تجريبي")
        
        assert "عقد تجريبي" in formatted
        assert '"term_id"' in formatted
        assert "{contract_text}" not in formatted


class TestArabicTextHandling:
    """Tests for Arabic text handling in JSON."""
    
    def test_arabic_text_in_json(self):
        """Test Arabic text preservation in JSON."""
        response = '''[
            {
                "term_id": "clause_1",
                "term_text": "يتعهد الطرف الأول بدفع مبلغ مائة ألف ريال",
                "potential_issues": ["الربا", "الغرر", "الجهالة"],
                "relevance_reason": "بند مالي يحتاج مراجعة شرعية"
            }
        ]'''
        
        is_valid, parsed, msg = validate_json_response(response, "array")
        assert is_valid is True
        assert "الطرف الأول" in parsed[0]["term_text"]
        assert "الربا" in parsed[0]["potential_issues"]
    
    def test_mixed_arabic_english(self):
        """Test mixed Arabic and English content."""
        response = '''[
            {
                "term_id": "clause_riba_1",
                "term_text": "Interest rate of 5% applied - نسبة فائدة 5%",
                "potential_issues": ["الربا"],
                "relevance_reason": "Contains interest clause"
            }
        ]'''
        
        is_valid, parsed, msg = validate_json_response(response, "array")
        assert is_valid is True
        assert "5%" in parsed[0]["term_text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
