"""
AI Service for Google Generative AI integration.
Refactored to use the new google-genai SDK.
"""

import pathlib
import time
import traceback
import json
import logging
from flask import current_app
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Global chat sessions storage
chat_sessions = {}

def init_ai_service(app):
    """Initialize AI service with configuration."""
    try:
        google_api_key = app.config.get('GOOGLE_API_KEY')
        gemini_api_key = app.config.get('GEMINI_API_KEY')
        
        if not google_api_key and not gemini_api_key:
            logger.warning("GOOGLE_API_KEY/GEMINI_API_KEY not configured - AI services will be unavailable")
            return
            
        logger.info("Google GenAI service initialized (client will be created per request)")
    except Exception as e:
        logger.error(f"Error initializing Google GenAI service: {e}")
        traceback.print_exc()

from app.utils.logging_utils import mask_key

def get_client():
    """Get a configured GenAI client."""
    api_key = current_app.config.get('GEMINI_API_KEY') or current_app.config.get('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("API Key not configured")
    
    # Log key usage (masked)
    logger.info(f"Creating GenAI client with API Key: {mask_key(api_key)}")
    
    return genai.Client(api_key=api_key)

def get_chat_session(session_id_key: str, system_instruction: str | None = None, force_new: bool = False):
    """Get or create a chat session for AI interactions."""
    global chat_sessions
    session_id_key = session_id_key or "default_chat_session_key"

    if force_new or session_id_key not in chat_sessions:
        if force_new and session_id_key in chat_sessions:
            logger.info(f"Forcing new chat session for key (was existing): {session_id_key}")
        else:
            logger.info(f"Creating new chat session for key: {session_id_key}")
        try:
            model_name = current_app.config.get('MODEL_NAME', 'gemini-2.5-flash')
            temperature = current_app.config.get('TEMPERATURE', 0)
            
            client = get_client()
            
            config = types.GenerateContentConfig(
                temperature=temperature,
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                ],
                system_instruction=system_instruction
            )
            
            chat = client.chats.create(
                model=model_name,
                config=config,
                history=[]
            )
            chat_sessions[session_id_key] = chat
            
        except Exception as e:
            logger.error(f"Failed to create chat session {session_id_key}: {e}")
            traceback.print_exc()
            raise Exception(f"فشل في بدء جلسة الدردشة مع النموذج: {e}")
            
    return chat_sessions[session_id_key]

def send_text_to_remote_api(text_payload: str, session_id_key: str, formatted_system_prompt: str):
    """Send text to AI API for processing."""
    if not text_payload or not text_payload.strip():
        logger.warning(f"Empty text_payload for session_id_key {session_id_key}")
        return ""

    logger.info(f"Sending text to LLM for session: {session_id_key}, payload length: {len(text_payload)}")
    
    try:
        chat = get_chat_session(session_id_key, system_instruction=formatted_system_prompt, force_new=True)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending request to AI API (attempt {attempt + 1}/{max_retries})")
                response = chat.send_message(text_payload)
                
                if response and response.text:
                    logger.info(f"Received response from AI API: {len(response.text)} characters")
                    return response.text
                else:
                    logger.warning(f"Empty response from AI API on attempt {attempt + 1}")
                    
            except Exception as e:
                logger.error(f"AI API request failed on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
        
        return "ERROR_API_FAILED"
        
    except Exception as e:
        logger.error(f"Critical error in AI API communication: {e}")
        traceback.print_exc()
        return f"ERROR_API_COMMUNICATION: {str(e)}"

def extract_text_from_file(file_path: str):
    """Extract text from PDF/TXT files using AI."""
    try:
        logger.info(f"Extracting text from file: {file_path}")
        
        extraction_prompt = current_app.config.get('EXTRACTION_PROMPT', 
            "Extract the full text from the provided file with high accuracy. Use **Markdown** format to preserve structure.")
            
        client = get_client()
        
        # Upload file to AI service
        # Note: google-genai uses client.files.upload
        file_path_obj = pathlib.Path(file_path)
        sample_file = client.files.upload(path=file_path_obj, config={'display_name': "Contract Document"})
        logger.info(f"File uploaded to AI service: {sample_file.name}")
        
        # Wait for file to be active (if needed, though usually fast for small files)
        # For PDF extraction, we might need to wait? 
        # The new SDK handles this usually, but let's be safe if it's large.
        # But for now, standard generate_content.
        
        model_name = current_app.config.get('MODEL_NAME', 'gemini-2.5-flash')
        
        response = client.models.generate_content(
            model=model_name,
            contents=[sample_file, extraction_prompt]
        )
        
        if response and response.text:
            logger.info(f"Text extraction completed: {len(response.text)} characters")
            return response.text
        else:
            logger.error("No text extracted from file")
            return None
            
    except Exception as e:
        logger.error(f"Text extraction failed for {file_path}: {e}")
        traceback.print_exc()
        return None