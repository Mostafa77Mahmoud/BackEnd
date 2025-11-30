import time
import json
import re
from google import genai
from google.genai import types
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from flask import current_app
from app.utils.logging_utils import get_logger, mask_key

logger = get_logger(__name__)

FILE_SEARCH_AVAILABLE = hasattr(genai.Client, 'file_search_stores') if hasattr(genai, 'Client') else False

def check_file_search_support():
    """Check if File Search API is supported in the installed google-genai version."""
    try:
        import google.genai as genai_module
        version = getattr(genai_module, '__version__', 'unknown')
        logger.info(f"google-genai version: {version}")
        
        if not FILE_SEARCH_AVAILABLE:
            logger.warning("File Search API not available in this version of google-genai")
            logger.warning("Please upgrade: pip install --upgrade google-genai>=1.50.0")
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking File Search support: {e}")
        return False

class FileSearchService:
    """
    Service for searching files using Google Gemini File Search API.
    Focuses on retrieving chunks from AAOIFI reference documents.
    
    Uses a two-step approach:
    1. Extract key terms from the contract.
    2. Search in File Search using extracted terms.
    """

    # Chunk Schema Configuration
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
        """Initialize service with Gemini API connection."""
        self.file_search_enabled = check_file_search_support()
        
        self.api_key = current_app.config.get('GEMINI_FILE_SEARCH_API_KEY') or current_app.config.get('GEMINI_API_KEY')
        if not self.api_key:
            logger.error("GEMINI_FILE_SEARCH_API_KEY or GEMINI_API_KEY not found in config")
            self.file_search_enabled = False
        
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"FileSearchService initialized using API Key: {mask_key(self.api_key)}")
            except Exception as e:
                logger.error(f"Failed to create GenAI client: {e}")
                self.file_search_enabled = False
        
        self.model_name = current_app.config.get('MODEL_NAME', 'gemini-2.5-flash')
        self.store_id: Optional[str] = current_app.config.get('FILE_SEARCH_STORE_ID')
        self.context_dir = "context"
        
        logger.info(f"Model: {self.model_name}")
        logger.info(f"File Search Enabled: {self.file_search_enabled}")
        if self.store_id:
            logger.info(f"Store ID: {self.store_id}")

    @property
    def extract_prompt_template(self):
        from config.default import DefaultConfig
        config = DefaultConfig()
        return config.EXTRACT_KEY_TERMS_PROMPT

    @property
    def search_prompt_template(self):
        from config.default import DefaultConfig
        config = DefaultConfig()
        return config.FILE_SEARCH_PROMPT

    def initialize_store(self) -> str:
        """
        Initialize or connect to existing File Search Store.

        Returns:
            str: Store ID
        """
        logger.info("="*60)
        logger.info("FILE SEARCH STORE INITIALIZATION")
        logger.info("="*60)

        if not self.file_search_enabled:
            logger.error("File Search API is not available")
            raise ValueError("File Search API not available. Please upgrade google-genai>=1.50.0")
        
        if not self.client:
            logger.error("GenAI client not initialized")
            raise ValueError("GenAI client not initialized")

        # Check for existing Store ID
        if self.store_id:
            logger.info(f"Checking existing Store ID: {self.store_id}")
            try:
                store = self.client.file_search_stores.get(name=self.store_id)
                logger.info(f"Connected to existing store: '{store.display_name}'")
                logger.info("Store is active and ready")
                return self.store_id
            except Exception as e:
                logger.warning(f"Could not access store {self.store_id}")
                logger.warning(f"Error: {e}")
                logger.info("Will create a new store...")

        # Create new Store
        logger.info("Creating new File Search Store...")
        try:
            store = self.client.file_search_stores.create(
                config={'display_name': 'AAOIFI Reference Store'}
            )
            self.store_id = store.name
            logger.info(f"New store created: {self.store_id}")
            logger.warning("IMPORTANT: Save this Store ID to .env file:")
            logger.warning(f"FILE_SEARCH_STORE_ID={self.store_id}")

            # Upload files from context/ folder
            self._upload_context_files()

            if self.store_id is None:
                raise ValueError("Store ID was not set after creation")

            return self.store_id

        except Exception as e:
            logger.error(f"Failed to create File Search Store: {e}")
            raise

    def _upload_context_files(self):
        """Upload all files from context/ directory to File Search Store."""

        if not self.store_id:
            logger.error("Store ID is not set. Cannot upload files.")
            return

        # Use absolute path for context directory relative to app root if needed
        # Assuming run.py is at root, context is at root
        context_path = Path(current_app.root_path).parent / self.context_dir
        if not context_path.exists():
             context_path = Path(self.context_dir) # Try relative to CWD

        # Check directory existence
        if not context_path.exists():
            logger.warning(f"Context directory '{context_path}' not found")
            context_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {context_path}")
            logger.info(f"Please add your AAOIFI reference files to '{context_path}/' folder")
            return

        # Find files
        files = list(context_path.glob("*"))
        files = [f for f in files if f.is_file() and not f.name.startswith('.')]

        if not files:
            logger.warning(f"No files found in '{context_path}/' directory")
            logger.info("Please add your AAOIFI reference files (PDF, TXT, etc.)")
            return

        logger.info(f"Found {len(files)} file(s) to upload:")
        for f in files:
            logger.info(f"  - {f.name}")

        # Upload each file
        uploaded_count = 0
        for file_path in files:
            logger.info(f"Uploading: {file_path.name}")
            try:
                operation = self.client.file_search_stores.upload_to_file_search_store(
                    file=str(file_path),
                    file_search_store_name=self.store_id,
                    config={'display_name': file_path.name}
                )

                logger.info(f"Waiting for {file_path.name} to be indexed...")
                while not operation.done:
                    time.sleep(2)
                    operation = self.client.operations.get(operation)

                uploaded_count += 1
                logger.info(f"{file_path.name} uploaded and indexed")

            except Exception as e:
                logger.error(f"Failed to upload {file_path.name}: {e}")

        logger.info(f"Successfully uploaded {uploaded_count}/{len(files)} files")
        logger.info("="*60)

    def extract_key_terms(self, contract_text: str) -> List[Dict]:
        """
        Step 1: Extract key terms from contract.
        
        Uses Gemini to analyze contract and extract 5-15 important clauses
        with Sharia keywords to improve subsequent search.
        
        Args:
            contract_text: Full contract text
            
        Returns:
            List[Dict]: List of extracted terms
        """
        
        logger.info("STEP 1/2: Extracting key terms from contract...")
        logger.info(f"Contract length: {len(contract_text)} characters")
        logger.info(f"Using API Key: {mask_key(self.api_key)}")
        
        try:
            # Apply extraction prompt
            try:
                extraction_prompt = self.extract_prompt_template.format(contract_text=contract_text)
            except KeyError as e:
                logger.error(f"Prompt formatting error: {e}")
                extraction_prompt = "Extract key terms from this contract: " + contract_text[:1000]
            
            logger.info("Calling Gemini for term extraction...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=extraction_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT"]
                )
            )
            
            # Extract text from response
            if not hasattr(response, 'candidates') or not response.candidates:
                logger.error("No candidates in extraction response")
                return []
            
            candidate = response.candidates[0]
            if not hasattr(candidate, 'content') or not candidate.content:
                logger.error("No content in extraction response")
                return []
            
            if not hasattr(candidate.content, 'parts') or not candidate.content.parts:
                logger.error("No parts in extraction response")
                return []
            
            extracted_text = candidate.content.parts[0].text if hasattr(candidate.content.parts[0], 'text') else None
            
            if not extracted_text:
                logger.error("No text in extraction response")
                return []
            
            logger.debug(f"Extraction response length: {len(extracted_text)} characters")
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', extracted_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                extracted_terms = json.loads(json_str)
                logger.info(f"Extracted {len(extracted_terms)} key terms")
                
                return extracted_terms
            else:
                logger.error("Could not find JSON array in response")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from extraction: {e}")
            return []
        except Exception as e:
            logger.error(f"Term extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_sensitive_keywords(self) -> List[str]:
        """Sensitive keywords requiring deeper separate search."""
        return [
            "الغرر", "الجهالة", "الربا", "فائدة التأخير", 
            "التعويض غير المشروع", "الشرط الباطل", "الشرط الجائر",
            "الظلم", "الإكراه", "الضرر", "الوعد الملزم"
        ]

    def _filter_sensitive_clauses(self, extracted_terms: List[Dict]) -> List[Dict]:
        """Separate sensitive clauses from normal ones."""
        sensitive_keywords = self._get_sensitive_keywords()
        sensitive_clauses = []
        
        for term in extracted_terms:
            issues = term.get("potential_issues", [])
            if any(keyword in issues for keyword in sensitive_keywords):
                sensitive_clauses.append(term)
        
        return sensitive_clauses

    def search_chunks(self, contract_text: str, top_k: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Hybrid File Search for contract text.
        
        Returns:
            Tuple[List[Dict], List[Dict]]: (chunks, extracted_terms)
        """

        if not self.store_id:
            # Try to initialize if not set
            try:
                self.initialize_store()
            except:
                raise ValueError("File Search Store not initialized.")

        if top_k is None:
            top_k = current_app.config.get('TOP_K_CHUNKS', 10)

        logger.info("="*60)
        logger.info("HYBRID FILE SEARCH PROCESS (Two-Step + Sensitive Clauses)")
        logger.info("="*60)
        logger.info(f"Using API Key: {mask_key(self.api_key)}")

        try:
            # ===== Phase 1: Extract Key Terms =====
            extracted_terms = self.extract_key_terms(contract_text)
            
            if not extracted_terms:
                logger.warning("No terms extracted, falling back to full contract search")
                extracted_clauses_text = contract_text[:2000]
            else:
                extracted_clauses_text = json.dumps(extracted_terms, ensure_ascii=False, indent=2)
            
            # ===== Phase 2: General Search (All Clauses) =====
            logger.info("PHASE 1/2: General Search for all extracted clauses...")
            logger.info(f"Using top_k={top_k} for comprehensive coverage")
            
            full_prompt = self.search_prompt_template.format(extracted_clauses=extracted_clauses_text)

            logger.info("SEARCH: Querying Gemini File Search (Phase 1)...")
            
            # Retry logic for 503 errors
            max_retries = 3
            retry_count = 0
            response = None
            
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
                        logger.warning(f"Got 503 error, retrying... (attempt {retry_count}/{max_retries})")
                        if retry_count < max_retries:
                            time.sleep(2 ** retry_count)
                        else:
                            raise
                    else:
                        raise

            general_chunks = self._extract_grounding_chunks(response, top_k)
            logger.info(f"Phase 1 retrieved {len(general_chunks)} chunks")
            
            # ===== Phase 3: Deep Search (Sensitive Clauses) =====
            sensitive_chunks = []
            
            if extracted_terms:
                sensitive_clauses = self._filter_sensitive_clauses(extracted_terms)
                
                if sensitive_clauses:
                    logger.info(f"PHASE 2/2: Deep Search for {len(sensitive_clauses)} sensitive clause(s)...")
                    
                    for sensitive_clause in sensitive_clauses:
                        clause_id = sensitive_clause.get("term_id", "unknown")
                        clause_text = sensitive_clause.get("term_text", "")
                        issues = sensitive_clause.get("potential_issues", [])
                        
                        logger.info(f"DEEP SEARCH: Processing sensitive clause: {clause_id}")
                        
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
                        
                        if sensitive_response:
                            clause_chunks = self._extract_grounding_chunks(sensitive_response, 2)
                            sensitive_chunks.extend(clause_chunks)
                            logger.info(f"Deep search retrieved {len(clause_chunks)} chunks")
                else:
                    logger.info("PHASE 2/2: No sensitive clauses found, skipping deep search")
            
            # ===== Merge Results =====
            logger.info("MERGE: Combining general and sensitive chunks...")
            
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
                chunk["uid"] = "chunk_{}".format(idx + 1)
            
            logger.info(f"Total {len(all_chunks)} unique chunks")
            logger.info("="*60)
            
            return all_chunks, extracted_terms

        except Exception as e:
            logger.error(f"Search failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _extract_grounding_chunks(self, response, top_k: int) -> List[Dict]:
        """Extract chunks from grounding metadata."""
        chunks = []

        if not hasattr(response, 'candidates') or not response.candidates:
            return chunks

        candidate = response.candidates[0]

        if not hasattr(candidate, 'grounding_metadata'):
            return chunks

        grounding = candidate.grounding_metadata
        
        if grounding is None:
            return chunks
        
        # Priority 1: grounding_chunks (Original PDF content)
        if hasattr(grounding, 'grounding_chunks') and grounding.grounding_chunks:
            for idx, chunk in enumerate(grounding.grounding_chunks):
                if idx >= top_k:
                    break

                chunk_data = {
                    "uid": "chunk_{}".format(idx + 1),
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

        # Fallback: grounding_supports
        if hasattr(grounding, 'grounding_supports') and grounding.grounding_supports:
            for idx, support in enumerate(grounding.grounding_supports):
                if idx >= top_k:
                    break

                chunk_data = {
                    "uid": "support_{}".format(idx + 1),
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
        """Get info about current File Search Store."""
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
                "error": str(e),
                "message": "Failed to access store"
            }
