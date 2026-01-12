"""Routes cho Thinking endpoint - đối chiếu CV với JD"""
import logging
import json
import numpy as np
import re
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, status, Request
from openai import OpenAI
from db.database import get_all_files
from config import CV_DIRECTORY, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MINI_MODEL, OPENAI_EMBEDDING_MODEL
from prompts import get_cv_matching_prompt, get_system_message, format_cv_contents, get_extraction_prompt, get_cv_extraction_prompt, get_stage3_advanced_prompt
from utils import clean_text_for_embedding
from db import vector_db

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cấu hình OpenAI
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY không được tìm thấy trong biến môi trường. Vui lòng tạo file .env và thêm OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

router = APIRouter(prefix="/thinking", tags=["Thinking"])


class CVScoringEngine:
    """
    Stage 2: Deterministic scoring engine
    Tính điểm dựa trên structured data từ Stage 1
    """
    
    def __init__(self, requirements: dict, advanced_options: dict = None):
        """
        Args:
            requirements: Requirements từ JD (output của Stage 1)
            advanced_options: Tùy chọn nâng cao
        """
        self.requirements = requirements
        self.advanced_options = advanced_options or {}
        self.must_have_count = len(requirements.get('must_have_requirements', []))
        self.nice_to_have_count = len(requirements.get('nice_to_have_requirements', []))
    
    def calculate_score(self, cv_data: dict) -> dict:
        """
        Tính điểm cho 1 CV dựa trên extracted data
        
        Args:
            cv_data: CV data từ Stage 1 (bao gồm must_have_matched, nice_to_have_matched)
        
        Returns:
            dict: Kết quả scoring với score, matched_requirements, missing_requirements
        """
        # Đếm must-have matched
        must_have_matched = [m for m in cv_data.get('must_have_matched', []) if m.get('matched')]
        must_have_missing = [m for m in cv_data.get('must_have_matched', []) if not m.get('matched')]
        
        # Đếm nice-to-have matched
        nice_to_have_matched = [m for m in cv_data.get('nice_to_have_matched', []) if m.get('matched')]
        
        # Tính % must-have đạt được
        if self.must_have_count > 0:
            must_have_percentage = len(must_have_matched) / self.must_have_count
        else:
            must_have_percentage = 1.0  # Nếu không có must-have thì coi như đạt 100%
        
        # Base score từ must-have (0-90 điểm)
        base_score = must_have_percentage * 90
        
        # Bonus từ nice-to-have (0-10 điểm)
        if self.nice_to_have_count > 0:
            nice_to_have_bonus = (len(nice_to_have_matched) / self.nice_to_have_count) * 10
        else:
            nice_to_have_bonus = 0
        
        # Tổng điểm
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
        candidate_name = cv_data.get('candidate_name', 'Ứng viên')
        
        if must_have_pct >= 1.0:
            desc = f"{candidate_name} đáp ứng đầy đủ {must_total}/{must_total} yêu cầu bắt buộc."
        elif must_have_pct >= 0.8:
            desc = f"{candidate_name} đáp ứng {must_matched}/{must_total} yêu cầu bắt buộc (thiếu {must_total - must_matched})."
        elif must_have_pct >= 0.5:
            desc = f"{candidate_name} chỉ đáp ứng {must_matched}/{must_total} yêu cầu bắt buộc, thiếu một số yêu cầu quan trọng."
        else:
            desc = f"{candidate_name} chưa đáp ứng đủ yêu cầu, chỉ có {must_matched}/{must_total} yêu cầu bắt buộc."
        
        if nice_total > 0:
            desc += f" Có {nice_matched}/{nice_total} kỹ năng ưu tiên."
        
        return desc


def extract_text_from_pdf(file_path: Path) -> str:
    """Đọc nội dung text từ file PDF"""
    try:
        import PyPDF2
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except ImportError:
        logger.warning("PyPDF2 chưa được cài đặt, thử pypdf...")
        try:
            import pypdf
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        except ImportError:
            logger.error("Không tìm thấy thư viện đọc PDF (PyPDF2 hoặc pypdf)")
            return ""
    except Exception as e:
        logger.error(f"Lỗi khi đọc PDF {file_path}: {e}")
        return ""


def extract_text_from_docx(file_path: Path) -> str:
    """Đọc nội dung text từ file DOCX"""
    try:
        from docx import Document
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    except ImportError:
        logger.error("python-docx chưa được cài đặt")
        return ""
    except Exception as e:
        logger.error(f"Lỗi khi đọc DOCX {file_path}: {e}")
        return ""


