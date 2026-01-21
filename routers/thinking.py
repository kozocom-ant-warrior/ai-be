"""Routes for Thinking endpoint - matching CVs with JD"""
import logging
import json
import numpy as np
import re
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from fastapi import APIRouter, HTTPException, status, Request
from openai import OpenAI
import tiktoken
from db.database import get_all_files
from config import CV_DIRECTORY, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MINI_MODEL, OPENAI_EMBEDDING_MODEL, PROMPT_LANGUAGE
from prompts import get_cv_matching_prompt, get_system_message, format_cv_contents, get_extraction_prompt, get_cv_extraction_prompt, get_stage3_advanced_prompt
from utils import clean_text_for_embedding
from db import vector_db

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI configuration
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables. Please create .env file and add OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

router = APIRouter(prefix="/thinking", tags=["Thinking"])


class CVScoringEngine:
    """
    Stage 2: Deterministic scoring engine
    Calculates scores based on structured data from Stage 1
    """
    
    def __init__(self, requirements: dict, advanced_options: dict = None):
        """
        Args:
            requirements: Requirements from JD (output of Stage 1)
            advanced_options: Advanced options
        """
        self.requirements = requirements
        self.advanced_options = advanced_options or {}
        self.must_have_count = len(requirements.get('must_have_requirements', []))
        self.nice_to_have_count = len(requirements.get('nice_to_have_requirements', []))
    
    def calculate_score(self, cv_data: dict) -> dict:
        """
        Calculate score for a CV based on extracted data
        
        Args:
            cv_data: CV data from Stage 1 (includes must_have_matched, nice_to_have_matched)
        
        Returns:
            dict: Scoring results with score, matched_requirements, missing_requirements
        """
        # Count must-have matched
        must_have_matched = [m for m in cv_data.get('must_have_matched', []) if m.get('matched')]
        must_have_missing = [m for m in cv_data.get('must_have_matched', []) if not m.get('matched')]
        
        # Count nice-to-have matched
        nice_to_have_matched = [m for m in cv_data.get('nice_to_have_matched', []) if m.get('matched')]
        
        # Calculate must-have percentage
        if self.must_have_count > 0:
            must_have_percentage = len(must_have_matched) / self.must_have_count
        else:
            must_have_percentage = 1.0  # If no must-haves, consider 100%
        
        # Base score from must-have (0-90 points)
        base_score = must_have_percentage * 90
        
        # Bonus from nice-to-have (0-10 points)
        if self.nice_to_have_count > 0:
            nice_to_have_bonus = (len(nice_to_have_matched) / self.nice_to_have_count) * 10
        else:
            nice_to_have_bonus = 0
        
        # Total score
        total_score = min(100, base_score + nice_to_have_bonus)
        
        # Apply stricter rules
        missing_count = len(must_have_missing)
        if missing_count == 1:
            total_score = min(total_score, 85)
        elif missing_count == 2:
            total_score = min(total_score, 70)
        elif missing_count >= 3:
            total_score = min(total_score, 60)
        
        # Build matched_requirements list
        matched_requirements = []
        for m in must_have_matched:
            req_text = f"{m['skill']}"
            if m.get('note'):
                req_text += f" - {m['note']}"
            matched_requirements.append(req_text)
        
        for m in nice_to_have_matched:
            req_text = f"{m['skill']} (nice-to-have)"
            if m.get('note'):
                req_text += f" - {m['note']}"
            matched_requirements.append(req_text)
        
        # Build missing_requirements list
        missing_requirements = []
        for m in must_have_missing:
            req_text = f"{m['skill']}"
            if m.get('note'):
                req_text += f" - {m['note']}"
            missing_requirements.append(req_text)
        
        # Build mapping description
        mapping_description = self._build_description(
            cv_data,
            must_have_percentage,
            len(must_have_matched),
            self.must_have_count,
            len(nice_to_have_matched),
            self.nice_to_have_count
        )
        
        return {
            "score": round(total_score, 1),
            "matched_requirements": matched_requirements,
            "missing_requirements": missing_requirements,
            "mapping_description": mapping_description,
            "must_have_matched_count": len(must_have_matched),
            "must_have_total_count": self.must_have_count,
            "nice_to_have_matched_count": len(nice_to_have_matched),
            "nice_to_have_total_count": self.nice_to_have_count
        }
    
    def _build_description(self, cv_data: dict, must_have_pct: float, 
                          must_matched: int, must_total: int,
                          nice_matched: int, nice_total: int) -> str:
        """Build mapping description"""
        candidate_name = cv_data.get('candidate_name', 'Candidate')
        
        if must_have_pct >= 1.0:
            desc = f"{candidate_name} fully meets {must_total}/{must_total} must-have requirements."
        elif must_have_pct >= 0.8:
            desc = f"{candidate_name} meets {must_matched}/{must_total} must-have requirements (missing {must_total - must_matched})."
        elif must_have_pct >= 0.5:
            desc = f"{candidate_name} only meets {must_matched}/{must_total} must-have requirements, missing some important requirements."
        else:
            desc = f"{candidate_name} does not meet sufficient requirements, only has {must_matched}/{must_total} must-have requirements."
        
        if nice_total > 0:
            desc += f" Has {nice_matched}/{nice_total} nice-to-have skills."
        
        return desc


def calculate_optimal_batch_size(
    cvs: List[Dict], 
    requirements: Dict,
    max_tokens: int = 120000,
    model: str = "gpt-4o-mini"
) -> List[List[Dict]]:
    """
    Chia CVs thành batches dựa trên token count, không phải số lượng cố định
    
    Args:
        cvs: List of CV objects with 'content' field
        requirements: JD requirements (to calculate prompt overhead)
        max_tokens: Maximum tokens per batch (default: 120K for gpt-4o-mini)
        model: Model name for token encoding
        
    Returns:
        List[List[Dict]]: List of batches, mỗi batch là list CVs
    """
    try:
        # Get encoder for model
        try:
            encoder = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base encoding (for gpt-4o-mini/gpt-4o)
            encoder = tiktoken.get_encoding("cl100k_base")
        
        # Calculate overhead tokens (system prompt + requirements prompt)
        system_prompt = "You are a CV analysis expert. Return EXACTLY the JSON as requested."
        requirements_text = json.dumps(requirements)
        overhead_tokens = len(encoder.encode(system_prompt)) + len(encoder.encode(requirements_text))
        
        # Reserve tokens for system + requirements + output
        RESERVED_TOKENS = overhead_tokens + 5000  # Extra 5K for output
        max_batch_tokens = max_tokens - RESERVED_TOKENS
        
        logger.info(f"📊 Dynamic Batching Config:")
        logger.info(f"   Model: {model}")
        logger.info(f"   Max tokens per batch: {max_tokens}")
        logger.info(f"   Overhead tokens: {overhead_tokens} (system + requirements)")
        logger.info(f"   Reserved for output: 5000")
        logger.info(f"   Available for CVs: {max_batch_tokens}")
        
        batches = []
        current_batch = []
        current_tokens = 0
        
        for cv in cvs:
            cv_content = cv.get('content', '')
            cv_tokens = len(encoder.encode(cv_content))
            
            # Nếu CV này vượt quá max_batch_tokens (CV quá dài)
            if cv_tokens > max_batch_tokens:
                logger.warning(
                    f"⚠️  CV {cv.get('filename', 'unknown')} có {cv_tokens} tokens, "
                    f"vượt quá max_batch_tokens ({max_batch_tokens}). Sẽ xử lý riêng."
                )
                # Nếu current_batch có data, lưu lại trước
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
                # Thêm CV này vào batch riêng
                batches.append([cv])
                continue
            
            # Nếu thêm CV này vào batch vượt limit → tạo batch mới
            if current_tokens + cv_tokens > max_batch_tokens and current_batch:
                batches.append(current_batch)
                logger.info(
                    f"   ✓ Batch {len(batches)}: {len(current_batch)} CVs, "
                    f"{current_tokens:,} tokens"
                )
                current_batch = []
                current_tokens = 0
            
            current_batch.append(cv)
            current_tokens += cv_tokens
        
        # Add remaining CVs
        if current_batch:
            batches.append(current_batch)
            logger.info(
                f"   ✓ Batch {len(batches)}: {len(current_batch)} CVs, "
                f"{current_tokens:,} tokens"
            )
        
        logger.info(f"📦 Dynamic Batching Result:")
        logger.info(f"   Total CVs: {len(cvs)}")
        logger.info(f"   Total Batches: {len(batches)}")
        logger.info(f"   Avg CVs per batch: {len(cvs) / len(batches):.1f}")
        
        return batches
        
    except Exception as e:
        logger.error(f"Error in calculate_optimal_batch_size: {e}")
        logger.warning("Fallback to fixed batch size of 5")
        # Fallback: batch size = 5
        FALLBACK_BATCH_SIZE = 5
        return [cvs[i:i + FALLBACK_BATCH_SIZE] for i in range(0, len(cvs), FALLBACK_BATCH_SIZE)]


