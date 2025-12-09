"""
AI Service for Google Generative AI integration.
Refactored to use the new google-genai SDK while maintaining compatibility with old patterns.
"""

import pathlib
import time
import traceback
import json
import logging
from flask import current_app
from google import genai
from google.genai import types
from app.utils.logging_utils import get_request_tracer

logger = logging.getLogger(__name__)

chat_sessions = {}
_clients = {}

def init_ai_service(app):
    """Initialize AI service with configuration."""
    try:
        gemini_api_key = app.config.get('GEMINI_API_KEY')
        gemini_file_search_key = app.config.get('GEMINI_FILE_SEARCH_API_KEY')
        
        if not gemini_api_key:
            logger.warning("GEMINI_API_KEY not configured - AI analysis services will be unavailable")
        else:
            logger.info(f"GEMINI_API_KEY configured: {mask_key(gemini_api_key)}")
            
        if not gemini_file_search_key:
            logger.warning("GEMINI_FILE_SEARCH_API_KEY not configured - File Search will be unavailable")
        else:
            logger.info(f"GEMINI_FILE_SEARCH_API_KEY configured: {mask_key(gemini_file_search_key)}")
            
        logger.info("Google GenAI service initialized (client will be created per request)")
    except Exception as e:
        logger.error(f"Error initializing Google GenAI service: {e}")
        traceback.print_exc()

def mask_key(key):
    """Mask API key for logging."""
    if not key:
        return "None"
    return f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"

def get_client():
    """Get a configured GenAI client for analysis, extraction and interaction."""
    import os
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured - required for AI analysis services")
    
    logger.info(f"Creating GenAI client with API Key: {mask_key(api_key)}")
    
    # Temporarily unset GOOGLE_API_KEY to prevent library auto-detection conflict
    original_google_key = os.environ.pop('GOOGLE_API_KEY', None)
    try:
        client = genai.Client(api_key=api_key)
    finally:
        # Restore GOOGLE_API_KEY if it was set
        if original_google_key is not None:
            os.environ['GOOGLE_API_KEY'] = original_google_key
    
    return client

def get_thinking_config():
    """Get thinking mode configuration for Gemini 2.5+ models."""
    enable_thinking = current_app.config.get('ENABLE_THINKING_MODE', True)
    
    if not enable_thinking:
        logger.info("Thinking mode DISABLED")
        return None
    
    thinking_budget = current_app.config.get('THINKING_BUDGET', 4096)
    include_summary = current_app.config.get('INCLUDE_THINKING_SUMMARY', False)
    
    logger.info(f"Thinking mode ENABLED: budget={thinking_budget} tokens, include_summary={include_summary}")
    
    return types.ThinkingConfig(
        thinking_budget=thinking_budget,
        include_thoughts=include_summary
    )

def get_chat_session(session_id_key: str, system_instruction: str | None = None, force_new: bool = False):
    """Get or create a chat session for AI interactions with thinking mode enabled."""
    global chat_sessions, _clients
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
            _clients[session_id_key] = client
            
            thinking_config = get_thinking_config()
            
            config = types.GenerateContentConfig(
                temperature=temperature,
                thinking_config=thinking_config,
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                ],
                system_instruction=system_instruction
            )
            
            logger.info(f"Chat session config: model={model_name}, temperature={temperature}, thinking={'enabled' if thinking_config else 'disabled'}")
            
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
    """
    Send text to AI API for processing.
    Matches the interface of old remote_api.py send_text_to_remote_api function.
    """
    if not text_payload or not text_payload.strip():
        logger.warning(f"Empty text_payload for session_id_key {session_id_key}")
        return ""

    logger.info(f"Sending text to LLM for session: {session_id_key}, payload length: {len(text_payload)}, system prompt length: {len(formatted_system_prompt) if formatted_system_prompt else 0}")
    
    try:
        chat = get_chat_session(session_id_key, system_instruction=formatted_system_prompt, force_new=True)
        
        max_retries = 3
        retry_delay = 5
        
        tracer = get_request_tracer()
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending request to AI API (attempt {attempt + 1}/{max_retries})")
                api_start_time = time.time()
                response = chat.send_message(text_payload)
                api_duration = time.time() - api_start_time
                
                token_usage = {}
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    token_usage = {
                        "input_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                        "output_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
                        "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0)
                    }
                    logger.info(f"Token usage for session {session_id_key}: input={token_usage['input_tokens']}, output={token_usage['output_tokens']}, total={token_usage['total_tokens']}")
                
                if tracer:
                    tracer.record_api_call(
                        service="gemini_chat",
                        method="send_message",
                        endpoint="chat.send_message",
                        request_data={"session_id": session_id_key, "payload_length": len(text_payload), "attempt": attempt + 1},
                        response_data={"response_length": len(response.text) if response.text else 0, "has_text": bool(response.text), "token_usage": token_usage},
                        duration=api_duration
                    )
                
                if not response.text:
                    if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                        block_reason = getattr(response.prompt_feedback, 'block_reason', None)
                        if block_reason:
                            block_reason_msg = f"Prompt blocked for session {session_id_key}. Reason: {block_reason}"
                            logger.warning(block_reason_msg)
                            return f"ERROR_PROMPT_BLOCKED: {block_reason}"
                    
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        finish_reason = getattr(candidate, 'finish_reason', None)
                        if finish_reason and str(finish_reason) != "STOP":
                            block_reason_msg = f"Content possibly blocked/filtered for session {session_id_key}. Finish Reason: {finish_reason}"
                            logger.warning(block_reason_msg)
                            if str(finish_reason) == "SAFETY":
                                return f"ERROR_CONTENT_BLOCKED_SAFETY: {finish_reason}"
                            return f"ERROR_CONTENT_BLOCKED: {finish_reason}"
                    
                    logger.warning(f"Received empty text response from API for session {session_id_key} on attempt {attempt + 1}")
                    if attempt == max_retries - 1:
                        logger.error(f"All retries resulted in empty response for {session_id_key}.")
                        return ""
                else:
                    logger.info(f"Received successful response for session {session_id_key}. Response text length: {len(response.text)}")
                    return response.text
                    
            except Exception as e_inner:
                logger.error(f"Attempt {attempt + 1} failed for send_message to API for session {session_id_key}: {e_inner}")
                traceback.print_exc()
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds for session {session_id_key}...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"All retries failed for session {session_id_key}.")
                    raise
        
        return ""

    except Exception as e:
        logger.error(f"General error during text sending to API for session {session_id_key}: {e}")
        traceback.print_exc()
        raise Exception(f"فشل في استدعاء API للنموذج: {e}")