def extract_text_from_cv(file_path: str) -> str:
    """Đọc nội dung text từ file CV (PDF hoặc DOCX)"""
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"File không tồn tại: {file_path}")
        return ""
    
    extension = path.suffix.lower()
    if extension == ".pdf":
        return extract_text_from_pdf(path)
    elif extension in [".docx", ".doc"]:
        return extract_text_from_docx(path)
    else:
        logger.warning(f"Định dạng file không được hỗ trợ: {extension}")
        return ""


def get_embedding(text: str, cache_id: Optional[int] = None, cache_type: Optional[str] = None) -> list:
    """
    Tạo embedding vector cho text sử dụng OpenAI Embeddings API với cache
    
    Args:
        text: Text cần tạo embedding
        cache_id: ID để cache (file_id cho CV/JD)
        cache_type: Loại cache ('cv' hoặc 'jd')
        
    Returns:
        list: Embedding vector (1536 chiều)
    """
    # Kiểm tra cache nếu có cache_id và cache_type
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
    
    # Không có cache, tạo mới qua API
    try:
        logger.info(f"🔄 Generating new embedding via OpenAI API ({OPENAI_EMBEDDING_MODEL})...")
        # Clean text trước khi gửi API (loại bỏ emoji, ký tự đặc biệt)
        cleaned_text = clean_text_for_embedding(text)
        response = client.embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,
            input=cleaned_text  # Use cleaned text for embedding
        )
        embedding = response.data[0].embedding
        
        # Lưu vào cache nếu có cache_id và cache_type
        if cache_id and cache_type and embedding:
            filename = f"{cache_type}_{cache_id}"
            if cache_type == 'cv':
                vector_db.cache_cv_embedding(cache_id, filename, text, embedding)
            elif cache_type == 'jd':
                vector_db.cache_jd_embedding(filename, text, embedding)
        
        return embedding
    except Exception as e:
        logger.error(f"Lỗi khi tạo embedding: {e}")
        return []


def cosine_similarity(vec1: list, vec2: list) -> float:
    """
    Tính cosine similarity giữa 2 vectors
    
    Args:
        vec1: Vector thứ nhất
        vec2: Vector thứ hai
        
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
    Pre-filter CVs bằng vector similarity
    
    Args:
        cv_data_list: Danh sách tất cả CVs
        jd_text: Job Description
        response_requirement: Yêu cầu phản hồi
        top_n: Số lượng CVs muốn lấy
        
    Returns:
        list: Top N CVs có similarity cao nhất
    """
    try:
        logger.info("=" * 80)
        logger.info("STAGE 1: PRE-FILTERING VỚI VECTOR SIMILARITY")
        logger.info("=" * 80)
        
        # Cache JD embedding riêng
        # Dùng MD5 hash của JD text làm cache_id
        jd_hash = hashlib.md5(jd_text.encode('utf-8')).hexdigest()
        jd_cache_id = int(jd_hash[:8], 16)  # Lấy 8 ký tự đầu convert sang int
        
        logger.info(f"Đang tạo embedding cho JD (với cache)...")
        jd_embedding = get_embedding(jd_text, cache_id=jd_cache_id, cache_type='jd')
        
        if jd_embedding is None or len(jd_embedding) == 0:
            logger.warning("Không tạo được JD embedding, bỏ qua pre-filtering")
            return cv_data_list
        
        # Note: response_requirement chỉ chứa metadata (số lượng CVs)
        # KHÔNG cần embedding vì không ảnh hưởng semantic similarity
        # Số lượng CVs được parse và apply ở stage cuối
        
        # Tạo embeddings cho tất cả CVs với cache
        logger.info(f"Đang tạo embeddings cho {len(cv_data_list)} CVs (với cache)...")
        cv_embeddings = []
        cache_hits = 0
        cache_misses = 0
        
        for cv in cv_data_list:
            cv_file_id = cv.get('file_id')  # Fix: use 'file_id' not 'id'
            cv_filename = cv.get('filename', f'CV_{cv_file_id}')
            cv_content = cv.get('content', '')
            
            # Check cache trước
            cached = vector_db.get_cached_cv_embedding(cv_file_id, cv_content)
            if cached is not None and len(cached) > 0:
                cache_hits += 1
                cv_embeddings.append(cached)
                logger.info(f"  📦 Cache HIT: {cv_filename} (file_id={cv_file_id})")
            else:
                cache_misses += 1
                logger.info(f"  🔄 Cache MISS: {cv_filename} (file_id={cv_file_id}) - Gọi OpenAI API...")
                # Lấy embedding (tự động check cache trong get_embedding)
                embedding = get_embedding(cv_content, cache_id=cv_file_id, cache_type='cv')
                
                if embedding:
                    cv_embeddings.append(embedding)
                else:
                    logger.warning(f"Không tạo được embedding cho CV {cv_file_id}")
                    cv_embeddings.append([])
        
        logger.info(f"✅ Embedding cache: {cache_hits} hits, {cache_misses} misses ({cache_hits/(cache_hits+cache_misses)*100:.1f}% hit rate)")
        
        # Tính similarity scores
        logger.info("Đang tính cosine similarity...")
        similarities = []
        for i, cv_emb in enumerate(cv_embeddings):
            sim = cosine_similarity(jd_embedding, cv_emb)
            similarities.append({
                'cv': cv_data_list[i],
                'similarity': sim
            })
        
        # Sort theo similarity giảm dần
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Log kết quả
        logger.info(f"Top 10 similarity scores:")
        for i, item in enumerate(similarities[:10], 1):
            logger.info(f"  {i}. {item['cv']['filename']}: {item['similarity']:.4f}")
        
        # Lấy top N
        actual_top_n = min(top_n, len(similarities))
        top_cvs = [item['cv'] for item in similarities[:actual_top_n]]
        
        logger.info(f"Pre-filtering: {len(cv_data_list)} CVs → {len(top_cvs)} CVs (similarity >= {similarities[actual_top_n-1]['similarity']:.4f})")
        logger.info("=" * 80)
        
        return top_cvs
        
    except Exception as e:
        logger.error(f"Lỗi trong pre-filtering: {e}", exc_info=True)
        logger.warning("Fallback: Sử dụng tất cả CVs")
        return cv_data_list