def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text content from PDF file"""
    try:
        import PyPDF2
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except ImportError:
        logger.warning("PyPDF2 not installed, trying pypdf...")
        try:
            import pypdf
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        except ImportError:
            logger.error("PDF library not found (PyPDF2 or pypdf)")
            return ""
    except Exception as e:
        logger.error(f"Error reading PDF {file_path}: {e}")
        return ""


def extract_text_from_docx(file_path: Path) -> str:
    """Extract text content from DOCX file"""
    try:
        from docx import Document
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    except ImportError:
        logger.error("python-docx not installed")
        return ""
    except Exception as e:
        logger.error(f"Error reading DOCX {file_path}: {e}")
        return ""


def extract_text_from_cv(file_path: str) -> str:
    """Extract text content from CV file (PDF or DOCX)"""
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"File does not exist: {file_path}")
        return ""
    
    extension = path.suffix.lower()
    if extension == ".pdf":
        return extract_text_from_pdf(path)
    elif extension in [".docx", ".doc"]:
        return extract_text_from_docx(path)
    else:
        logger.warning(f"Unsupported file format: {extension}")
        return ""


def get_embedding(text: str, cache_id: Optional[int] = None, cache_type: Optional[str] = None) -> list:
    """
    Create embedding vector for text using OpenAI Embeddings API with cache
    
    Args:
        text: Text to create embedding for
        cache_id: ID for cache (file_id for CV/JD)
        cache_type: Cache type ('cv' or 'jd')
        
    Returns:
        list: Embedding vector (1536 dimensions)
    """
    # Check cache if cache_id and cache_type are provided
    if cache_id and cache_type:
        if cache_type == 'cv':
            cached = vector_db.get_cached_cv_embedding(cache_id, text)
        elif cache_type == 'jd':
            cached = vector_db.get_cached_jd_embedding(text)
        else:
            cached = None
            
        if cached is not None and len(cached) > 0:
            logger.info(f"📦 Using cached embedding for {cache_type} {cache_id}")
            return cached
    
    # No cache, create new via API
    try:
        logger.info(f"🔄 Generating new embedding via OpenAI API ({OPENAI_EMBEDDING_MODEL})...")
        # Clean text before sending to API (remove emojis, special characters)
        cleaned_text = clean_text_for_embedding(text)
        response = client.embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,
            input=cleaned_text  # Use cleaned text for embedding
        )
        embedding = response.data[0].embedding
        
        # Save to cache if cache_id and cache_type are provided
        if cache_id and cache_type and embedding:
            filename = f"{cache_type}_{cache_id}"
            if cache_type == 'cv':
                vector_db.cache_cv_embedding(cache_id, filename, text, embedding)
            elif cache_type == 'jd':
                vector_db.cache_jd_embedding(filename, text, embedding)
        
        return embedding
    except Exception as e:
        logger.error(f"Error creating embedding: {e}")
        return []


def cosine_similarity(vec1: list, vec2: list) -> float:
    """
    Calculate cosine similarity between 2 vectors
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        float: Cosine similarity (0-1)
    """
    # Check if vectors are empty or None
    if vec1 is None or vec2 is None or len(vec1) == 0 or len(vec2) == 0:
        return 0.0
    
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    
    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))


def pre_filter_cvs_by_similarity(cv_data_list: list, jd_text: str, response_requirement: str, top_n: int = 50) -> list:
    """
    Pre-filter CVs using vector similarity
    
    Args:
        cv_data_list: List of all CVs
        jd_text: Job Description
        response_requirement: Response requirement
        top_n: Number of CVs to return
        
    Returns:
        list: Top N CVs with highest similarity
    """
    try:
        logger.info("=" * 80)
        logger.info("STAGE 1: PRE-FILTERING WITH VECTOR SIMILARITY")
        logger.info("=" * 80)
        
        # Cache JD embedding separately
        # Use MD5 hash of JD text + PROMPT_LANGUAGE as cache_id
        jd_cache_key = f"{jd_text}_{PROMPT_LANGUAGE}"
        jd_hash = hashlib.md5(jd_cache_key.encode('utf-8')).hexdigest()
        jd_cache_id = int(jd_hash[:8], 16)  # Take first 8 chars and convert to int
        
        logger.info(f"🔑 JD Cache Key Debug:")
        logger.info(f"  JD text length: {len(jd_text)} chars")
        logger.info(f"  JD text (first 100 chars): {jd_text[:100]}")
        logger.info(f"  PROMPT_LANGUAGE: {PROMPT_LANGUAGE}")
        logger.info(f"  JD hash: {jd_hash[:16]}...")
        
        logger.info(f"Creating embedding for JD (with cache)...")
        jd_embedding = get_embedding(jd_text, cache_id=jd_cache_id, cache_type='jd')
        
        if jd_embedding is None or len(jd_embedding) == 0:
            logger.warning("Could not create JD embedding, skipping pre-filtering")
            return cv_data_list
        
        # Note: response_requirement only contains metadata (number of CVs)
        # Does NOT need embedding as it doesn't affect semantic similarity
        # Number of CVs is parsed and applied at final stage
        
        # Create embeddings for all CVs with cache
        logger.info(f"Creating embeddings for {len(cv_data_list)} CVs (with cache)...")
        cv_embeddings = []
        cache_hits = 0
        cache_misses = 0
        
        for cv in cv_data_list:
            cv_file_id = cv.get('file_id')  # Fix: use 'file_id' not 'id'
            cv_filename = cv.get('filename', f'CV_{cv_file_id}')
            cv_content = cv.get('content', '')
            
            # Check cache first
            cached = vector_db.get_cached_cv_embedding(cv_file_id, cv_content)
            if cached is not None and len(cached) > 0:
                cache_hits += 1
                cv_embeddings.append(cached)
                logger.info(f"  📦 Cache HIT: {cv_filename} (file_id={cv_file_id})")
            else:
                cache_misses += 1
                logger.info(f"  🔄 Cache MISS: {cv_filename} (file_id={cv_file_id}) - Calling OpenAI API...")
                # Get embedding (automatically checks cache in get_embedding)
                embedding = get_embedding(cv_content, cache_id=cv_file_id, cache_type='cv')
                
                if embedding:
                    cv_embeddings.append(embedding)
                else:
                    logger.warning(f"Could not create embedding for CV {cv_file_id}")
                    cv_embeddings.append([])
        
        logger.info(f"✅ Embedding cache: {cache_hits} hits, {cache_misses} misses ({cache_hits/(cache_hits+cache_misses)*100:.1f}% hit rate)")
        
        # Calculate similarity scores
        logger.info("Calculating cosine similarity...")
        similarities = []
        for i, cv_emb in enumerate(cv_embeddings):
            sim = cosine_similarity(jd_embedding, cv_emb)
            similarities.append({
                'cv': cv_data_list[i],
                'similarity': sim
            })
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Log results
        logger.info(f"Top 10 similarity scores:")
        for i, item in enumerate(similarities[:10], 1):
            logger.info(f"  {i}. {item['cv']['filename']}: {item['similarity']:.4f}")
        
        # Get top N
        actual_top_n = min(top_n, len(similarities))
        top_cvs = [item['cv'] for item in similarities[:actual_top_n]]
        
        logger.info(f"Pre-filtering: {len(cv_data_list)} CVs → {len(top_cvs)} CVs (similarity >= {similarities[actual_top_n-1]['similarity']:.4f})")
        logger.info("=" * 80)
        
        return top_cvs
        
    except Exception as e:
        logger.error(f"Error in pre-filtering: {e}", exc_info=True)
        logger.warning("Fallback: Using all CVs")
        return cv_data_list


@router.post("/")
async def thinking_dump(request: Request):
    """
    Endpoint to dump/log all values sent from client
    All fields are optional (not required)
    Supports both text fields and file uploads
    
    Args:
        request: FastAPI Request object
    
    Returns:
        dict: All received values
    """
    try:
        # Parse form data (supports both text and files)
        form_data = await request.form()
        
        # Debug: Log keys in form
        logger.info("=" * 80)
        logger.info("THINKING ENDPOINT - Received request")
        logger.info(f"Form data keys: {list(form_data.keys())}")
        logger.info("=" * 80)
        
        # Helper function to process values from form_data
        async def process_form_value(key: str):
            """Process value from form_data, supports both string and file"""
            if key not in form_data:
                return None
            
            value = form_data[key]
            
            # If UploadFile (file upload)
            if hasattr(value, 'read'):
                try:
                    # Read file content
                    content = await value.read()
                    file_info = {
                        "filename": value.filename,
                        "content_type": value.content_type,
                        "size": len(content) if isinstance(content, bytes) else 0,
                        "is_binary": True
                    }
                    # If text file, decode
                    if isinstance(content, bytes):
                        try:
                            text_content = content.decode('utf-8')
                            file_info["text_content"] = text_content
                        except UnicodeDecodeError:
                            file_info["text_content"] = None
                    return file_info
                except Exception as e:
                    logger.warning(f"Error reading file {key}: {e}")
                    return {"error": str(e), "is_binary": True}
            
            # If string
            str_value = str(value) if value else None
            if str_value and str_value.strip():
                return str_value
            return None
        
        # Process all fields from form_data
        received_data = {}
        for key in form_data.keys():
            processed_value = await process_form_value(key)
            received_data[key] = processed_value
        
        # Log all values
        logger.info("=" * 80)
        logger.info("THINKING ENDPOINT - Dump values from client:")
        logger.info("=" * 80)
        for key, value in received_data.items():
            if isinstance(value, dict) and value.get("is_binary"):
                logger.info(f"{key}: (binary file)")
                logger.info(f"  - filename: {value.get('filename')}")
                logger.info(f"  - content_type: {value.get('content_type')}")
                logger.info(f"  - size: {value.get('size')} bytes")
                if value.get("text_content"):
                    logger.info(f"  - text_content: {value.get('text_content')[:100]}...")
            else:
                logger.info(f"{key}: {value}")
        logger.info("=" * 80)
        
        # Print to console for easier debugging
        print("\n" + "=" * 80)
        print("THINKING ENDPOINT - Dump values from client:")
        print("=" * 80)
        for key, value in received_data.items():
            if isinstance(value, dict) and value.get("is_binary"):
                print(f"{key}: (binary file)")
                print(f"  - filename: {value.get('filename')}")
                print(f"  - content_type: {value.get('content_type')}")
                print(f"  - size: {value.get('size')} bytes")
                if value.get("text_content"):
                    print(f"  - text_content: {value.get('text_content')[:100]}...")
            else:
                print(f"{key}: {value}")
        print("=" * 80 + "\n")
        
        # Get data from form
        jd_text = received_data.get("jd_text", "")
        response_requirement = received_data.get("response_requirement", "")
        advanced_options_str = received_data.get("advanced_options", "{}")
        
        # Parse advanced_options if string
        try:
            if isinstance(advanced_options_str, str):
                advanced_options = json.loads(advanced_options_str)
            else:
                advanced_options = advanced_options_str
        except:
            advanced_options = {}
        
        # Get all CVs from database
        logger.info("Loading CV list from database...")
        cv_files, total_cvs = get_all_files(limit=1000, offset=0, file_type="cv")
        logger.info(f"Found {total_cvs} CVs in database")
        
        if total_cvs == 0:
            logger.warning("No CVs found in database")
            return {
                "status": "success",
                "message": "No CVs found in database",
                "received_data": received_data,
                "cv_mappings": []
            }
        
        # Get content from each CV from database (content column)
        cv_data_list = []
        unreadable_cvs = []  # Track unreadable CVs
        for cv_file in cv_files:
            file_path = cv_file.get("file_path", "")
            if not file_path:
                continue
            
            logger.info(f"Loading CV content: {cv_file.get('original_filename', 'unknown')}")
            
            # Prioritize getting from content column in database
            cv_text = cv_file.get("content")
            
            # If no content in database, fallback to reading file (for old CVs)
            if not cv_text or not cv_text.strip():
                logger.info(f"CV {cv_file.get('original_filename', 'unknown')} has no content in DB, reading from file...")
                cv_text = extract_text_from_cv(file_path)
            
            if cv_text and cv_text.strip():
                cv_data_list.append({
                    "cv_id": f"cv_{cv_file['id']}",
                    "file_id": cv_file['id'],
                    "filename": cv_file.get('original_filename', ''),
                    "content": cv_text  # Keep full text for accurate embedding
                })
            else:
                unreadable_filename = cv_file.get('original_filename', 'unknown')
                unreadable_cvs.append(unreadable_filename)
                logger.warning(f"Could not get CV content: {unreadable_filename}")
        
        if not cv_data_list:
            logger.warning("No CVs with readable content")
            return {
                "status": "success",
                "message": "Could not read content from CVs",
                "received_data": received_data,
                "cv_mappings": []
            }
        
        logger.info(f"Successfully read {len(cv_data_list)} CVs")
        logger.info(f"Advanced options: {advanced_options}")
        
        # Debug: Log JD text hash to detect duplicates
        import hashlib
        jd_cache_key_preview = f"{jd_text}_{PROMPT_LANGUAGE}"
        jd_hash_preview = hashlib.md5(jd_cache_key_preview.encode('utf-8')).hexdigest()
        logger.info("=" * 80)
        logger.info("🔍 JD TEXT DEBUG:")
        logger.info(f"   Length: {len(jd_text)} chars")
        logger.info(f"   PROMPT_LANGUAGE: {PROMPT_LANGUAGE}")
        logger.info(f"   MD5 Hash (with lang): {jd_hash_preview}")
        logger.info(f"   First 200 chars: {jd_text[:200]}")
        logger.info(f"   Last 100 chars: {jd_text[-100:]}")
        logger.info("=" * 80)
        
        # Get number of CVs to return from payload (max_cv_count) or parse from response_requirement
        requested_cv_count = None
        
        # Prioritize getting from max_cv_count in payload
        max_cv_count_value = received_data.get("max_cv_count")
        
        if max_cv_count_value is not None and isinstance(max_cv_count_value, str):
            try:
                # Handle string, remove whitespace
                stripped = max_cv_count_value.strip()
                if stripped:  # Only convert if not empty
                    requested_cv_count = int(stripped)
                    logger.info(f"✅ Got max_cv_count from payload: {requested_cv_count}")
                else:
                    logger.warning(f"max_cv_count is empty string, skipping")
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid max_cv_count: {max_cv_count_value} (error: {e}), will try parsing from response_requirement")
        
        # Fallback: Parse from response_requirement if no max_cv_count
        if requested_cv_count is None and response_requirement:
            # Find patterns like "2 CV", "top 3", "3 candidates", etc.
            patterns = [
                r'(?:get|return|give|top)\s*(\d+)\s*(?:cv|candidate)',
                r'(\d+)\s*(?:cv|candidate)',
            ]
            for pattern in patterns:
                match = re.search(pattern, response_requirement.lower())
                if match:
                    requested_cv_count = int(match.group(1))
                    logger.info(f"Detected CV count requirement: {requested_cv_count}")
                    break
        
        # STAGE 1: Pre-filter CVs using vector similarity
        # Always create embeddings for cache, only filter when there are many CVs
        PRE_FILTER_THRESHOLD = 50  # Threshold to apply filtering (does not affect cache)
        
        # Calculate number of CVs to pre-filter based on requirement
        if requested_cv_count:
            PRE_FILTER_TOP_N = max(requested_cv_count * 5, 30)
        else:
            PRE_FILTER_TOP_N = 50
        
        # ALWAYS create embeddings for cache (regardless of CV count)
        # Only apply filtering when exceeding threshold
        if len(cv_data_list) > PRE_FILTER_THRESHOLD:
            logger.info(f"Will pre-filter down to {PRE_FILTER_TOP_N} CVs (buffer for {requested_cv_count or 'all'} requested CVs)")
            top_n = PRE_FILTER_TOP_N
        else:
            logger.info(f"Creating embeddings for cache (no filter as only {len(cv_data_list)} CVs)")
            top_n = len(cv_data_list)  # No filter, but still create cache
        
        cv_data_list = pre_filter_cvs_by_similarity(
            cv_data_list, 
            jd_text, 
            response_requirement, 
            top_n=top_n  # Pass len(cv_data_list) if no filter
        )
        logger.info(f"After pre-filtering: {len(cv_data_list)} CVs")
        
        # Define helper function for OpenAI retry logic
        def call_openai_with_retry(messages, max_retries=5, model=None):
            """Call OpenAI API with exponential backoff retry"""
            if model is None:
                model = OPENAI_MODEL
            
            for attempt in range(max_retries):
                try:
                    start_time = time.time()
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.1,  # Slightly increase to help GPT focus on completing JSON
                        max_tokens=6000  # Increased for Stage 3 with cv_presentation_comment object
                    )
                    elapsed_time = time.time() - start_time
                    
                    # Log token usage and time
                    usage = response.usage
                    logger.info(f"  ⏱️  {elapsed_time:.2f}s | 📊 Tokens: {usage.prompt_tokens} in + {usage.completion_tokens} out = {usage.total_tokens} total")
                    
                    return response
                except Exception as e:
                    if "rate_limit" in str(e).lower() or "429" in str(e):
                        wait_time = min(2 ** attempt, 20)  # Max 20 seconds
                        logger.warning(f"Rate limit hit, waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        if attempt == max_retries - 1:
                            raise
                    else:
                        raise
        
        # STAGE 1: Extract requirements from JD
        logger.info("=" * 80)
        logger.info("STAGE 1: EXTRACTING REQUIREMENTS FROM JD")
        logger.info("=" * 80)
        
        import time
        stage1_start = time.time()
        
        # Token tracking
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0
        
        try:
            # Create JD hash for cache (Stage 1A cache key)
            jd_cache_key_stage1a = f"{jd_text}_{PROMPT_LANGUAGE}"
            jd_hash_for_stage1a = hashlib.md5(jd_cache_key_stage1a.encode('utf-8')).hexdigest()
            
            # Initialize stage1a_usage (default to None, set if cache MISS)
            stage1a_usage = None
            
            # Check cache before calling OpenAI
            logger.info(f"🔍 Checking cache for JD requirements (hash: {jd_hash_for_stage1a[:16]}...)")
            requirements = vector_db.get_cached_jd_requirements(jd_hash_for_stage1a)
            
            if requirements:
                logger.info(f"✅ Cache HIT: Using cached JD requirements")
            else:
                # Cache MISS - call OpenAI
                logger.info(f"❌ Cache MISS: Calling OpenAI ({OPENAI_MODEL}) to extract requirements from JD...")
                extraction_prompt = get_extraction_prompt(jd_text, response_requirement)
                
                extraction_response = call_openai_with_retry(
                    messages=[
                        {"role": "system", "content": "You are a Job Description analysis expert. Return EXACTLY the JSON as requested."},
                        {"role": "user", "content": extraction_prompt}
                    ],
                    model=OPENAI_MODEL
                )
                
                requirements_text = extraction_response.choices[0].message.content.strip()
                
                # Parse JSON from response
                if "```json" in requirements_text:
                    requirements_text = requirements_text.split("```json")[1].split("```")[0].strip()
                elif "```" in requirements_text:
                    requirements_text = requirements_text.split("```")[1].split("```")[0].strip()
                
                requirements = json.loads(requirements_text)
                
                # Track tokens from Stage 1A
                stage1a_usage = extraction_response.usage
                total_prompt_tokens += stage1a_usage.prompt_tokens
                total_completion_tokens += stage1a_usage.completion_tokens
                total_tokens += stage1a_usage.total_tokens
                
                # Cache result
                vector_db.cache_jd_requirements(jd_hash_for_stage1a, requirements)
                logger.info(f"💾 Cached JD requirements for future use")
            
            logger.info(f"✓ Extracted requirements:")
            logger.info(f"  - Role: {requirements.get('role_type')}")
            logger.info(f"  - Must-have: {len(requirements.get('must_have_requirements', []))} items")
            logger.info(f"  - Nice-to-have: {len(requirements.get('nice_to_have_requirements', []))} items")
            
            stage1_time = time.time() - stage1_start
            logger.info(f"⏱️  Stage 1 completed in {stage1_time:.2f}s")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Error extracting requirements: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error analyzing JD: {str(e)}"
            )
        
        # STAGE 1B: Extract CV data and match with requirements
        logger.info("STAGE 1B: EXTRACTING CV DATA AND MATCHING")
        logger.info("=" * 80)
        
        stage1b_start = time.time()
        cv_list = []
        
        # Create JD hash for cache (extraction depends on both JD and PROMPT_LANGUAGE)
        # Number of CVs to return → Use separate max_cv_count field (does not affect cache)
        jd_cache_key = f"{jd_text}_{PROMPT_LANGUAGE}"
        jd_hash = hashlib.md5(jd_cache_key.encode('utf-8')).hexdigest()
        logger.info(f"JD hash (with lang={PROMPT_LANGUAGE}): {jd_hash[:16]}... (full: {jd_hash})")
        logger.info(f"JD text length: {len(jd_text)} chars")
        logger.info(f"JD text (first 200 chars): {jd_text[:200]}...")
        logger.info(f"JD text (last 100 chars): ...{jd_text[-100:]}")
        
        # Split CVs into batches using DYNAMIC batching (token-based)
        # Automatically calculates optimal batch size based on CV content length
        logger.info(f"🔄 Using DYNAMIC BATCHING (token-based) for {len(cv_data_list)} CVs...")
        cv_batches = calculate_optimal_batch_size(
            cvs=cv_data_list,
            requirements=requirements,
            max_tokens=120000,  # gpt-4o-mini context window
            model=OPENAI_MINI_MODEL
        )
        
        logger.info(f"✓ Split {len(cv_data_list)} CVs into {len(cv_batches)} dynamic batch(es)")
        
        try:
            # Process each batch
            extracted_cvs = []
            extraction_cache_hits = 0
            extraction_cache_misses = 0
            
            for batch_idx, cv_batch in enumerate(cv_batches, 1):
                logger.info(f"Extracting batch {batch_idx}/{len(cv_batches)} ({len(cv_batch)} CVs)...")
                
                # Check cache for each CV in batch
                batch_cached_cvs = []
                batch_uncached_cvs = []
                
                for cv in cv_batch:
                    cv_file_id = cv.get('file_id')
                    cv_content = cv.get('content', '')
                    cv_filename = cv.get('filename', 'unknown')
                    
                    # Debug: Log cache check
                    content_hash = hashlib.md5(cv_content.encode()).hexdigest()
                    doc_id = f"cv_{content_hash[:16]}_{jd_hash[:16]}"
                    logger.info(f"  🔍 Checking cache: {cv_filename} (file_id={cv_file_id}, doc_id={doc_id})")
                    
                    # Check cache (extraction depends on both CV and JD)
                    cached_data = vector_db.get_cached_extracted_cv_data(
                        cv_file_id, 
                        cv_content, 
                        jd_hash
                    )
                    
                    if cached_data:
                        extraction_cache_hits += 1
                        batch_cached_cvs.append(cached_data)
                        logger.info(f"  ✅ Cache HIT (extraction): {cv_filename} (file_id={cv_file_id})")
                    else:
                        extraction_cache_misses += 1
                        batch_uncached_cvs.append(cv)
                        logger.info(f"  ❌ Cache MISS (extraction): {cv_filename} (file_id={cv_file_id})")
                
                # If entire batch already cached, skip OpenAI
                if len(batch_uncached_cvs) == 0:
                    logger.info(f"Batch {batch_idx} - ✅ All {len(batch_cached_cvs)} CVs already cached, skipping OpenAI")
                    extracted_cvs.extend(batch_cached_cvs)
                    continue
                
                # Call OpenAI for uncached CVs
                logger.info(f"  🔄 Cache MISS (extraction): {len(batch_uncached_cvs)} CVs need OpenAI call...")
                
                # Format CV contents for this batch
                cv_contents_text = format_cv_contents(batch_uncached_cvs)
                cv_extraction_prompt = get_cv_extraction_prompt(cv_contents_text, requirements)
                
                # Debug: Print prompt length
                logger.info(f"Batch {batch_idx} - Prompt length: {len(cv_extraction_prompt)} chars (~{len(cv_extraction_prompt)//4} tokens)")
                
                # Call OpenAI with retry - use GPT-4o-mini for CV extraction (16x cheaper)
                logger.info(f"Calling OpenAI API ({OPENAI_MINI_MODEL}) for {len(batch_uncached_cvs)} CVs...")
                response = call_openai_with_retry(
                    messages=[
                        {"role": "system", "content": "You are a CV analysis expert. Return EXACTLY the JSON as requested."},
                        {"role": "user", "content": cv_extraction_prompt}
                    ],
                    model=OPENAI_MINI_MODEL
                )
                
                # Parse response
                batch_response_text = response.choices[0].message.content.strip()
                logger.info(f"Batch {batch_idx} - OpenAI response (first 300 chars): {batch_response_text[:300]}...")
                
                # Find JSON in response
                if "```json" in batch_response_text:
                    batch_response_text = batch_response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in batch_response_text:
                    batch_response_text = batch_response_text.split("```")[1].split("```")[0].strip()
                
                # Parse JSON
                batch_cv_data = json.loads(batch_response_text)
                
                # Ensure it's a list
                if not isinstance(batch_cv_data, list):
                    batch_cv_data = [batch_cv_data]
                
                # Cache extraction result for each CV
                for cv_data in batch_cv_data:
                    cv_id = cv_data.get('cv_id')
                    # Find original CV to get content
                    cv_original = next((cv for cv in batch_uncached_cvs if cv.get('cv_id') == cv_id), None)
                    if cv_original:
                        vector_db.cache_extracted_cv_data(
                            cv_original.get('file_id'),
                            cv_original.get('content', ''),
                            jd_hash,
                            cv_data
                        )
                
                # Track tokens from this batch
                batch_usage = response.usage
                total_prompt_tokens += batch_usage.prompt_tokens
                total_completion_tokens += batch_usage.completion_tokens
                total_tokens += batch_usage.total_tokens
                
                # Combine cached + newly extracted
                batch_all_cvs = batch_cached_cvs + batch_cv_data
                extracted_cvs.extend(batch_all_cvs)
                
                # Validate: Warn if extracted CV count != batch CV count
                if len(batch_all_cvs) != len(cv_batch):
                    logger.warning(f"⚠️  Batch {batch_idx} - Expected {len(cv_batch)} CVs, got {len(batch_all_cvs)} CVs (MISSING {len(cv_batch) - len(batch_all_cvs)} CV(s))")
                    missing_cv_ids = set([cv['cv_id'] for cv in cv_batch]) - set([cv.get('cv_id') for cv in batch_all_cvs])
                    if missing_cv_ids:
                        # Map cv_id to filename for readability
                        cv_id_to_name = {cv['cv_id']: cv['filename'] for cv in cv_batch}
                        missing_filenames = [cv_id_to_name.get(cv_id, cv_id) for cv_id in missing_cv_ids]
                        logger.warning(f"     ❌ Missing: {', '.join(missing_filenames)}")
                    logger.info(f"Batch {batch_idx} - ✅ Extracted {len(batch_all_cvs)}/{len(cv_batch)} CVs")
                else:
                    logger.info(f"Batch {batch_idx} - ✅ Extracted {len(batch_all_cvs)}/{len(cv_batch)} CVs (all complete)")
            
            # Log cache statistics
            total_cvs_to_extract = len(cv_data_list)
            cache_hit_rate = (extraction_cache_hits / total_cvs_to_extract * 100) if total_cvs_to_extract > 0 else 0
            logger.info("=" * 80)
            logger.info("📊 CV EXTRACTION CACHE STATISTICS:")
            logger.info(f"   Cache Hits: {extraction_cache_hits}/{total_cvs_to_extract} ({cache_hit_rate:.1f}%)")
            logger.info(f"   Cache Misses: {extraction_cache_misses}/{total_cvs_to_extract}")
            if extraction_cache_hits > 0:
                logger.info(f"   💰 Saved: ~{extraction_cache_hits * 500} tokens (estimated)")
            logger.info("=" * 80)
            
            stage1b_time = time.time() - stage1b_start
            logger.info(f"✓ Extracted {len(extracted_cvs)} CVs (from {len(cv_data_list)} CVs input)")
            logger.info(f"⏱️  Stage 1B completed in {stage1b_time:.2f}s")
            logger.info("=" * 80)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error from OpenAI: {e}")
            logger.error(f"Response text: {batch_response_text[:500] if 'batch_response_text' in locals() else 'N/A'}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"JSON parse error from OpenAI: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error extracting CV data: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error extracting CV data: {str(e)}"
            )
        
        # STAGE 2: Deterministic Scoring
        logger.info("STAGE 2: DETERMINISTIC SCORING")
        logger.info("=" * 80)
        
        stage2_start = time.time()
        scoring_engine = CVScoringEngine(requirements, advanced_options)
        
        for cv_data in extracted_cvs:
            # Calculate score
            score_result = scoring_engine.calculate_score(cv_data)
            
            # Build final CV object
            cv_item = {
                "cv_id": cv_data.get("cv_id"),
                "candidate_name": cv_data.get("candidate_name"),
                "email": cv_data.get("email"),
                "phone": cv_data.get("phone"),
                "position": cv_data.get("position"),
                "experience_years": cv_data.get("experience_years"),
                "skills": cv_data.get("skills", []),
                "education": cv_data.get("education", {}),
                "scope": {
                    "score": score_result["score"],
                    "matched_requirements": score_result["matched_requirements"],
                    "missing_requirements": score_result["missing_requirements"]
                },
                "mapping_description": score_result["mapping_description"]
            }
            
            # Add placeholder for advanced features if enabled (Stage 3 will override with real data)
            if advanced_options.get("cvPresentation", False):
                cv_item["cv_presentation_comment"] = None  # Stage 3 will override
            
            if advanced_options.get("interviewQuestions", False):
                cv_item["interview_questions"] = []  # Stage 3 will override
            
            if advanced_options.get("jobLeveling", False):
                cv_item["job_leveling"] = []  # Stage 3 will override
            
            if advanced_options.get("certBenefit", False):
                cv_item["cert_comment"] = None  # Stage 3 will override
            
            cv_list.append(cv_item)
        
        # Map back with file_id from database
        cv_id_to_file = {cv_data['cv_id']: cv_data['file_id'] for cv_data in cv_data_list}
        for cv_item in cv_list:
            cv_id = cv_item.get('cv_id', '')
            if cv_id in cv_id_to_file:
                cv_item['file_id'] = cv_id_to_file[cv_id]
        
        # Sort by score from high to low
        cv_list.sort(key=lambda x: x.get("scope", {}).get("score", 0), reverse=True)
        
        stage2_time = time.time() - stage2_start
        
        # Log scoring summary
        logger.info(f"✓ Scoring completed for {len(cv_list)} CVs")
        if cv_list:
            top_3 = cv_list[:3]
            for i, cv in enumerate(top_3, 1):
                logger.info(f"  {i}. {cv.get('candidate_name')}: {cv['scope']['score']:.1f}/100")
        logger.info(f"⏱️  Stage 2 completed in {stage2_time:.2f}s (deterministic, no API calls)")
        logger.info("=" * 80)
        
        # Filter to keep only CVs with score > 0 (BEFORE Stage 3)
        cv_list_before_filter = len(cv_list)
        cv_list = [cv for cv in cv_list if cv.get("scope", {}).get("score", 0) > 0]
        
        if cv_list_before_filter > len(cv_list):
            logger.info(f"Filtered: {cv_list_before_filter} CVs → {len(cv_list)} CVs (removed {cv_list_before_filter - len(cv_list)} CVs with score = 0)")
        else:
            logger.info(f"No CVs filtered (all {len(cv_list)} CVs have score > 0)")
        
        # Limit number of CVs per request (if any) - BEFORE Stage 3
        if requested_cv_count and requested_cv_count > 0:
            cv_list_before_limit = len(cv_list)
            cv_list = cv_list[:requested_cv_count]
            logger.info(f"Limited results: {cv_list_before_limit} CVs → {len(cv_list)} CVs (per request: top {requested_cv_count})")
        
        # STAGE 3: Advanced Features (MOVED DOWN HERE - AFTER LIMIT)
        # ONLY generate for final CVs to return
        stage3_time = 0
        has_advanced_options = any([
            # advanced_options.get("detectDuplicate", False),
            advanced_options.get("cvPresentation", False),
            advanced_options.get("interviewQuestions", False),
            advanced_options.get("jobLeveling", False),
            advanced_options.get("certBenefit", False)
        ])
        
        if has_advanced_options:
            logger.info("=" * 80)
            logger.info("STAGE 3: ADVANCED FEATURES GENERATION")
            logger.info("=" * 80)
            
            stage3_start = time.time()
            
            # Check cache for EACH individual CV
            cv_ids = [cv.get('file_id') for cv in cv_list]
            
            # DEBUG: Log cache key components
            import hashlib
            cv_ids_str = "_".join(sorted([str(id) for id in cv_ids]))
            cv_ids_hash = hashlib.md5(cv_ids_str.encode()).hexdigest()
            options_str = json.dumps(advanced_options, sort_keys=True)
            options_hash = hashlib.md5(options_str.encode()).hexdigest()
            cache_key = f"advanced_{jd_hash[:8]}_{cv_ids_hash[:8]}_{options_hash[:8]}"
            
            logger.info(f"🔍 STAGE 3 CACHE DEBUG:")
            logger.info(f"  JD hash: {jd_hash[:16]}...")
            logger.info(f"  CV IDs (sorted): {sorted(cv_ids)}")
            logger.info(f"  CV IDs hash: {cv_ids_hash[:16]}...")
            logger.info(f"  Options: {advanced_options}")
            logger.info(f"  Options hash: {options_hash[:16]}...")
            logger.info(f"  Cache key: {cache_key}")
            
            # LEVEL 1: Try bulk cache (fastest - 1 lookup for all CVs)
            cached_advanced = vector_db.get_cached_advanced_features(jd_hash, cv_ids, advanced_options)
            
            if cached_advanced:
                logger.info(f"📦 BULK Cache HIT: Stage 3 advanced features for ALL {len(cv_list)} CVs")
                advanced_data = cached_advanced
            else:
                # LEVEL 2: Try individual cache for each CV (more flexible)
                logger.info(f"🔄 BULK Cache MISS → Checking INDIVIDUAL cache for {len(cv_ids)} CVs...")
                
                cached_cvs = []
                uncached_cvs = []
                
                # Check individual cache for each CV
                collection = vector_db._get_or_create_collection(vector_db.ADVANCED_FEATURES_COLLECTION)
                for cv_item in cv_list:
                    cv_id = cv_item.get('cv_id')
                    file_id = cv_item.get('file_id')
                    
                    # Individual cache key: jd_hash + cv_id + options_hash
                    individual_doc_id = f"ind_adv_{jd_hash[:16]}_{cv_id}_{options_hash[:8]}"
                    
                    result = collection.get(ids=[individual_doc_id], include=["documents"])
                    
                    if result['ids'] and len(result['documents']) > 0:
                        cv_advanced = json.loads(result['documents'][0])
                        cached_cvs.append(cv_advanced)
                        logger.info(f"  ✓ Individual cache HIT: {cv_item.get('candidate_name', 'Unknown')} (cv_id={cv_id})")
                    else:
                        # Find corresponding extracted_cv for uncached CVs
                        extracted_cv = next((cv for cv in extracted_cvs if cv.get('cv_id') == cv_id), None)
                        if extracted_cv:
                            uncached_cvs.append(extracted_cv)
                            logger.info(f"  ✗ Individual cache MISS: {cv_item.get('candidate_name', 'Unknown')} (cv_id={cv_id})")
                
                logger.info(f"Individual cache status: {len(cached_cvs)} hits, {len(uncached_cvs)} misses")
                
                # Only generate features for uncached CVs
                newly_generated = []
                
                if len(uncached_cvs) > 0:
                    logger.info(f"🔄 Generating advanced features for {len(uncached_cvs)} uncached CVs...")
                    
                    # SPLIT INTO BATCHES to avoid response being too long and truncated
                    STAGE3_BATCH_SIZE = 1  # 1 CV/batch for Stage 3 (very long prompt with detailed examples)
                    
                    # Split into batches
                    stage3_batches = [uncached_cvs[i:i + STAGE3_BATCH_SIZE] for i in range(0, len(uncached_cvs), STAGE3_BATCH_SIZE)]
                    logger.info(f"Splitting {len(uncached_cvs)} CVs into {len(stage3_batches)} batch(es) ({STAGE3_BATCH_SIZE} CVs/batch)")
                    
                    for batch_idx, batch_extracted in enumerate(stage3_batches, 1):
                        logger.info(f"📦 Processing Stage 3 batch {batch_idx}/{len(stage3_batches)} ({len(batch_extracted)} CVs)...")
                        
                        # Generate prompt ONLY for this batch
                        advanced_prompt = get_stage3_advanced_prompt(batch_extracted, jd_text, requirements, advanced_options)
                        
                        if advanced_prompt:
                            # Call OpenAI
                            logger.info(f"Calling OpenAI API ({OPENAI_MINI_MODEL}) for batch {batch_idx}...")
                            stage3_response = call_openai_with_retry(
                                messages=[
                                    {"role": "system", "content": "You are an AI recruitment expert. IMPORTANT: You MUST return a COMPLETE JSON array with all required fields. DO NOT STOP in the middle. Ensure JSON has all closing brackets {{ }}, [ ] before finishing."},
                                    {"role": "user", "content": advanced_prompt}
                                ],
                                model=OPENAI_MINI_MODEL
                            )
                            
                            # Parse response
                            stage3_text = stage3_response.choices[0].message.content.strip()
                            finish_reason = stage3_response.choices[0].finish_reason
                            
                            # DEBUG: Log GPT response for job_leveling
                            logger.info("=" * 80)
                            logger.info(f"🔍 STAGE 3 BATCH {batch_idx} GPT RESPONSE DEBUG:")
                            logger.info(f"Response length: {len(stage3_text)} chars")
                            logger.info(f"Finish reason: {finish_reason}")
                            logger.info(f"First 500 chars: {stage3_text[:500]}")
                            logger.info(f"Last 200 chars: ...{stage3_text[-200:]}")
                            logger.info(f"Contains 'job_leveling': {'job_leveling' in stage3_text}")
                            logger.info("=" * 80)
                            
                            # Extract JSON - FIX: Get everything between first and last ```
                            if "```json" in stage3_text:
                                # Find position after ```json
                                start_idx = stage3_text.find("```json") + len("```json")
                                # Find last ``` position
                                end_idx = stage3_text.rfind("```")
                                if end_idx > start_idx:
                                    stage3_text = stage3_text[start_idx:end_idx].strip()
                            elif "```" in stage3_text:
                                # Find position after first ```
                                start_idx = stage3_text.find("```") + 3
                                # Find last ```
                                end_idx = stage3_text.rfind("```")
                                if end_idx > start_idx:
                                    stage3_text = stage3_text[start_idx:end_idx].strip()
                            
                            # Debug: Log GPT response before parsing
                            logger.info("=" * 80)
                            logger.info(f"🔍 STAGE 3 BATCH {batch_idx} GPT RESPONSE (first 1000 chars):")
                            logger.info(stage3_text[:1000])
                            logger.info("=" * 80)
                            
                            batch_generated = json.loads(stage3_text)
                            
                            # ✨ CRITICAL FIX: Validate and fix cv_id format
                            if isinstance(batch_generated, list):
                                for item in batch_generated:
                                    if 'cv_id' not in item or not item['cv_id']:
                                        logger.error(f"⚠️ GPT response missing cv_id: {item}")
                                        # Try to infer cv_id from batch_extracted
                                        if len(batch_extracted) == 1:
                                            item['cv_id'] = batch_extracted[0].get('cv_id')
                                            logger.warning(f"Fixed cv_id to: {item['cv_id']}")
                                    
                                    # ✨ NORMALIZE job_leveling to ARRAY (backward compatibility)
                                    if 'job_leveling' in item and isinstance(item['job_leveling'], str):
                                        item['job_leveling'] = [item['job_leveling']]
                                        logger.info(f"Normalized job_leveling to array for {item.get('cv_id')}: {item['job_leveling']}")
                            else:
                                # Single CV response
                                if 'cv_id' not in batch_generated or not batch_generated['cv_id']:
                                    if len(batch_extracted) == 1:
                                        batch_generated['cv_id'] = batch_extracted[0].get('cv_id')
                                        logger.warning(f"Fixed cv_id to: {batch_generated['cv_id']}")
                                
                                # Normalize job_leveling for single CV
                                if 'job_leveling' in batch_generated and isinstance(batch_generated['job_leveling'], str):
                                    batch_generated['job_leveling'] = [batch_generated['job_leveling']]
                                    logger.info(f"Normalized job_leveling to array: {batch_generated['job_leveling']}")
                            
                            # Track tokens
                            stage3_usage = stage3_response.usage
                            total_prompt_tokens += stage3_usage.prompt_tokens
                            total_completion_tokens += stage3_usage.completion_tokens
                            total_tokens += stage3_usage.total_tokens
                            
                            # Add to newly_generated
                            if isinstance(batch_generated, list):
                                newly_generated.extend(batch_generated)
                            else:
                                newly_generated.append(batch_generated)
                            
                            logger.info(f"✓ Batch {batch_idx} completed: Generated {len(batch_generated) if isinstance(batch_generated, list) else 1} CV(s)")
                    logger.info(f"✓ Stage 3 batching completed: Generated {len(newly_generated)} total CVs")
                    
                    # ✨ Cache INDIVIDUAL CVs (for flexibility when max_cv_count changes)
                    collection = vector_db._get_or_create_collection(vector_db.ADVANCED_FEATURES_COLLECTION)
                    for cv_advanced in newly_generated:
                        cv_id = cv_advanced.get('cv_id')
                        individual_doc_id = f"ind_adv_{jd_hash[:16]}_{cv_id}_{options_hash[:8]}"
                        
                        collection.upsert(
                            ids=[individual_doc_id],
                            documents=[json.dumps(cv_advanced)],
                            metadatas=[{
                                "jd_hash": jd_hash,
                                "cv_id": cv_id,
                                "options_hash": options_hash,
                                "cached_at": time.time()
                            }]
                        )
                    logger.info(f"✓ Cached INDIVIDUAL Stage 3 for {len(newly_generated)} newly generated CVs")
                
                # Merge cached + newly generated
                advanced_data = cached_cvs + newly_generated
                logger.info(f"Total advanced data: {len(cached_cvs)} cached + {len(newly_generated)} new = {len(advanced_data)} CVs")
                
                # ✨ Cache BULK for ALL CVs (for speed when same max_cv_count)
                # This ensures next run with same JD + same top CVs + same options → INSTANT cache hit
                vector_db.cache_advanced_features(jd_hash, cv_ids, advanced_options, advanced_data)
                logger.info(f"✓ Cached BULK Stage 3 advanced features for ALL {len(cv_ids)} CVs")
            
            # Merge advanced data into cv_list
            advanced_dict = {item.get('cv_id'): item for item in advanced_data}
            
            # DEBUG: Log cv_id formats to debug merge issue
            logger.info(f"🔍 DEBUG: advanced_dict keys: {list(advanced_dict.keys())[:5]}")
            logger.info(f"🔍 DEBUG: cv_list cv_ids: {[cv.get('cv_id') for cv in cv_list]}")
            
            for cv_item in cv_list:
                cv_id = cv_item.get('cv_id')
                if cv_id in advanced_dict:
                    advanced_item = advanced_dict[cv_id]
                    logger.debug(f"🔍 Merging advanced data for {cv_id}: {list(advanced_item.keys())}")
                    
                    # Merge fields
                    # if advanced_options.get("detectDuplicate") and 'duplicate_warning' in advanced_item:
                    #     cv_item["duplicate_warning"] = advanced_item["duplicate_warning"]
                    
                    if advanced_options.get("cvPresentation") and 'cv_presentation_comment' in advanced_item:
                        cv_item["cv_presentation_comment"] = advanced_item["cv_presentation_comment"]
                    
                    if advanced_options.get("interviewQuestions") and 'interview_questions' in advanced_item:
                        cv_item["interview_questions"] = advanced_item["interview_questions"]
                    
                    if advanced_options.get("jobLeveling") and 'job_leveling' in advanced_item:
                        cv_item["job_leveling"] = advanced_item["job_leveling"]
                    
                    if advanced_options.get("certBenefit") and 'cert_comment' in advanced_item:
                        cv_item["cert_comment"] = advanced_item["cert_comment"]
            
            # DEBUG: Check how many CVs got job_leveling
            cvs_with_job_leveling = [cv for cv in cv_list if cv.get('job_leveling') is not None]
            logger.info(f"📊 After merge: {len(cvs_with_job_leveling)}/{len(cv_list)} CVs have job_leveling")
            if len(cvs_with_job_leveling) < len(cv_list):
                missing_job_leveling = [cv.get('cv_id') for cv in cv_list if cv.get('job_leveling') is None]
                logger.warning(f"⚠️ Missing job_leveling for CVs: {missing_job_leveling}")
            
            stage3_time = time.time() - stage3_start
            logger.info(f"⏱️  Stage 3 completed in {stage3_time:.2f}s")
            logger.info("=" * 80)
        
        # Filter/limit already moved up before Stage 3
        
        total_time = time.time() - stage1_start
        
        # Calculate estimated cost
        # Stage 1A: gpt-4o ($2.50 input, $10.00 output per 1M tokens)
        # Stage 1B: gpt-4o-mini ($0.150 input, $0.600 output per 1M tokens)
        
        if stage1a_usage:
            # Cache MISS - has token usage from OpenAI
            stage1a_tokens = stage1a_usage.prompt_tokens + stage1a_usage.completion_tokens
            stage1b_prompt = total_prompt_tokens - stage1a_usage.prompt_tokens
            stage1b_completion = total_completion_tokens - stage1a_usage.completion_tokens
            
            cost_1a_input = (stage1a_usage.prompt_tokens / 1_000_000) * 2.50
            cost_1a_output = (stage1a_usage.completion_tokens / 1_000_000) * 10.00
        else:
            # Cache HIT - no token usage for Stage 1A
            stage1a_tokens = 0
            stage1b_prompt = total_prompt_tokens
            stage1b_completion = total_completion_tokens
            
            cost_1a_input = 0
            cost_1a_output = 0
        
        cost_1b_input = (stage1b_prompt / 1_000_000) * 0.150
        cost_1b_output = (stage1b_completion / 1_000_000) * 0.600
        total_cost = cost_1a_input + cost_1a_output + cost_1b_input + cost_1b_output
        
        logger.info("=" * 80)
        logger.info(f"✅ THREE-STAGE HYBRID APPROACH COMPLETED in {total_time:.2f}s")
        logger.info(f"  📋 Database: {total_cvs} CVs total")
        
        # Detail unreadable CVs
        if unreadable_cvs:
            logger.info(f"  📄 Readable: {len(cv_data_list)} CVs (skipped {len(unreadable_cvs)} unreadable)")
            logger.info(f"     ⚠️  Unreadable: {', '.join(unreadable_cvs)}")
        else:
            logger.info(f"  📄 Readable: {len(cv_data_list)} CVs (all readable ✓)")
        
        logger.info(f"  🔍 Stage 1A (JD): {len(requirements.get('must_have_requirements', []))} must-haves, {len(requirements.get('nice_to_have_requirements', []))} nice-to-haves)")
        
        # Detail CVs skipped by LLM
        missing_count = len(cv_data_list) - len(extracted_cvs)
        if missing_count > 0:
            # Find which CVs were skipped
            extracted_cv_ids = {cv.get('cv_id') for cv in extracted_cvs}
            skipped_cvs = [cv['filename'] for cv in cv_data_list if cv.get('cv_id') not in extracted_cv_ids]
            
            logger.info(f"  🤖 Stage 1B (Extract): {len(extracted_cvs)} CVs extracted using {OPENAI_MINI_MODEL}")
            logger.info(f"     ⚠️  LLM skipped {missing_count} CV(s) during extraction:")
            for skipped in skipped_cvs:
                logger.info(f"        - {skipped}")
        else:
            logger.info(f"  🤖 Stage 1B (Extract): {len(extracted_cvs)} CVs extracted using {OPENAI_MINI_MODEL} (all extracted ✓)")
        
        logger.info(f"  ⚙️  Stage 2 (Score): {cv_list_before_filter} CVs scored → {len(cv_list)} CVs returned")
        
        if has_advanced_options:
            logger.info(f"  ✨ Stage 3 (Advanced): Generated features for {len(cv_list)} CVs")
        
        logger.info(f"")
        logger.info(f"  📊 Token Usage:")
        logger.info(f"     Input: {total_prompt_tokens:,} tokens")
        logger.info(f"     Output: {total_completion_tokens:,} tokens")
        logger.info(f"     Total: {total_tokens:,} tokens")
        logger.info(f"  💰 Estimated Cost: ${total_cost:.4f}")
        logger.info(f"     Stage 1A ({OPENAI_MODEL}): ${cost_1a_input + cost_1a_output:.4f}")
        logger.info(f"     Stage 1B ({OPENAI_MINI_MODEL}): ${cost_1b_input + cost_1b_output:.4f}")
        if stage3_time > 0:
            logger.info(f"  ⏱️  Total time: Stage 1A={stage1_time:.1f}s + Stage 1B={stage1b_time:.1f}s + Stage 2={stage2_time:.1f}s + Stage 3={stage3_time:.1f}s = {total_time:.1f}s")
        else:
            logger.info(f"  ⏱️  Total time: Stage 1A={stage1_time:.1f}s + Stage 1B={stage1b_time:.1f}s + Stage 2={stage2_time:.1f}s = {total_time:.1f}s")
        logger.info("=" * 80)
        
        # Return results
        return {
            "status": "success",
            "message": f"Matched {len(cv_list)} CVs with JD",
            "received_data": received_data,
            "cv_mappings": cv_list,
            "total_cvs_processed": len(cv_data_list),
            "total_cvs_matched": len(cv_list)
        }
    
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing request: {str(e)}"
        )

