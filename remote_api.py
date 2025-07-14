# --- START OF MODIFIED FILE remote_api.py ---

import pathlib
import google.generativeai as genai
from config import (
    GOOGLE_API_KEY,
    MODEL_NAME,
    TEMPERATURE,
    EXTRACTION_PROMPT, 
    SYS_PROMPT # Will be formatted in api_server.py
)
import time
import traceback
import json # For error responses

try:
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    print(f"ERROR: خطأ في تهيئة Google Generative AI: {e}")
    traceback.print_exc()

chat_sessions = {} 

def get_chat_session(session_id_key: str, system_instruction: str | None = None, force_new: bool = False):
    global chat_sessions
    session_id_key = session_id_key or "default_chat_session_key"

    if force_new or session_id_key not in chat_sessions:
        if force_new and session_id_key in chat_sessions:
            print(f"Forcing new chat session for key (was existing): {session_id_key}")
        else:
            print(f"Creating new chat session for key: {session_id_key}")
        try:
            generation_config = genai.GenerationConfig(temperature=TEMPERATURE)
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            model = genai.GenerativeModel(
                MODEL_NAME,
                generation_config=generation_config,
                system_instruction=system_instruction, 
                safety_settings=safety_settings
            )
            chat_sessions[session_id_key] = model.start_chat(history=[]) 
        except Exception as e:
            print(f"ERROR: فشل في إنشاء GenerativeModel أو بدء الدردشة للجلسة {session_id_key}: {e}")
            traceback.print_exc()
            raise Exception(f"فشل في بدء جلسة الدردشة مع النموذج: {e}")
    return chat_sessions[session_id_key]

def send_text_to_remote_api(text_payload: str, session_id_key: str, formatted_system_prompt: str):
    if not text_payload or not text_payload.strip():
        print(f"Warning: Empty text_payload for session_id_key {session_id_key}.")
        return "" 

    try:
        chat = get_chat_session(session_id_key, system_instruction=formatted_system_prompt, force_new=True)
        
        max_retries = 3
        retry_delay = 5  
        for attempt in range(max_retries):
            try:
                # print(f"--- Sending to LLM (Attempt {attempt+1}, Session Key: {session_id_key}) ---")
                # print(f"System Prompt Used (first 200 chars): {formatted_system_prompt[:200]}...") 
                # print(f"Payload (first 200 chars): {text_payload[:200]}...")
                
                response = chat.send_message(text_payload)
                
                # print(f"LLM Response Text (first 200 chars): {response.text[:200] if response.text else 'EMPTY'}")
                # print(f"LLM Response Prompt Feedback: {response.prompt_feedback}")
                # if response.candidates:
                #     print(f"LLM Response Candidate Finish Reason: {response.candidates[0].finish_reason}")
                #     print(f"LLM Response Candidate Safety Ratings: {response.candidates[0].safety_ratings}")

                if not response.text: 
                    if response.prompt_feedback and response.prompt_feedback.block_reason:
                        block_reason_msg = f"Prompt blocked for session {session_id_key}. Reason: {response.prompt_feedback.block_reason}"
                        print(f"Warning: {block_reason_msg}")
                        return f"ERROR_PROMPT_BLOCKED: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"
                    
                    if response.candidates and response.candidates[0].finish_reason.name != "STOP": 
                        candidate = response.candidates[0]
                        block_reason_msg = f"Content possibly blocked/filtered for session {session_id_key}. Candidate Finish Reason: {candidate.finish_reason.name}"
                        print(f"Warning: {block_reason_msg}")
                        if candidate.safety_ratings:
                            for rating in candidate.safety_ratings:
                                print(f"Safety Rating: {rating.category.name} - {rating.probability.name}")
                        if candidate.finish_reason.name == "SAFETY":
                             return f"ERROR_CONTENT_BLOCKED_SAFETY: {candidate.finish_reason.name}"
                        return f"ERROR_CONTENT_BLOCKED: {candidate.finish_reason.name}" 
                    
                    print(f"Warning: Received empty text response from API for session {session_id_key} on attempt {attempt + 1}, but no explicit block reason found.")
                    if attempt == max_retries - 1: 
                        print(f"All retries resulted in empty response for {session_id_key}.")
                        return "" 
                else:
                    return response.text 
            
            except Exception as e_inner:
                print(f"ERROR: Attempt {attempt + 1} failed for send_message to API for session {session_id_key}: {e_inner}")
                traceback.print_exc()
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2 
                else:
                    print(f"ERROR: All retries failed for session {session_id_key}.")
                    raise 
        
        return "" 

    except Exception as e:
        print(f"ERROR: خطأ عام أثناء إرسال النص إلى API للنموذج للجلسة {session_id_key}: {e}")
        traceback.print_exc()
        raise Exception(f"فشل في استدعاء API للنموذج: {e}")