@router.post("/")
async def thinking_dump(request: Request):
    """
    Endpoint để dump/log tất cả các giá trị từ client gửi lên
    Tất cả các trường đều optional (không bắt buộc)
    Hỗ trợ cả text fields và file uploads
    
    Args:
        request: FastAPI Request object
    
    Returns:
        dict: Tất cả các giá trị đã nhận được
    """
    try:
        # Parse form data (hỗ trợ cả text và file)
        form_data = await request.form()
        
        # Debug: Log các keys có trong form
        logger.info("=" * 80)
        logger.info("THINKING ENDPOINT - Nhận request")
        logger.info(f"Form data keys: {list(form_data.keys())}")
        logger.info("=" * 80)
        
        # Helper function để xử lý giá trị từ form_data
        async def process_form_value(key: str):
            """Xử lý giá trị từ form_data, hỗ trợ cả string và file"""
            if key not in form_data:
                return None
            
            value = form_data[key]
            
            # Nếu là UploadFile (file upload)
            if hasattr(value, 'read'):
                try:
                    # Đọc file content
                    content = await value.read()
                    file_info = {
                        "filename": value.filename,
                        "content_type": value.content_type,
                        "size": len(content) if isinstance(content, bytes) else 0,
                        "is_binary": True
                    }
                    # Nếu là text file, decode
                    if isinstance(content, bytes):
                        try:
                            text_content = content.decode('utf-8')
                            file_info["text_content"] = text_content
                        except UnicodeDecodeError:
                            file_info["text_content"] = None
                    return file_info
                except Exception as e:
                    logger.warning(f"Lỗi khi đọc file {key}: {e}")
                    return {"error": str(e), "is_binary": True}
            
            # Nếu là string
            str_value = str(value) if value else None
            if str_value and str_value.strip():
                return str_value
            return None
        
        # Xử lý tất cả các trường từ form_data
        received_data = {}
        for key in form_data.keys():
            processed_value = await process_form_value(key)
            received_data[key] = processed_value
        
        # Log tất cả giá trị
        logger.info("=" * 80)
        logger.info("THINKING ENDPOINT - Dump các giá trị từ client:")
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
        
        # Print ra console để dễ debug
        print("\n" + "=" * 80)
        print("THINKING ENDPOINT - Dump các giá trị từ client:")
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
        
        # Lấy dữ liệu từ form
        jd_text = received_data.get("jd_text", "")
        response_requirement = received_data.get("response_requirement", "")
        advanced_options_str = received_data.get("advanced_options", "{}")
        
        # Parse advanced_options nếu là string
        try:
            if isinstance(advanced_options_str, str):
                advanced_options = json.loads(advanced_options_str)
            else:
                advanced_options = advanced_options_str
        except:
            advanced_options = {}
        
        # Lấy tất cả CV từ database
        logger.info("Đang lấy danh sách CV từ database...")
        cv_files, total_cvs = get_all_files(limit=1000, offset=0, file_type="cv")
        logger.info(f"Tìm thấy {total_cvs} CV trong database")
        
        if total_cvs == 0:
            logger.warning("Không có CV nào trong database")
            return {
                "status": "success",
                "message": "Không tìm thấy CV nào trong database",
                "received_data": received_data,
                "cv_mappings": []
            }
        
        # Lấy nội dung từng CV từ database (cột content)
        cv_data_list = []
        unreadable_cvs = []  # Track CVs không đọc được
        for cv_file in cv_files:
            file_path = cv_file.get("file_path", "")
            if not file_path:
                continue
            
            logger.info(f"Đang lấy nội dung CV: {cv_file.get('original_filename', 'unknown')}")
            
            # Ưu tiên lấy từ cột content trong database
            cv_text = cv_file.get("content")
            
            # Nếu không có content trong database, fallback về đọc file (cho CV cũ)
            if not cv_text or not cv_text.strip():
                logger.info(f"CV {cv_file.get('original_filename', 'unknown')} chưa có content trong DB, đang đọc từ file...")
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
                logger.warning(f"Không thể lấy nội dung CV: {unreadable_filename}")
        
        if not cv_data_list:
            logger.warning("Không có CV nào có thể đọc được nội dung")
            return {
                "status": "success",
                "message": "Không thể đọc nội dung từ các CV",
                "received_data": received_data,
                "cv_mappings": []
            }
        
        logger.info(f"Đã đọc được {len(cv_data_list)} CV")
        logger.info(f"Advanced options: {advanced_options}")
        
        # Debug: Log JD text hash để detect duplicates
        import hashlib
        jd_hash_preview = hashlib.md5(jd_text.encode('utf-8')).hexdigest()
        logger.info("=" * 80)
        logger.info("🔍 JD TEXT DEBUG:")
        logger.info(f"   Length: {len(jd_text)} chars")
        logger.info(f"   MD5 Hash: {jd_hash_preview}")
        logger.info(f"   First 200 chars: {jd_text[:200]}")
        logger.info(f"   Last 100 chars: {jd_text[-100:]}")
        logger.info("=" * 80)
        
        # Lấy số lượng CV cần trả về từ payload (max_cv_count) hoặc parse từ response_requirement
        requested_cv_count = None
        
        # Ưu tiên lấy từ max_cv_count trong payload
        max_cv_count_value = received_data.get("max_cv_count")
        
        if max_cv_count_value is not None and isinstance(max_cv_count_value, str):
            try:
                # Xử lý string, loại bỏ khoảng trắng
                stripped = max_cv_count_value.strip()
                if stripped:  # Chỉ convert nếu không rỗng
                    requested_cv_count = int(stripped)
                    logger.info(f"✅ Lấy max_cv_count từ payload: {requested_cv_count}")
                else:
                    logger.warning(f"max_cv_count là string rỗng, bỏ qua")
            except (ValueError, TypeError) as e:
                logger.warning(f"max_cv_count không hợp lệ: {max_cv_count_value} (error: {e}), sẽ thử parse từ response_requirement")
        
        # Fallback: Parse từ response_requirement nếu không có max_cv_count
        if requested_cv_count is None and response_requirement:
            # Tìm pattern như "2 CV", "top 3", "3 ứng viên", etc.
            patterns = [
                r'(?:lấy|trả về|cho|top)\s*(\d+)\s*(?:cv|ứng viên|candidate)',
                r'(\d+)\s*(?:cv|ứng viên|candidate)',
            ]
            for pattern in patterns:
                match = re.search(pattern, response_requirement.lower())
                if match:
                    requested_cv_count = int(match.group(1))
                    logger.info(f"Phát hiện yêu cầu số lượng CV: {requested_cv_count}")
                    break
        
        # STAGE 1: Pre-filter CVs bằng vector similarity
        # Luôn tạo embeddings để cache, chỉ filter khi có nhiều CVs
        PRE_FILTER_THRESHOLD = 50  # Ngưỡng để áp dụng filtering (không ảnh hưởng cache)
        
        # Tính số lượng CVs cần pre-filter dựa trên yêu cầu
        if requested_cv_count:
            PRE_FILTER_TOP_N = max(requested_cv_count * 5, 30)
        else:
            PRE_FILTER_TOP_N = 50
        
        # LUÔN LUÔN tạo embeddings để cache (bất kể số CVs)
        # Chỉ áp dụng filtering khi vượt threshold
        if len(cv_data_list) > PRE_FILTER_THRESHOLD:
            logger.info(f"Sẽ pre-filter xuống {PRE_FILTER_TOP_N} CVs (buffer cho {requested_cv_count or 'all'} CVs yêu cầu)")
            top_n = PRE_FILTER_TOP_N
        else:
            logger.info(f"Tạo embeddings cho cache (không filter vì chỉ có {len(cv_data_list)} CVs)")
            top_n = len(cv_data_list)  # Không filter, nhưng vẫn tạo cache
        
        cv_data_list = pre_filter_cvs_by_similarity(
            cv_data_list, 
            jd_text, 
            response_requirement, 
            top_n=top_n  # Truyền len(cv_data_list) nếu không filter
        )
        logger.info(f"Sau pre-filtering: {len(cv_data_list)} CVs")
        
        # Define helper function for OpenAI retry logic
        def call_openai_with_retry(messages, max_retries=5, model=None):
            """Gọi OpenAI API với exponential backoff retry"""
            if model is None:
                model = OPENAI_MODEL
            
            for attempt in range(max_retries):
                try:
                    start_time = time.time()
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0,  # 0 = hoàn toàn deterministic
                        max_tokens=6000  # Đủ cho 5-8 CVs/batch, không quá lớn
                    )
                    elapsed_time = time.time() - start_time
                    
                    # Log token usage và thời gian
                    usage = response.usage
                    logger.info(f"  ⏱️  {elapsed_time:.2f}s | 📊 Tokens: {usage.prompt_tokens} in + {usage.completion_tokens} out = {usage.total_tokens} total")
                    
                    return response
                except Exception as e:
                    if "rate_limit" in str(e).lower() or "429" in str(e):
                        wait_time = min(2 ** attempt, 20)  # Max 20 giây
                        logger.warning(f"Rate limit hit, waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        if attempt == max_retries - 1:
                            raise
                    else:
                        raise
        
        # STAGE 1: Extract requirements từ JD
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
            # Extract requirements từ JD - dùng GPT-4o cho accuracy cao
            extraction_prompt = get_extraction_prompt(jd_text, response_requirement)
            logger.info(f"Đang gọi OpenAI ({OPENAI_MODEL}) để extract requirements từ JD...")
            
            extraction_response = call_openai_with_retry(
                messages=[
                    {"role": "system", "content": "Bạn là một chuyên gia phân tích Job Description. Trả về CHÍNH XÁC JSON như yêu cầu."},
                    {"role": "user", "content": extraction_prompt}
                ],
                model=OPENAI_MODEL
            )
            
            requirements_text = extraction_response.choices[0].message.content.strip()
            
            # Parse JSON từ response
            if "```json" in requirements_text:
                requirements_text = requirements_text.split("```json")[1].split("```")[0].strip()
            elif "```" in requirements_text:
                requirements_text = requirements_text.split("```")[1].split("```")[0].strip()
            
            requirements = json.loads(requirements_text)
            
            # Track tokens từ Stage 1A
            stage1a_usage = extraction_response.usage
            total_prompt_tokens += stage1a_usage.prompt_tokens
            total_completion_tokens += stage1a_usage.completion_tokens
            total_tokens += stage1a_usage.total_tokens
            
            logger.info(f"✓ Extracted requirements:")
            logger.info(f"  - Role: {requirements.get('role_type')}")
            logger.info(f"  - Must-have: {len(requirements.get('must_have_requirements', []))} items")
            logger.info(f"  - Nice-to-have: {len(requirements.get('nice_to_have_requirements', []))} items")
            
            stage1_time = time.time() - stage1_start
            logger.info(f"⏱️  Stage 1 completed in {stage1_time:.2f}s")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Lỗi khi extract requirements: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi phân tích JD: {str(e)}"
            )
        
        # STAGE 1B: Extract CV data và match với requirements
        logger.info("STAGE 1B: EXTRACTING CV DATA AND MATCHING")
        logger.info("=" * 80)
        
        stage1b_start = time.time()
        cv_list = []
        
        # Tạo JD hash để dùng cho cache (extraction phụ thuộc vào JD)
        # Số lượng CV cần return → Dùng field max_cv_count riêng (không ảnh hưởng cache)
        jd_hash = hashlib.md5(jd_text.encode('utf-8')).hexdigest()
        logger.info(f"JD hash: {jd_hash[:16]}... (full: {jd_hash})")
        logger.info(f"JD text length: {len(jd_text)} chars")
        logger.info(f"JD text (first 200 chars): {jd_text[:200]}...")
        logger.info(f"JD text (last 100 chars): ...{jd_text[-100:]}")
        
        # Chia CVs thành các batch để tối ưu chi phí và tránh truncate
        # gpt-4o-mini output ngắn hơn gpt-4o → có thể tăng batch size
        BATCH_SIZE = 7  # Sweet spot: vừa tiết kiệm (6 batches vs 8), vừa an toàn
        cv_batches = [cv_data_list[i:i + BATCH_SIZE] for i in range(0, len(cv_data_list), BATCH_SIZE)]
        
        logger.info(f"Chia {len(cv_data_list)} CVs thành {len(cv_batches)} batch(es) ({BATCH_SIZE} CVs/batch)")
        
        try:
            # Xử lý từng batch
            extracted_cvs = []
            extraction_cache_hits = 0
            extraction_cache_misses = 0
            
            for batch_idx, cv_batch in enumerate(cv_batches, 1):
                logger.info(f"Đang extract batch {batch_idx}/{len(cv_batches)} ({len(cv_batch)} CVs)...")
                
                # Check cache cho từng CV trong batch
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
                    
                    # Check cache (extraction phụ thuộc cả CV lẫn JD)
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
                
                # Nếu toàn bộ batch đã có cache, bỏ qua OpenAI
                if len(batch_uncached_cvs) == 0:
                    logger.info(f"Batch {batch_idx} - ✅ Tất cả {len(batch_cached_cvs)} CVs đã có cache, bỏ qua OpenAI")
                    extracted_cvs.extend(batch_cached_cvs)
                    continue
                
                # Gọi OpenAI cho các CVs chưa có cache
                logger.info(f"  🔄 Cache MISS (extraction): {len(batch_uncached_cvs)} CVs cần gọi OpenAI...")
                
                # Format CV contents cho batch này
                cv_contents_text = format_cv_contents(batch_uncached_cvs)
                cv_extraction_prompt = get_cv_extraction_prompt(cv_contents_text, requirements)
                
                # Debug: In độ dài prompt
                logger.info(f"Batch {batch_idx} - Prompt length: {len(cv_extraction_prompt)} chars (~{len(cv_extraction_prompt)//4} tokens)")
                
                # Gọi OpenAI với retry - dùng GPT-4o-mini cho CV extraction (rẻ hơn 16 lần)
                logger.info(f"Đang gọi OpenAI API ({OPENAI_MINI_MODEL}) cho {len(batch_uncached_cvs)} CVs...")
                response = call_openai_with_retry(
                    messages=[
                        {"role": "system", "content": "Bạn là một chuyên gia phân tích CV. Trả về CHÍNH XÁC JSON như yêu cầu."},
                        {"role": "user", "content": cv_extraction_prompt}
                    ],
                    model=OPENAI_MINI_MODEL
                )
                
                # Parse response
                batch_response_text = response.choices[0].message.content.strip()
                logger.info(f"Batch {batch_idx} - OpenAI response (first 300 chars): {batch_response_text[:300]}...")
                
                # Tìm JSON trong response
                if "```json" in batch_response_text:
                    batch_response_text = batch_response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in batch_response_text:
                    batch_response_text = batch_response_text.split("```")[1].split("```")[0].strip()
                
                # Parse JSON
                batch_cv_data = json.loads(batch_response_text)
                
                # Đảm bảo là list
                if not isinstance(batch_cv_data, list):
                    batch_cv_data = [batch_cv_data]
                
                # Cache kết quả extraction cho từng CV
                for cv_data in batch_cv_data:
                    cv_id = cv_data.get('cv_id')
                    # Tìm CV gốc để lấy content
                    cv_original = next((cv for cv in batch_uncached_cvs if cv.get('cv_id') == cv_id), None)
                    if cv_original:
                        vector_db.cache_extracted_cv_data(
                            cv_original.get('file_id'),
                            cv_original.get('content', ''),
                            jd_hash,
                            cv_data
                        )
                
                # Track tokens từ batch này
                batch_usage = response.usage
                total_prompt_tokens += batch_usage.prompt_tokens
                total_completion_tokens += batch_usage.completion_tokens
                total_tokens += batch_usage.total_tokens
                
                # Kết hợp cached + newly extracted
                batch_all_cvs = batch_cached_cvs + batch_cv_data
                extracted_cvs.extend(batch_all_cvs)
                
                # Validate: Cảnh báo nếu số CV extract != số CV trong batch
                if len(batch_all_cvs) != len(cv_batch):
                    logger.warning(f"⚠️  Batch {batch_idx} - Expected {len(cv_batch)} CVs, got {len(batch_all_cvs)} CVs (MISSING {len(cv_batch) - len(batch_all_cvs)} CV(s))")
                    missing_cv_ids = set([cv['cv_id'] for cv in cv_batch]) - set([cv.get('cv_id') for cv in batch_all_cvs])
                    if missing_cv_ids:
                        # Map cv_id về filename để dễ đọc
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
                logger.info(f"   💰 Saved: ~{extraction_cache_hits * 500} tokens (ước tính)")
            logger.info("=" * 80)
            
            stage1b_time = time.time() - stage1b_start
            logger.info(f"✓ Đã extract {len(extracted_cvs)} CVs (từ {len(cv_data_list)} CVs input)")
            logger.info(f"⏱️  Stage 1B completed in {stage1b_time:.2f}s")
            logger.info("=" * 80)
            
        except json.JSONDecodeError as e:
            logger.error(f"Lỗi parse JSON từ OpenAI: {e}")
            logger.error(f"Response text: {batch_response_text[:500] if 'batch_response_text' in locals() else 'N/A'}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi parse JSON từ OpenAI: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Lỗi khi extract CV data: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi extract CV data: {str(e)}"
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
        
        # Map lại với file_id từ database
        cv_id_to_file = {cv_data['cv_id']: cv_data['file_id'] for cv_data in cv_data_list}
        for cv_item in cv_list:
            cv_id = cv_item.get('cv_id', '')
            if cv_id in cv_id_to_file:
                cv_item['file_id'] = cv_id_to_file[cv_id]
        
        # Sắp xếp theo điểm từ cao đến thấp
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
        
        # Lọc chỉ giữ CV có score > 0 (TRƯỚC Stage 3)
        cv_list_before_filter = len(cv_list)
        cv_list = [cv for cv in cv_list if cv.get("scope", {}).get("score", 0) > 0]
        
        if cv_list_before_filter > len(cv_list):
            logger.info(f"Đã lọc: {cv_list_before_filter} CVs → {len(cv_list)} CVs (loại {cv_list_before_filter - len(cv_list)} CVs có score = 0)")
        else:
            logger.info(f"Không có CV nào bị loại (tất cả {len(cv_list)} CVs đều có score > 0)")
        
        # Giới hạn số lượng CV theo yêu cầu (nếu có) - TRƯỚC Stage 3
        if requested_cv_count and requested_cv_count > 0:
            cv_list_before_limit = len(cv_list)
            cv_list = cv_list[:requested_cv_count]
            logger.info(f"Giới hạn kết quả: {cv_list_before_limit} CVs → {len(cv_list)} CVs (theo yêu cầu: top {requested_cv_count})")
        
        # STAGE 3: Advanced Features (DI CHUYỂN XUỐNG ĐÂY - SAU KHI ĐÃ LIMIT)
        # CHỈ generate cho CVs cuối cùng cần trả về
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
            
            # Check cache cho TỪNG CV riêng lẻ
            cv_ids = [cv.get('file_id') for cv in cv_list]
            cached_advanced = vector_db.get_cached_advanced_features(jd_hash, cv_ids, advanced_options)
            
            if cached_advanced:
                logger.info(f"📦 Cache HIT: Stage 3 advanced features for ALL {len(cv_list)} CVs")
                advanced_data = cached_advanced
            else:
                # Một số CVs đã có cache, một số chưa → Chỉ generate cho CVs chưa có cache
                logger.info(f"🔄 Cache PARTIAL/MISS: Checking individual CV cache...")
                
                # Check cache từng CV
                options_str = json.dumps(advanced_options, sort_keys=True)
                options_hash = hashlib.md5(options_str.encode()).hexdigest()
                
                cached_cvs = []
                uncached_cvs = []
                
                for cv_item in cv_list:
                    cv_id = cv_item.get('cv_id')
                    file_id = cv_item.get('file_id')
                    
                    # Check individual cache
                    collection = vector_db._get_or_create_collection(vector_db.ADVANCED_FEATURES_COLLECTION)
                    doc_id = f"advanced_{jd_hash[:16]}_{cv_id}_{options_hash[:8]}"
                    
                    result = collection.get(ids=[doc_id], include=["documents"])
                    
                    if result['ids'] and len(result['documents']) > 0:
                        cv_advanced = json.loads(result['documents'][0])
                        cached_cvs.append(cv_advanced)
                        logger.info(f"  📦 Cache HIT: {cv_item.get('candidate_name', 'Unknown')} (cv_id={cv_id})")
                    else:
                        # Tìm extracted_cv tương ứng
                        extracted_cv = next((cv for cv in extracted_cvs if cv.get('cv_id') == cv_id), None)
                        if extracted_cv:
                            uncached_cvs.append(extracted_cv)
                            logger.info(f"  🔄 Cache MISS: {cv_item.get('candidate_name', 'Unknown')} (cv_id={cv_id})")
                
                logger.info(f"Cache status: {len(cached_cvs)} hits, {len(uncached_cvs)} misses")
                
                # Nếu có CVs chưa cache, gọi OpenAI CHỈ cho các CVs đó
                newly_generated = []
                if len(uncached_cvs) > 0:
                    logger.info(f"🔄 Generating advanced features for {len(uncached_cvs)} uncached CVs...")
                    
                    # Generate prompt CHỈ cho uncached CVs
                    advanced_prompt = get_stage3_advanced_prompt(uncached_cvs, jd_text, requirements, advanced_options)
                    
                    if advanced_prompt:
                        # Call OpenAI
                        logger.info(f"Đang gọi OpenAI API ({OPENAI_MINI_MODEL}) cho {len(uncached_cvs)} CVs...")
                        stage3_response = call_openai_with_retry(
                            messages=[
                                {"role": "system", "content": "Bạn là chuyên gia tuyển dụng AI. Tạo advanced features cho CVs. Trả về CHÍNH XÁC JSON như yêu cầu."},
                                {"role": "user", "content": advanced_prompt}
                            ],
                            model=OPENAI_MINI_MODEL
                        )
                        
                        # Parse response
                        stage3_text = stage3_response.choices[0].message.content.strip()
                        
                        # DEBUG: Log GPT response for job_leveling
                        logger.info("=" * 80)
                        logger.info("🔍 STAGE 3 GPT RESPONSE DEBUG:")
                        logger.info(f"Response length: {len(stage3_text)} chars")
                        logger.info(f"First 500 chars: {stage3_text[:500]}")
                        logger.info(f"Contains 'job_leveling': {'job_leveling' in stage3_text}")
                        logger.info("=" * 80)
                        
                        # Extract JSON
                        if "```json" in stage3_text:
                            stage3_text = stage3_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in stage3_text:
                            stage3_text = stage3_text.split("```")[1].split("```")[0].strip()
                        
                        newly_generated = json.loads(stage3_text)
                        
                        # Track tokens
                        stage3_usage = stage3_response.usage
                        total_prompt_tokens += stage3_usage.prompt_tokens
                        total_completion_tokens += stage3_usage.completion_tokens
                        total_tokens += stage3_usage.total_tokens
                        
                        # Cache kết quả (từng CV riêng lẻ)
                        uncached_cv_ids = [cv.get('file_id') for cv in uncached_cvs]
                        vector_db.cache_advanced_features(jd_hash, uncached_cv_ids, advanced_options, newly_generated)
                        logger.info(f"✓ Cached Stage 3 advanced features for {len(newly_generated)} newly generated CVs")
                
                # Merge cached + newly generated
                advanced_data = cached_cvs + newly_generated
                logger.info(f"Total advanced data: {len(cached_cvs)} cached + {len(newly_generated)} new = {len(advanced_data)} CVs")
            
            # Merge advanced data vào cv_list
            advanced_dict = {item.get('cv_id'): item for item in advanced_data}
            for cv_item in cv_list:
                cv_id = cv_item.get('cv_id')
                if cv_id in advanced_dict:
                    advanced_item = advanced_dict[cv_id]
                    
                    # Merge các fields
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
            
            stage3_time = time.time() - stage3_start
            logger.info(f"⏱️  Stage 3 completed in {stage3_time:.2f}s")
            logger.info("=" * 80)
        
        # Filter/limit đã được di chuyển lên trước Stage 3
        
        total_time = time.time() - stage1_start
        
        # Tính cost ước tính
        # Stage 1A: gpt-4o ($2.50 input, $10.00 output per 1M tokens)
        # Stage 1B: gpt-4o-mini ($0.150 input, $0.600 output per 1M tokens)
        # Giả sử Stage 1A dùng ~10% tokens (1 call vs 6 calls)
        stage1a_tokens = stage1a_usage.prompt_tokens + stage1a_usage.completion_tokens
        stage1b_prompt = total_prompt_tokens - stage1a_usage.prompt_tokens
        stage1b_completion = total_completion_tokens - stage1a_usage.completion_tokens
        
        cost_1a_input = (stage1a_usage.prompt_tokens / 1_000_000) * 2.50
        cost_1a_output = (stage1a_usage.completion_tokens / 1_000_000) * 10.00
        cost_1b_input = (stage1b_prompt / 1_000_000) * 0.150
        cost_1b_output = (stage1b_completion / 1_000_000) * 0.600
        total_cost = cost_1a_input + cost_1a_output + cost_1b_input + cost_1b_output
        
        logger.info("=" * 80)
        logger.info(f"✅ THREE-STAGE HYBRID APPROACH COMPLETED in {total_time:.2f}s")
        logger.info(f"  📋 Database: {total_cvs} CVs total")
        
        # Chi tiết CVs không đọc được
        if unreadable_cvs:
            logger.info(f"  📄 Readable: {len(cv_data_list)} CVs (skipped {len(unreadable_cvs)} unreadable)")
            logger.info(f"     ⚠️  Unreadable: {', '.join(unreadable_cvs)}")
        else:
            logger.info(f"  📄 Readable: {len(cv_data_list)} CVs (all readable ✓)")
        
        logger.info(f"  🔍 Stage 1A (JD): {len(requirements.get('must_have_requirements', []))} must-haves, {len(requirements.get('nice_to_have_requirements', []))} nice-to-haves)")
        
        # Chi tiết CVs bị LLM bỏ sót
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
        
        # Trả về kết quả
        return {
            "status": "success",
            "message": f"Đã đối chiếu {len(cv_list)} CV phù hợp với JD",
            "received_data": received_data,
            "cv_mappings": cv_list,
            "total_cvs_processed": len(cv_data_list),
            "total_cvs_matched": len(cv_list)
        }
    
    except Exception as e:
        logger.error(f"Lỗi khi xử lý request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xử lý request: {str(e)}"
        )

