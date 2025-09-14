# NOTE: shim — kept for backward compatibility
# All functionality moved to app/services/ai_service.py

from app.services.ai_service import get_chat_session, send_text_to_remote_api, extract_text_from_file

__all__ = ['get_chat_session', 'send_text_to_remote_api', 'extract_text_from_file']