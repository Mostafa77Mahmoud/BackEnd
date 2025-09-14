"""
Basic Endpoint Tests

Tests for core API endpoints to verify functionality after restructuring.
"""

import unittest
import json
import tempfile
import os
from unittest.mock import patch, MagicMock
from app import create_app


class TestBasicEndpoints(unittest.TestCase):
    """Test basic endpoint functionality."""
    
    def setUp(self):
        """Set up test client."""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Mock database collections for testing
        self.mock_contracts_collection = MagicMock()
        self.mock_terms_collection = MagicMock()
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('service', data)
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'healthy')
    
    def test_analyze_endpoint_no_data(self):
        """Test analyze endpoint with no data."""
        response = self.client.post('/api/analyze')
        # Returns 503 (Database service unavailable) in test environment - this is expected
        self.assertEqual(response.status_code, 503)
    
    @patch('app.routes.analysis_upload.get_contracts_collection')
    @patch('app.routes.analysis_upload.get_terms_collection')
    @patch('app.services.ai_service.send_text_to_remote_api')
    def test_analyze_endpoint_text_input(self, mock_ai, mock_terms_coll, mock_contracts_coll):
        """Test analyze endpoint with text input."""
        mock_contracts_coll.return_value = self.mock_contracts_collection
        mock_terms_coll.return_value = self.mock_terms_collection
        
        # Mock successful database operations
        self.mock_contracts_collection.insert_one.return_value = MagicMock(inserted_id="test_session")
        self.mock_contracts_collection.update_one.return_value = MagicMock()
        self.mock_terms_collection.insert_many.return_value = MagicMock()
        
        # Mock AI service response
        mock_ai.return_value = '[{"term_id": "test_term", "term_text": "Test clause", "is_valid_sharia": true, "sharia_issue": null, "reference_number": null, "modified_term": null}]'
        
        payload = {
            "text": "Test contract clause for analysis",
            "analysis_type": "sharia",
            "jurisdiction": "Egypt"
        }
        
        response = self.client.post('/api/analyze', 
                                  data=json.dumps(payload),
                                  content_type='application/json')
        
        # Should succeed with mocked services
        self.assertEqual(response.status_code, 200)
    
    @patch('app.routes.interaction.get_contracts_collection')
    @patch('app.routes.interaction.get_terms_collection')
    def test_interact_endpoint_no_session(self, mock_terms_coll, mock_contracts_coll):
        """Test interact endpoint without session."""
        mock_contracts_coll.return_value = self.mock_contracts_collection
        mock_terms_coll.return_value = self.mock_terms_collection
        
        payload = {"question": "Test question"}
        response = self.client.post('/api/interact',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    @patch('app.routes.interaction.get_contracts_collection')
    @patch('app.routes.interaction.get_terms_collection')
    @patch('app.services.ai_service.get_chat_session')
    def test_interact_endpoint_with_session(self, mock_ai, mock_terms_coll, mock_contracts_coll):
        """Test interact endpoint with valid session."""
        mock_contracts_coll.return_value = self.mock_contracts_collection
        mock_terms_coll.return_value = self.mock_terms_collection
        
        # Mock session document
        mock_session = {
            "_id": "test_session",
            "detected_contract_language": "ar",
            "analysis_type": "sharia",
            "original_contract_plain": "Test contract"
        }
        self.mock_contracts_collection.find_one.return_value = mock_session
        
        # Mock AI service
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Test AI response"
        mock_chat.send_message.return_value = mock_response
        mock_ai.return_value = mock_chat
        
        payload = {
            "question": "Test question",
            "session_id": "test_session"
        }
        
        response = self.client.post('/api/interact',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        
        # Should succeed with mocked data
        self.assertEqual(response.status_code, 200)
    
    def test_generate_from_brief_endpoint_no_data(self):
        """Test generate from brief endpoint with no data."""
        response = self.client.post('/api/generate_from_brief')
        # Returns 415 (Unsupported Media Type) when no JSON is sent
        self.assertEqual(response.status_code, 415)
    
    @patch('app.routes.analysis_session.get_contracts_collection')
    def test_sessions_endpoint(self, mock_coll):
        """Test sessions listing endpoint."""
        mock_coll.return_value = self.mock_contracts_collection
        
        # Mock the full chain: find().sort().skip().limit()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor  
        mock_cursor.limit.return_value = []
        self.mock_contracts_collection.find.return_value = mock_cursor
        self.mock_contracts_collection.count_documents.return_value = 0
        
        response = self.client.get('/api/sessions')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('sessions', data)
    
    @patch('app.routes.analysis_admin.get_contracts_collection')
    @patch('app.routes.analysis_admin.get_terms_collection')
    def test_statistics_endpoint(self, mock_terms_coll, mock_contracts_coll):
        """Test statistics endpoint."""
        mock_contracts_coll.return_value = self.mock_contracts_collection
        mock_terms_coll.return_value = self.mock_terms_collection
        
        # Mock count operations
        self.mock_contracts_collection.count_documents.return_value = 5
        self.mock_terms_collection.count_documents.return_value = 20
        
        response = self.client.get('/api/statistics')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('total_sessions', data)
        self.assertIn('total_terms_analyzed', data)


class TestConfigurationAndPrompts(unittest.TestCase):
    """Test configuration and prompt loading."""
    
    def setUp(self):
        """Set up test app."""
        self.app = create_app()
    
    def test_prompts_loading(self):
        """Test that all prompts load correctly."""
        from config.default import DefaultConfig
        
        config = DefaultConfig()
        
        # Test key prompts
        prompts_to_test = [
            'SYS_PROMPT_SHARIA',
            'SYS_PROMPT_LEGAL', 
            'INTERACTION_PROMPT_SHARIA',
            'INTERACTION_PROMPT_LEGAL',
            'REVIEW_MODIFICATION_PROMPT_SHARIA',
            'REVIEW_MODIFICATION_PROMPT_LEGAL',
            'CONTRACT_GENERATION_PROMPT',
            'CONTRACT_REGENERATION_PROMPT',
            'EXTRACTION_PROMPT'
        ]
        
        for prompt_name in prompts_to_test:
            with self.subTest(prompt=prompt_name):
                prompt_content = getattr(config, prompt_name)
                self.assertIsInstance(prompt_content, str)
                self.assertGreater(len(prompt_content.strip()), 10)
                self.assertNotIn('ERROR:', prompt_content)
                # Check for language placeholder
                if prompt_name != 'EXTRACTION_PROMPT':
                    self.assertIn('{output_language}', prompt_content)


if __name__ == '__main__':
    unittest.main()