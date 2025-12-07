import time
import json
import re
from google import genai
from google.genai import types
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from flask import current_app
from app.utils.logging_utils import get_logger, mask_key, get_trace_id, RequestTimer, get_request_tracer

logger = get_logger(__name__)

FILE_SEARCH_AVAILABLE = hasattr(genai.Client, 'file_search_stores') if hasattr(genai, 'Client') else False


def check_file_search_support():
    try:
        import google.genai as genai_module
        version = getattr(genai_module, '__version__', 'unknown')
        logger.debug(f"google-genai version: {version}")
        
        if not FILE_SEARCH_AVAILABLE:
            logger.warning("File Search API not available in this version")
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking File Search support: {e}")
        return False


def validate_json_response(response_text: str, expected_type: str = "array") -> Tuple[bool, any, str]:
    if not response_text or not response_text.strip():
        return False, None, "Empty response from model"
    
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
        error_context = cleaned[max(0, e.pos - 20):e.pos + 20] if hasattr(e, 'pos') else cleaned[:50]
        return False, None, f"JSON parse error at position {e.pos}: {e.msg}. Context: ...{error_context}..."


def validate_term_structure(term: dict) -> Tuple[bool, str]:
    required_fields = ["term_id", "term_text"]
    
    for field in required_fields:
        if field not in term:
            return False, f"Missing required field: {field}"
        if not isinstance(term[field], str):
            return False, f"Field {field} must be string, got {type(term[field]).__name__}"
    
    if "potential_issues" in term:
        if not isinstance(term["potential_issues"], list):
            return False, "potential_issues must be a list"
    
    return True, "Valid term structure"