def extract_text_from_file(file_path: str) -> str | None:
    """
    Extract text from PDF/TXT files using AI.
    Matches the interface of old remote_api.py extract_text_from_file function.
    """
    path_obj = pathlib.Path(file_path)
    ext = path_obj.suffix.lower()

    if ext not in [".pdf", ".txt"]:
        logger.warning(f"Unsupported file type for extraction: {ext}")
        return None
        
    try:
        logger.info(f"Extracting text from file: {file_path}")
        
        from config.default import DefaultConfig
        extraction_prompt = DefaultConfig.EXTRACTION_PROMPT
            
        client = get_client()
        model_name = current_app.config.get('MODEL_NAME', 'gemini-2.5-flash')
        
        file_data = path_obj.read_bytes()
        mime_type = "application/pdf" if ext == ".pdf" else "text/plain"
        
        max_retries = 2
        retry_delay = 3
        tracer = get_request_tracer()
        
        for attempt in range(max_retries):
            try:
                api_start_time = time.time()
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=file_data, mime_type=mime_type),
                        extraction_prompt
                    ]
                )
                api_duration = time.time() - api_start_time
                
                token_usage = {}
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    token_usage = {
                        "input_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                        "output_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
                        "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0)
                    }
                    logger.info(f"Token usage for file extraction {file_path}: input={token_usage['input_tokens']}, output={token_usage['output_tokens']}, total={token_usage['total_tokens']}")
                
                if tracer:
                    tracer.record_api_call(
                        service="gemini",
                        method="extract_text_from_file",
                        endpoint=f"models/{model_name}/generateContent",
                        request_data={"file_path": file_path, "mime_type": mime_type, "file_size": len(file_data), "attempt": attempt + 1},
                        response_data={"response_length": len(response.text) if response and response.text else 0, "has_text": bool(response and response.text), "token_usage": token_usage},
                        duration=api_duration
                    )
                
                if response and response.text:
                    logger.info(f"Successfully extracted text from {file_path}. Text length: {len(response.text)}")
                    return response.text
                    
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    block_reason = getattr(response.prompt_feedback, 'block_reason', None)
                    if block_reason:
                        logger.warning(f"Extraction prompt blocked for {file_path}. Reason: {block_reason}")
                        return None
                
                logger.warning(f"Empty text from extraction for {file_path} on attempt {attempt + 1}")
                if attempt == max_retries - 1:
                    logger.error(f"All retries failed to extract text from {file_path}.")
                    return None
                    
            except Exception as e_inner:
                logger.error(f"Attempt {attempt + 1} failed for extraction of {file_path}: {e_inner}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying extraction for {file_path} in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    traceback.print_exc()
                    logger.error(f"Failed extraction for {file_path} after all retries.")
                    return None
                    
        return None
        
    except Exception as e:
        logger.error(f"General error during text extraction from file {file_path}: {e}")
        traceback.print_exc()
        return None

def send_file_to_remote_api(file_path: str, session_id=None, output_language='ar'):
    """
    Send file to AI API for analysis.
    Matches the interface of old remote_api.py send_file_to_remote_api function.
    """
    path_obj = pathlib.Path(file_path)
    ext = path_obj.suffix.lower()

    if ext not in [".pdf", ".txt"]:
        logger.error(f"Unsupported file type in send_file_to_remote_api: {ext}")
        return json.dumps({"error": "نوع ملف غير مدعوم"}), None

    extracted_markdown = extract_text_from_file(file_path)

    if extracted_markdown is None:
         logger.error(f"Text extraction failed for file: {file_path}")
         return json.dumps({"error": "فشل استخلاص النص من الملف"}), None
    elif not extracted_markdown.strip():
         logger.warning(f"Extracted text from file is empty: {file_path}")
         return "[]", ""

    try:
        from config.default import DefaultConfig
        sys_prompt_template = DefaultConfig.SYS_PROMPT
        
        logger.info(f"Analyzing extracted content from file {file_path} for session: {session_id or 'default'}")
        formatted_sys_prompt = sys_prompt_template.format(output_language=output_language)
        
        analysis_response_text = send_text_to_remote_api(
            text_payload=extracted_markdown, 
            session_id_key=f"{session_id}_analysis_file", 
            formatted_system_prompt=formatted_sys_prompt
        )
        logger.info(f"Analysis complete for file {file_path}, session {session_id or 'default'}")
        return analysis_response_text, extracted_markdown
    except Exception as e:
        logger.error(f"Analysis step failed after extraction for session {session_id or 'default'} for file {file_path}: {e}")
        traceback.print_exc()
        return json.dumps({"error": f"فشل استدعاء API للتحليل: {str(e)}"}), extracted_markdown