def extract_text_from_file(file_path: str) -> str | None:
    path_obj = pathlib.Path(file_path)
    ext = path_obj.suffix.lower()

    if ext not in [".pdf", ".txt"]:
        print(f"Warning: نوع ملف غير مدعوم للاستخلاص: {ext}")
        return None
    try:
        file_data = path_obj.read_bytes()
        mime_type = "application/pdf" if ext == ".pdf" else "text/plain"
        file_part = {"data": file_data, "mime_type": mime_type}

        generation_config = genai.GenerationConfig(temperature=0.0) 
        safety_settings = [ 
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        model = genai.GenerativeModel(MODEL_NAME, generation_config=generation_config, safety_settings=safety_settings)
        
        max_retries = 2
        retry_delay = 3
        for attempt in range(max_retries):
            try:
                response = model.generate_content(contents=[file_part, EXTRACTION_PROMPT])
                if response.text:
                    return response.text
                elif response.prompt_feedback and response.prompt_feedback.block_reason:
                    print(f"Extraction prompt blocked for {file_path}. Reason: {response.prompt_feedback.block_reason}")
                    return None 
                
                if response.candidates and response.candidates[0].finish_reason.name != "STOP":
                    print(f"Extraction content possibly blocked for {file_path}. Reason: {response.candidates[0].finish_reason.name}")
                    return None

                print(f"Warning: Empty text from extraction for {file_path} on attempt {attempt + 1}")
                if attempt == max_retries -1: return None
            except Exception as e_inner:
                print(f"ERROR: Attempt {attempt + 1} failed for extraction of {file_path}: {e_inner}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *=2
                else:
                    traceback.print_exc()
                    return None 
        return None
    except Exception as e:
        print(f"ERROR: خطأ أثناء استخلاص النص من الملف {file_path}: {e}")
        traceback.print_exc()
        return None

def send_file_to_remote_api(file_path: str, session_id=None, output_language='ar'):
    path_obj = pathlib.Path(file_path)
    ext = path_obj.suffix.lower()

    if ext not in [".pdf", ".txt"]:
        print(f"ERROR: نوع ملف غير مدعوم في send_file_to_remote_api: {ext}")
        return json.dumps({"error": "نوع ملف غير مدعوم"}), None

    extracted_markdown = extract_text_from_file(file_path)

    if extracted_markdown is None:
         return json.dumps({"error": "فشل استخلاص النص من الملف"}), None
    elif not extracted_markdown.strip():
         print(f"Warning: النص المستخرج من الملف فارغ: {file_path}")
         return "[]", "" # Return empty JSON list for analysis, and empty markdown

    try:
        # SYS_PROMPT is imported from config and is the full template string
        formatted_sys_prompt = SYS_PROMPT.format(output_language=output_language)
        
        analysis_response_text = send_text_to_remote_api(
            text_payload=extracted_markdown, 
            session_id_key=f"{session_id}_analysis_file", 
            formatted_system_prompt=formatted_sys_prompt
        )
        return analysis_response_text, extracted_markdown
    except Exception as e:
        print(f"ERROR: فشلت خطوة التحليل بعد الاستخلاص للجلسة {session_id}: {e}")
        traceback.print_exc()
        return json.dumps({"error": f"فشل استدعاء API للتحليل: {str(e)}"}), extracted_markdown

# --- END OF MODIFIED FILE remote_api.py ---