class FileSearchService:
    
    CHUNK_SCHEMA = {
        "description": "List of chunks retrieved from File Search",
        "fields": {
            "uid": "Unique chunk identifier",
            "chunk_text": "Original chunk text from document",
            "score": "Relevance score (0.0 - 1.0)",
            "uri": "File source URI",
            "title": "File or section title"
        }
    }

    def __init__(self):
        self.timer = RequestTimer()
        self.file_search_enabled = check_file_search_support()
        
        self.api_key = current_app.config.get('GEMINI_FILE_SEARCH_API_KEY') or current_app.config.get('GEMINI_API_KEY')
        if not self.api_key:
            logger.error("API key not configured for File Search")
            self.file_search_enabled = False
        
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Initialized with API Key: {mask_key(self.api_key)}")
            except Exception as e:
                logger.error(f"Failed to create GenAI client: {e}")
                self.file_search_enabled = False
        
        self.model_name = current_app.config.get('MODEL_NAME', 'gemini-2.5-flash')
        self.store_id: Optional[str] = current_app.config.get('FILE_SEARCH_STORE_ID')
        self.context_dir = "context"
        
        logger.debug(f"Model: {self.model_name}, Store ID: {self.store_id}")

    @property
    def extract_prompt_template(self):
        from config.default import DefaultConfig
        return DefaultConfig.EXTRACT_KEY_TERMS_PROMPT

    @property
    def search_prompt_template(self):
        from config.default import DefaultConfig
        return DefaultConfig.FILE_SEARCH_PROMPT

    def initialize_store(self) -> str:
        logger.info("=" * 50)
        logger.info("STORE INITIALIZATION")
        logger.info("=" * 50)

        if not self.file_search_enabled:
            raise ValueError("File Search API not available")
        
        if not self.client:
            raise ValueError("GenAI client not initialized")

        if self.store_id:
            logger.debug(f"Checking existing Store ID: {self.store_id}")
            try:
                store = self.client.file_search_stores.get(name=self.store_id)
                logger.info(f"Connected to store: '{store.display_name}'")
                return self.store_id
            except Exception as e:
                logger.warning(f"Store access failed: {e}")

        logger.info("Creating new File Search Store...")
        try:
            store = self.client.file_search_stores.create(
                config={'display_name': 'AAOIFI Reference Store'}
            )
            self.store_id = store.name
            logger.info(f"Store created: {self.store_id}")
            logger.warning(f"Save to .env: FILE_SEARCH_STORE_ID={self.store_id}")

            self._upload_context_files()

            if self.store_id is None:
                raise ValueError("Store ID was not set after creation")

            return self.store_id

        except Exception as e:
            logger.error(f"Store creation failed: {e}")
            raise

    def _upload_context_files(self):
        if not self.store_id:
            logger.error("Store ID not set, cannot upload files")
            return

        context_path = Path(current_app.root_path).parent / self.context_dir
        if not context_path.exists():
            context_path = Path(self.context_dir)

        if not context_path.exists():
            logger.warning(f"Context directory not found: {context_path}")
            context_path.mkdir(parents=True, exist_ok=True)
            return

        files = [f for f in context_path.glob("*") if f.is_file() and not f.name.startswith('.')]

        if not files:
            logger.warning(f"No files in {context_path}")
            return

        logger.info(f"Uploading {len(files)} file(s)")
        uploaded_count = 0
        
        for file_path in files:
            logger.debug(f"Uploading: {file_path.name}")
            try:
                operation = self.client.file_search_stores.upload_to_file_search_store(
                    file=str(file_path),
                    file_search_store_name=self.store_id,
                    config={'display_name': file_path.name}
                )

                while not operation.done:
                    time.sleep(2)
                    operation = self.client.operations.get(operation)

                uploaded_count += 1
                logger.debug(f"Uploaded: {file_path.name}")

            except Exception as e:
                logger.error(f"Upload failed for {file_path.name}: {e}")

        logger.info(f"Uploaded {uploaded_count}/{len(files)} files")

    def extract_key_terms(self, contract_text: str) -> List[Dict]:
        self.timer.start_step("term_extraction")
        logger.info("STEP 1: Term Extraction")
        logger.debug(f"Contract length: {len(contract_text)} chars")
        
        try:
            try:
                extraction_prompt = self.extract_prompt_template.format(contract_text=contract_text)
                logger.debug("Prompt formatted successfully")
            except KeyError as e:
                logger.error(f"Prompt format error: {e}")
                logger.warning("FALLBACK: Using simple extraction prompt due to template error")
                extraction_prompt = f"""استخرج البنود الشرعية المهمة من العقد التالي وأخرجها كـ JSON array:
[{{"term_id": "clause_1", "term_text": "...", "potential_issues": [], "relevance_reason": "..."}}]

العقد:
{contract_text[:3000]}

أخرج JSON array فقط:"""
            
            logger.debug("Calling Gemini API for extraction...")
            tracer = get_request_tracer()
            api_start_time = time.time()
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=extraction_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT"]
                )
            )
            
            api_duration = time.time() - api_start_time
            if tracer:
                tracer.record_api_call(
                    service="gemini",
                    method="extract_key_terms",
                    endpoint=f"models/{self.model_name}/generateContent",
                    request_data={"prompt_length": len(extraction_prompt)},
                    response_data={"has_candidates": hasattr(response, 'candidates') and bool(response.candidates)},
                    duration=api_duration
                )
            
            if not hasattr(response, 'candidates') or not response.candidates:
                logger.warning("FALLBACK: No candidates in response")
                self.timer.end_step()
                return []
            
            candidate = response.candidates[0]
            if not hasattr(candidate, 'content') or not candidate.content:
                logger.warning("FALLBACK: No content in response")
                self.timer.end_step()
                return []
            
            if not hasattr(candidate.content, 'parts') or not candidate.content.parts:
                logger.warning("FALLBACK: No parts in response")
                self.timer.end_step()
                return []
            
            extracted_text = candidate.content.parts[0].text if hasattr(candidate.content.parts[0], 'text') else None
            
            if not extracted_text:
                logger.warning("FALLBACK: Empty text in response")
                self.timer.end_step()
                return []
            
            logger.debug(f"Response length: {len(extracted_text)} chars")
            
            is_valid, parsed_terms, validation_msg = validate_json_response(extracted_text, "array")
            
            if not is_valid:
                logger.error(f"JSON validation failed: {validation_msg}")
                logger.warning("FALLBACK: Invalid JSON from model, will use full contract for search")
                self.timer.end_step()
                return []
            
            valid_terms = []
            for idx, term in enumerate(parsed_terms):
                is_term_valid, term_msg = validate_term_structure(term)
                if is_term_valid:
                    valid_terms.append(term)
                else:
                    logger.debug(f"Skipping invalid term {idx}: {term_msg}")
            
            logger.info(f"Extracted {len(valid_terms)} valid terms")
            self.timer.end_step()
            return valid_terms
                
        except Exception as e:
            logger.error(f"Term extraction failed: {e}")
            logger.warning("FALLBACK: Exception during extraction, will use full contract")
            self.timer.end_step()
            return []

    def _get_sensitive_keywords(self) -> List[str]:
        return [
            "الغرر", "الجهالة", "الربا", "فائدة التأخير", 
            "التعويض غير المشروع", "الشرط الباطل", "الشرط الجائر",
            "الظلم", "الإكراه", "الضرر", "الوعد الملزم"
        ]

    def _filter_sensitive_clauses(self, extracted_terms: List[Dict]) -> List[Dict]:
        sensitive_keywords = self._get_sensitive_keywords()
        sensitive_clauses = []
        
        for term in extracted_terms:
            issues = term.get("potential_issues", [])
            if any(keyword in issues for keyword in sensitive_keywords):
                sensitive_clauses.append(term)
        
        return sensitive_clauses

    def search_chunks(self, contract_text: str, top_k: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
        search_timer = RequestTimer()
        
        if not self.store_id:
            try:
                self.initialize_store()
            except Exception:
                raise ValueError("File Search Store not initialized")

        if top_k is None:
            top_k = current_app.config.get('TOP_K_CHUNKS', 10)

        logger.info("=" * 50)
        logger.info("FILE SEARCH PIPELINE START")
        logger.info("=" * 50)

        try:
            extracted_terms = self.extract_key_terms(contract_text)
            
            if not extracted_terms:
                logger.info("No terms extracted, using contract excerpt")
                extracted_clauses_text = contract_text[:2000]
            else:
                extracted_clauses_text = json.dumps(extracted_terms, ensure_ascii=False, indent=2)
            
            search_timer.start_step("general_search")
            logger.info("STEP 2: General Search")
            logger.debug(f"Using top_k={top_k}")
            
            full_prompt = self.search_prompt_template.format(extracted_clauses=extracted_clauses_text)

            logger.debug("Querying Gemini File Search...")
            tracer = get_request_tracer()
            
            max_retries = 3
            retry_count = 0
            response = None
            general_search_start = time.time()
            
            while retry_count < max_retries:
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(
                                file_search=types.FileSearch(
                                    file_search_store_names=[self.store_id],
                                    top_k=top_k
                                )
                            )],
                            response_modalities=["TEXT"]
                        )
                    )
                    break
                except Exception as e:
                    retry_count += 1
                    if "503" in str(e) or "UNAVAILABLE" in str(e):
                        logger.warning(f"Retry {retry_count}/{max_retries} due to 503")
                        if retry_count < max_retries:
                            time.sleep(2 ** retry_count)
                        else:
                            raise
                    else:
                        raise

            general_search_duration = time.time() - general_search_start
            general_chunks = self._extract_grounding_chunks(response, top_k)
            
            if tracer:
                tracer.record_api_call(
                    service="gemini_file_search",
                    method="general_search",
                    endpoint=f"models/{self.model_name}/generateContent",
                    request_data={"prompt_length": len(full_prompt), "top_k": top_k, "store_id": self.store_id},
                    response_data={"chunks_count": len(general_chunks), "retries": retry_count},
                    duration=general_search_duration
                )
            logger.info(f"General search: {len(general_chunks)} chunks")
            search_timer.end_step()
            
            sensitive_chunks = []
            
            if extracted_terms:
                sensitive_clauses = self._filter_sensitive_clauses(extracted_terms)
                
                if sensitive_clauses:
                    search_timer.start_step("sensitive_search")
                    logger.info(f"STEP 3: Sensitive Search ({len(sensitive_clauses)} clauses)")
                    
                    for sensitive_clause in sensitive_clauses:
                        clause_id = sensitive_clause.get("term_id", "unknown")
                        clause_text = sensitive_clause.get("term_text", "")
                        issues = sensitive_clause.get("potential_issues", [])
                        
                        logger.debug(f"Processing: {clause_id}")
                        
                        sensitive_search_prompt = """قم بالبحث الدقيق والعميق في معايير AAOIFI عن المقاطع التي تتعلق مباشرة بالمشاكل الشرعية التالية:

مشاكل شرعية:
{issues}

نص البند من العقد:
{clause_text}

ابحث عن:
1. المعايير الشرعية الدقيقة.
2. النصوص التي تحتوي على كلمات حاسمة: "لا يجوز"، "محرم"، "يبطل".
3. أمثلة على حالات مشابهة.

ركز على الدقة الشرعية العالية.""".format(
                            issues="\n".join(issues),
                            clause_text=clause_text
                        )
                        
                        max_retries_sensitive = 3
                        retry_count_sensitive = 0
                        sensitive_response = None
                        sensitive_search_start = time.time()
                        
                        while retry_count_sensitive < max_retries_sensitive:
                            try:
                                sensitive_response = self.client.models.generate_content(
                                    model=self.model_name,
                                    contents=sensitive_search_prompt,
                                    config=types.GenerateContentConfig(
                                        tools=[types.Tool(
                                            file_search=types.FileSearch(
                                                file_search_store_names=[self.store_id],
                                                top_k=2
                                            )
                                        )],
                                        response_modalities=["TEXT"]
                                    )
                                )
                                break
                            except Exception as e:
                                retry_count_sensitive += 1
                                if "503" in str(e) or "UNAVAILABLE" in str(e):
                                    time.sleep(2 ** retry_count_sensitive)
                                else:
                                    break
                        
                        sensitive_search_duration = time.time() - sensitive_search_start
                        
                        if sensitive_response:
                            clause_chunks = self._extract_grounding_chunks(sensitive_response, 2)
                            sensitive_chunks.extend(clause_chunks)
                            logger.debug(f"Sensitive search for {clause_id}: {len(clause_chunks)} chunks")
                            
                            if tracer:
                                tracer.record_api_call(
                                    service="gemini_file_search",
                                    method="sensitive_search",
                                    endpoint=f"models/{self.model_name}/generateContent",
                                    request_data={"clause_id": clause_id, "issues": issues, "top_k": 2},
                                    response_data={"chunks_count": len(clause_chunks), "retries": retry_count_sensitive},
                                    duration=sensitive_search_duration
                                )
                    
                    search_timer.end_step()
                else:
                    logger.info("STEP 3: No sensitive clauses, skipping")
            
            search_timer.start_step("merge_results")
            logger.info("STEP 4: Merging Results")
            
            chunk_dict = {}
            
            for chunk in general_chunks:
                chunk_text = chunk.get("chunk_text", "")
                if chunk_text and chunk_text not in chunk_dict:
                    chunk_dict[chunk_text] = chunk
            
            for chunk in sensitive_chunks:
                chunk_text = chunk.get("chunk_text", "")
                if chunk_text and chunk_text not in chunk_dict:
                    chunk_dict[chunk_text] = chunk
            
            all_chunks = list(chunk_dict.values())
            
            for idx, chunk in enumerate(all_chunks):
                chunk["uid"] = f"chunk_{idx + 1}"
            
            search_timer.end_step()
            
            timing = search_timer.get_summary()
            logger.info(f"Total unique chunks: {len(all_chunks)}")
            logger.info(f"Pipeline time: {timing['total_time_seconds']}s")
            logger.info("=" * 50)
            logger.info("FILE SEARCH PIPELINE COMPLETE")
            logger.info("=" * 50)
            
            return all_chunks, extracted_terms

        except Exception as e:
            logger.error(f"Search pipeline failed: {e}")
            raise

    def _extract_grounding_chunks(self, response, top_k: int) -> List[Dict]:
        chunks = []

        if not hasattr(response, 'candidates') or not response.candidates:
            return chunks

        candidate = response.candidates[0]

        if not hasattr(candidate, 'grounding_metadata'):
            return chunks

        grounding = candidate.grounding_metadata
        
        if grounding is None:
            return chunks
        
        if hasattr(grounding, 'grounding_chunks') and grounding.grounding_chunks:
            for idx, chunk in enumerate(grounding.grounding_chunks):
                if idx >= top_k:
                    break

                chunk_data = {
                    "uid": f"chunk_{idx + 1}",
                    "chunk_text": "",
                    "score": 1.0 - (idx * 0.05),
                    "uri": None,
                    "title": None
                }

                if hasattr(chunk, 'retrieved_context') and chunk.retrieved_context:
                    retrieved = chunk.retrieved_context
                    if hasattr(retrieved, 'text'):
                        chunk_data["chunk_text"] = retrieved.text
                    if hasattr(retrieved, 'uri'):
                        chunk_data["uri"] = retrieved.uri
                    if hasattr(retrieved, 'title'):
                        chunk_data["title"] = retrieved.title

                if chunk_data["chunk_text"]:
                    chunks.append(chunk_data)

            if chunks:
                return chunks

        if hasattr(grounding, 'grounding_supports') and grounding.grounding_supports:
            for idx, support in enumerate(grounding.grounding_supports):
                if idx >= top_k:
                    break

                chunk_data = {
                    "uid": f"support_{idx + 1}",
                    "chunk_text": "",
                    "score": 0.0,
                    "uri": None,
                    "title": "Generated Summary"
                }

                if hasattr(support, 'segment') and support.segment:
                    if hasattr(support.segment, 'text'):
                        chunk_data["chunk_text"] = support.segment.text

                if hasattr(support, 'confidence_scores') and support.confidence_scores:
                    chunk_data["score"] = float(support.confidence_scores[0])

                if chunk_data["chunk_text"]:
                    chunks.append(chunk_data)

        return chunks

    def get_store_info(self) -> Dict:
        if not self.store_id:
            return {
                "status": "not_initialized",
                "store_id": None,
                "message": "Store not initialized"
            }

        try:
            store = self.client.file_search_stores.get(name=self.store_id)
            return {
                "status": "active",
                "store_id": self.store_id,
                "display_name": store.display_name if hasattr(store, 'display_name') else "Unknown",
                "message": "Store is ready"
            }
        except Exception as e:
            return {
                "status": "error",
                "store_id": self.store_id,
                "message": f"Error accessing store: {str(e)}"
            }
