import time
import json
import re
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def is_retryable_error(error: Exception) -> bool:
    error_str = str(error).lower()
    retryable_patterns = [
        "503", "unavailable", "service unavailable",
        "429", "rate limit", "quota exceeded", "resource exhausted",
        "500", "internal server error",
        "timeout", "timed out", "deadline exceeded",
        "connection", "network", "socket"
    ]
    return any(pattern in error_str for pattern in retryable_patterns)


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
    
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_BASE_DELAY = 2
    
    _terms_cache: Dict[str, List[Dict]] = {}
    _cache_max_size: int = 100

    def __init__(self):
        self.timer = RequestTimer()
        self.file_search_enabled = check_file_search_support()
        
        self.api_key = current_app.config.get('GEMINI_FILE_SEARCH_API_KEY')
        if not self.api_key:
            logger.warning("GEMINI_FILE_SEARCH_API_KEY not configured - File Search service will be unavailable")
            logger.warning("Please set GEMINI_FILE_SEARCH_API_KEY in secrets for dedicated file search")
            self.file_search_enabled = False
        
        self.client = None
        if self.api_key:
            try:
                import os
                # Temporarily unset GOOGLE_API_KEY to prevent library auto-detection conflict
                original_google_key = os.environ.pop('GOOGLE_API_KEY', None)
                try:
                    self.client = genai.Client(api_key=self.api_key)
                finally:
                    # Restore GOOGLE_API_KEY if it was set
                    if original_google_key is not None:
                        os.environ['GOOGLE_API_KEY'] = original_google_key
                logger.info(f"File Search initialized with dedicated API Key: {mask_key(self.api_key)}")
            except Exception as e:
                logger.error(f"Failed to create GenAI client for File Search: {e}")
                self.file_search_enabled = False
        
        self.model_name = current_app.config.get('MODEL_NAME', 'gemini-2.5-flash')
        self.store_id: Optional[str] = current_app.config.get('FILE_SEARCH_STORE_ID')
        self.context_dir = "context"
        self.temperature = current_app.config.get('TEMPERATURE', 0)
        self.top_k_general = current_app.config.get('TOP_K_CHUNKS', 15)
        self.top_k_sensitive = current_app.config.get('TOP_K_SENSITIVE', 5)
        
        # Sensitive search rate limiting settings
        self.enable_sensitive_search = current_app.config.get('ENABLE_SENSITIVE_SEARCH', True)
        self.sensitive_search_max_workers = current_app.config.get('SENSITIVE_SEARCH_MAX_WORKERS', 2)
        self.sensitive_search_delay = current_app.config.get('SENSITIVE_SEARCH_DELAY', 1.0)
        
        logger.debug(f"Model: {self.model_name}, Store ID: {self.store_id}, Temperature: {self.temperature}")
        logger.debug(f"Sensitive search: enabled={self.enable_sensitive_search}, workers={self.sensitive_search_max_workers}, delay={self.sensitive_search_delay}s")

    @property
    def extract_prompt_template(self):
        from config.default import DefaultConfig
        return DefaultConfig.EXTRACT_KEY_TERMS_PROMPT

    @property
    def search_prompt_template(self):
        from config.default import DefaultConfig
        return DefaultConfig.FILE_SEARCH_PROMPT

    def _get_contract_hash(self, contract_text: str) -> str:
        normalized = ' '.join(contract_text.split()).strip()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:32]

    def _get_cached_terms(self, contract_hash: str) -> Optional[List[Dict]]:
        if contract_hash in self._terms_cache:
            logger.debug(f"Cache HIT for contract hash: {contract_hash[:8]}...")
            return self._terms_cache[contract_hash]
        return None

    def _set_cached_terms(self, contract_hash: str, terms: List[Dict]) -> None:
        if len(self._terms_cache) >= self._cache_max_size:
            oldest_key = next(iter(self._terms_cache))
            del self._terms_cache[oldest_key]
            logger.debug(f"Cache evicted oldest entry, size now: {len(self._terms_cache)}")
        self._terms_cache[contract_hash] = terms
        logger.debug(f"Cache SET for contract hash: {contract_hash[:8]}...")

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

    def extract_key_terms(self, contract_text: str, max_retries: int = None, use_cache: bool = True) -> List[Dict]:
        self.timer.start_step("term_extraction")
        logger.info("STEP 1: Term Extraction")
        logger.debug(f"Contract length: {len(contract_text)} chars")
        
        contract_hash = self._get_contract_hash(contract_text)
        
        if use_cache:
            cached_terms = self._get_cached_terms(contract_hash)
            if cached_terms is not None:
                logger.info(f"Using cached terms ({len(cached_terms)} terms) for contract hash: {contract_hash[:8]}...")
                self.timer.end_step()
                return cached_terms
        
        if max_retries is None:
            max_retries = self.DEFAULT_MAX_RETRIES
        
        if self.client is None:
            logger.warning("FALLBACK: GenAI client not available, skipping term extraction")
            self.timer.end_step()
            return []
        
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
            
            logger.debug("Calling Gemini API for extraction with temperature=0 for deterministic results...")
            tracer = get_request_tracer()
            api_start_time = time.time()
            
            response = None
            retry_count = 0
            
            for attempt in range(max_retries + 1):
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=extraction_prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.0,
                            response_modalities=["TEXT"]
                        )
                    )
                    retry_count = attempt
                    break
                except Exception as e:
                    retry_count = attempt
                    if is_retryable_error(e) and attempt < max_retries:
                        delay = self.DEFAULT_RETRY_BASE_DELAY ** (attempt + 1)
                        logger.warning(f"Term extraction retry {attempt + 1}/{max_retries} after {delay}s: {str(e)[:100]}")
                        time.sleep(delay)
                    else:
                        raise
            
            api_duration = time.time() - api_start_time
            if tracer:
                tracer.record_api_call(
                    service="gemini",
                    method="extract_key_terms",
                    endpoint=f"models/{self.model_name}/generateContent",
                    request_data={"prompt_length": len(extraction_prompt)},
                    response_data={"has_candidates": hasattr(response, 'candidates') and bool(response.candidates), "retries": retry_count},
                    duration=api_duration
                )
            
            if response is None:
                logger.warning(f"FALLBACK: No response after {retry_count} retries")
                self.timer.end_step()
                return []
            
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
            
            logger.info(f"Extracted {len(valid_terms)} valid terms (retries: {retry_count})")
            
            if valid_terms:
                self._set_cached_terms(contract_hash, valid_terms)
            
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

    def _search_single_sensitive_clause(self, sensitive_clause: Dict, tracer) -> Tuple[str, List[Dict], Optional[str]]:
        """
        Search for a single sensitive clause. Returns (clause_id, chunks, error).
        This method is designed to be called in parallel.
        """
        clause_id = sensitive_clause.get("term_id", "unknown")
        clause_text = sensitive_clause.get("term_text", "")
        issues = sensitive_clause.get("potential_issues", [])
        
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
        
        max_retries = self.DEFAULT_MAX_RETRIES
        retry_count = 0
        sensitive_response = None
        search_start = time.time()
        
        for attempt in range(max_retries + 1):
            try:
                sensitive_response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=sensitive_search_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        tools=[types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[self.store_id],
                                top_k=self.top_k_sensitive
                            )
                        )],
                        response_modalities=["TEXT"]
                    )
                )
                retry_count = attempt
                break
            except Exception as e:
                retry_count = attempt
                if is_retryable_error(e) and attempt < max_retries:
                    delay = self.DEFAULT_RETRY_BASE_DELAY ** (attempt + 1)
                    logger.warning(f"Sensitive search retry {attempt + 1}/{max_retries} for {clause_id}: {str(e)[:100]}")
                    time.sleep(delay)
                else:
                    logger.error(f"Sensitive search failed for {clause_id} after {attempt + 1} attempts: {e}")
                    return (clause_id, [], f"{clause_id}: {str(e)[:50]}")
        
        search_duration = time.time() - search_start
        
        if sensitive_response:
            clause_chunks = self._extract_grounding_chunks(sensitive_response, self.top_k_sensitive)
            logger.debug(f"Sensitive search for {clause_id}: {len(clause_chunks)} chunks (retries: {retry_count}, time: {search_duration:.1f}s)")
            
            if tracer:
                tracer.record_api_call(
                    service="gemini_file_search",
                    method="sensitive_search",
                    endpoint=f"models/{self.model_name}/generateContent",
                    request_data={"clause_id": clause_id, "issues": issues, "top_k": self.top_k_sensitive},
                    response_data={"chunks_count": len(clause_chunks), "retries": retry_count},
                    duration=search_duration
                )
            return (clause_id, clause_chunks, None)
        
        return (clause_id, [], f"{clause_id}: No response")

    def search_chunks(self, contract_text: str, top_k: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
        search_timer = RequestTimer()
        
        general_chunks = []
        extracted_terms = []
        sensitive_chunks = []
        pipeline_partial = False
        
        if self.client is None:
            logger.warning("FALLBACK: GenAI client not available, returning empty results")
            return [], []
        
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
            
            max_retries = self.DEFAULT_MAX_RETRIES
            retry_count = 0
            response = None
            general_search_start = time.time()
            
            for attempt in range(max_retries + 1):
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.0,
                            tools=[types.Tool(
                                file_search=types.FileSearch(
                                    file_search_store_names=[self.store_id],
                                    top_k=top_k
                                )
                            )],
                            response_modalities=["TEXT"]
                        )
                    )
                    retry_count = attempt
                    break
                except Exception as e:
                    retry_count = attempt
                    if is_retryable_error(e) and attempt < max_retries:
                        delay = self.DEFAULT_RETRY_BASE_DELAY ** (attempt + 1)
                        logger.warning(f"General search retry {attempt + 1}/{max_retries} after {delay}s: {str(e)[:100]}")
                        time.sleep(delay)
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
            logger.info(f"General search: {len(general_chunks)} chunks (retries: {retry_count})")
            search_timer.end_step()
            
            sensitive_search_failed = False
            sensitive_search_errors = []
            
            # Check if sensitive search is enabled
            if not self.enable_sensitive_search:
                logger.info("STEP 3: Sensitive Search DISABLED (ENABLE_SENSITIVE_SEARCH=False)")
            elif extracted_terms:
                sensitive_clauses = self._filter_sensitive_clauses(extracted_terms)
                
                if sensitive_clauses:
                    search_timer.start_step("sensitive_search")
                    # Use configurable max_workers with rate limiting
                    max_workers = min(len(sensitive_clauses), self.sensitive_search_max_workers)
                    logger.info(f"STEP 3: Sensitive Search ({len(sensitive_clauses)} clauses, {max_workers} workers, {self.sensitive_search_delay}s delay)")
                    
                    # Rate-limited parallel execution
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = []
                        for idx, clause in enumerate(sensitive_clauses):
                            # Add delay between submissions to respect rate limits
                            if idx > 0 and self.sensitive_search_delay > 0:
                                time.sleep(self.sensitive_search_delay)
                            futures.append(executor.submit(self._search_single_sensitive_clause, clause, tracer))
                        
                        for future in as_completed(futures):
                            try:
                                clause_id, clause_chunks, error = future.result()
                                if error:
                                    sensitive_search_failed = True
                                    sensitive_search_errors.append(error)
                                    # Check for rate limit errors
                                    if "429" in str(error) or "quota" in str(error).lower():
                                        logger.warning("Rate limit detected, skipping remaining sensitive searches")
                                        break
                                else:
                                    sensitive_chunks.extend(clause_chunks)
                            except Exception as e:
                                logger.error(f"Sensitive search future error: {e}")
                                sensitive_search_failed = True
                    
                    if sensitive_search_failed:
                        pipeline_partial = True
                        logger.warning(f"Sensitive search had {len(sensitive_search_errors)} failures, continuing with partial results")
                    
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
            status = "PARTIAL" if pipeline_partial else "COMPLETE"
            logger.info(f"Total unique chunks: {len(all_chunks)}")
            logger.info(f"Pipeline time: {timing['total_time_seconds']}s")
            logger.info("=" * 50)
            logger.info(f"FILE SEARCH PIPELINE {status}")
            logger.info("=" * 50)
            
            return all_chunks, extracted_terms

        except Exception as e:
            logger.error(f"Search pipeline failed: {e}")
            
            # Merge any collected chunks (general + sensitive) before returning
            collected_chunks = general_chunks.copy()
            if sensitive_chunks:
                # Add sensitive chunks that aren't duplicates
                existing_texts = {c.get("chunk_text", "") for c in collected_chunks}
                for chunk in sensitive_chunks:
                    if chunk.get("chunk_text", "") not in existing_texts:
                        collected_chunks.append(chunk)
            
            if collected_chunks or extracted_terms:
                logger.warning("PARTIAL RESULTS: Returning data collected before failure")
                
                for idx, chunk in enumerate(collected_chunks):
                    chunk["uid"] = f"chunk_{idx + 1}"
                
                logger.info(f"Returning partial: {len(collected_chunks)} chunks ({len(general_chunks)} general + {len(sensitive_chunks)} sensitive), {len(extracted_terms)} terms")
                return collected_chunks, extracted_terms
            
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
