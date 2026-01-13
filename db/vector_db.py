"""Vector Database operations using ChromaDB for embedding cache"""
import chromadb
from chromadb.config import Settings
import hashlib
import time
import json
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from config import DATABASE_PATH
import logging

logger = logging.getLogger(__name__)

# ChromaDB client (persistent storage)
CHROMA_DB_PATH = Path(DATABASE_PATH).parent / "chroma_db"
CHROMA_DB_PATH.mkdir(exist_ok=True)

logger.info(f"🗄️  ChromaDB initialized at: {CHROMA_DB_PATH}")

client = chromadb.PersistentClient(
    path=str(CHROMA_DB_PATH),
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)

logger.info("✅ ChromaDB client connected successfully")

# Collections
CV_COLLECTION_NAME = "cv_embeddings"
JD_COLLECTION_NAME = "jd_embeddings"
JD_REQUIREMENTS_COLLECTION = "jd_requirements_data"  # Cache cho Stage 1A: JD requirements extraction
CV_EXTRACTED_DATA_COLLECTION = "cv_extracted_data"  # Cache cho extracted CV JSON
ADVANCED_FEATURES_COLLECTION = "advanced_features"  # Cache cho Stage 3 advanced features


def _get_or_create_collection(collection_name: str):
    """Lấy hoặc tạo collection"""
    try:
        collection = client.get_collection(name=collection_name)
        logger.info(f"Sử dụng collection: {collection_name}")
    except Exception:
        collection = client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Sử dụng cosine similarity
        )
        logger.info(f"Tạo mới collection: {collection_name}")
    return collection


def _generate_doc_id(content: str, prefix: str = "") -> str:
    """Generate unique ID từ content hash"""
    content_hash = hashlib.md5(content.encode()).hexdigest()
    return f"{prefix}_{content_hash}" if prefix else content_hash


def cache_cv_embedding(file_id: int, filename: str, content: str, embedding: List[float]) -> bool:
    """
    Cache embedding của CV vào ChromaDB
    
    Args:
        file_id: ID của file trong SQLite database (stored in metadata for reference)
        filename: Tên file CV
        content: Nội dung text của CV
        embedding: Embedding vector (1536 chiều)
        
    Returns:
        bool: True nếu cache thành công
    """
    try:
        collection = _get_or_create_collection(CV_COLLECTION_NAME)
        
        # Use ONLY content hash for doc_id (not file_id)
        # This enables duplicate detection across different file uploads
        doc_id = _generate_doc_id(content)
        
        # Upsert: Update nếu đã tồn tại, Insert nếu chưa có
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[{
                "file_id": file_id,  # Keep for reference but not part of doc_id
                "filename": filename,
                "content_length": len(content),
                "content_hash": hashlib.md5(content.encode()).hexdigest()
            }],
            documents=[content[:1000]]  # Lưu preview 1000 ký tự đầu
        )
        
        logger.info(f"✓ Cached CV embedding: {filename} (ID: {doc_id})")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi cache CV embedding: {e}")
        return False


def get_cached_cv_embedding(file_id: int, content: str) -> Optional[List[float]]:
    """
    Lấy cached embedding của CV từ ChromaDB
    
    Args:
        file_id: ID của file trong SQLite database (unused, kept for API compatibility)
        content: Nội dung text của CV (để verify hash)
        
    Returns:
        Optional[List[float]]: Embedding vector nếu có trong cache, None nếu không
    """
    try:
        collection = _get_or_create_collection(CV_COLLECTION_NAME)
        
        # Use ONLY content hash (not file_id) for lookup
        doc_id = _generate_doc_id(content)
        
        result = collection.get(
            ids=[doc_id],
            include=["embeddings", "metadatas"]
        )
        
        if result['ids'] and len(result['embeddings']) > 0:
            # Verify content hash để đảm bảo content không thay đổi
            cached_hash = result['metadatas'][0].get('content_hash')
            current_hash = hashlib.md5(content.encode()).hexdigest()
            
            if cached_hash == current_hash:
                logger.info(f"✓ Cache hit: CV content hash {doc_id[:8]}...")
                return result['embeddings'][0]
            else:
                logger.warning(f"Cache hash mismatch for CV {file_id}, will regenerate")
                return None
        
        logger.info(f"Cache miss: CV {file_id}")
        return None
        
    except Exception as e:
        logger.error(f"Lỗi khi lấy cached CV embedding: {e}")
        return None


def cache_jd_embedding(filename: str, content: str, embedding: List[float]) -> bool:
    """
    Cache embedding của JD vào ChromaDB
    
    Args:
        filename: Tên file JD
        content: Nội dung text của JD
        embedding: Embedding vector (1536 chiều)
        
    Returns:
        bool: True nếu cache thành công
    """
    try:
        collection = _get_or_create_collection(JD_COLLECTION_NAME)
        
        # Use pure content hash as doc_id (same content = same cache)
        doc_id = _generate_doc_id(content)
        
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[{
                "filename": filename,
                "content_length": len(content),
                "content_hash": hashlib.md5(content.encode()).hexdigest()
            }],
            documents=[content[:1000]]
        )
        
        logger.info(f"✓ Cached JD embedding: {filename} (ID: {doc_id})")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi cache JD embedding: {e}")
        return False


def get_cached_jd_embedding(content: str) -> Optional[List[float]]:
    """
    Lấy cached embedding của JD từ ChromaDB
    
    Strategy: Content-based cache - JD giống nhau 100% → Cache HIT
    
    Args:
        content: Nội dung text của JD
        
    Returns:
        Optional[List[float]]: Embedding vector nếu có trong cache, None nếu không
    """
    try:
        collection = _get_or_create_collection(JD_COLLECTION_NAME)
        
        # Use pure content hash for lookup
        doc_id = _generate_doc_id(content)
        
        result = collection.get(
            ids=[doc_id],
            include=["embeddings", "metadatas"]
        )
        
        if result['ids'] and len(result['embeddings']) > 0:
            logger.info(f"✓ Cache hit: JD content hash {doc_id[:8]}...")
            return result['embeddings'][0]
        
        logger.info(f"Cache miss: JD content hash {doc_id[:8]}...")
        return None
        
    except Exception as e:
        logger.error(f"Lỗi khi lấy cached JD embedding: {e}")
        return None


def search_similar_cvs(query_embedding: List[float], top_k: int = 50) -> List[Dict]:
    """
    Tìm kiếm CVs tương tự dựa vào embedding
    
    Args:
        query_embedding: Embedding vector của query (JD)
        top_k: Số lượng CVs muốn lấy
        
    Returns:
        List[Dict]: Danh sách CVs với similarity scores
    """
    try:
        collection = _get_or_create_collection(CV_COLLECTION_NAME)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas", "distances"]
        )
        
        similar_cvs = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i, doc_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i]
                
                # ChromaDB trả về distance (0=giống nhất), convert sang similarity (1=giống nhất)
                similarity = 1 - distance
                
                similar_cvs.append({
                    'file_id': metadata.get('file_id'),
                    'filename': metadata.get('filename'),
                    'similarity': similarity
                })
        
        logger.info(f"✓ Found {len(similar_cvs)} similar CVs")
        return similar_cvs
        
    except Exception as e:
        logger.error(f"Lỗi khi search similar CVs: {e}")
        return []


def get_collection_stats() -> Dict:
    """Lấy thống kê về collections"""
    try:
        cv_collection = _get_or_create_collection(CV_COLLECTION_NAME)
        jd_collection = _get_or_create_collection(JD_COLLECTION_NAME)
        
        return {
            "cv_embeddings_count": cv_collection.count(),
            "jd_embeddings_count": jd_collection.count(),
            "chroma_db_path": str(CHROMA_DB_PATH)
        }
    except Exception as e:
        logger.error(f"Lỗi khi lấy stats: {e}")
        return {}


def cache_extracted_cv_data(file_id: int, content: str, jd_hash: str, extracted_data: dict) -> bool:
    """
    Cache extracted CV data (JSON) để tránh gọi OpenAI extraction lại
    
    Args:
        file_id: ID của CV file (stored in metadata for reference)
        content: Nội dung text của CV (để tạo hash)
        jd_hash: Hash của JD (vì extracted data phụ thuộc vào JD requirements)
        extracted_data: JSON data đã extract từ OpenAI
        
    Returns:
        bool: True nếu cache thành công
    """
    try:
        collection = _get_or_create_collection(CV_EXTRACTED_DATA_COLLECTION)
        
        # ID = cv_content_hash + jd_hash (vì extraction phụ thuộc cả CV lẫn JD)
        # Remove file_id from doc_id to enable duplicate detection
        content_hash = hashlib.md5(content.encode()).hexdigest()
        doc_id = f"cv_{content_hash[:16]}_{jd_hash[:16]}"
        
        collection.upsert(
            ids=[doc_id],
            documents=[json.dumps(extracted_data)],  # Store as JSON string
            metadatas=[{
                "file_id": file_id,  # Keep for reference
                "content_hash": content_hash,
                "jd_hash": jd_hash,
                "extracted_at": hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
            }]
        )
        
        logger.info(f"✓ Cached extracted CV data: doc_id={doc_id}")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi cache extracted CV data: {e}")
        return False


def get_cached_extracted_cv_data(file_id: int, content: str, jd_hash: str) -> Optional[dict]:
    """
    Lấy cached extracted CV data
    
    Args:
        file_id: ID của CV file (unused, kept for API compatibility)
        content: Nội dung text của CV
        jd_hash: Hash của JD
        
    Returns:
        Optional[dict]: Extracted data nếu có trong cache, None nếu không
    """
    try:
        collection = _get_or_create_collection(CV_EXTRACTED_DATA_COLLECTION)
        
        content_hash = hashlib.md5(content.encode()).hexdigest()
        doc_id = f"cv_{content_hash[:16]}_{jd_hash[:16]}"
        
        result = collection.get(
            ids=[doc_id],
            include=["documents", "metadatas"]
        )
        
        if result['ids'] and len(result['documents']) > 0:
            # Verify content hash
            cached_content_hash = result['metadatas'][0].get('content_hash')
            if cached_content_hash == content_hash:
                try:
                    # Try JSON first (new format)
                    extracted_data = json.loads(result['documents'][0])
                except json.JSONDecodeError:
                    # Fallback to ast.literal_eval for old cache (Python str format)
                    try:
                        import ast
                        extracted_data = ast.literal_eval(result['documents'][0])
                        logger.warning(f"⚠️  Using legacy cache format (str), consider re-caching: {doc_id}")
                    except Exception as e:
                        logger.error(f"❌ Failed to parse cached data: {e}")
                        return None
                
                logger.info(f"✓ Cache HIT: Extracted CV data (doc_id={doc_id})")
                return extracted_data
            else:
                logger.warning(f"⚠️  Cache content hash mismatch: expected={content_hash[:8]}, cached={cached_content_hash[:8]}")
                return None
        
        logger.info(f"Cache MISS: doc_id={doc_id} not found")
        return None
        
    except Exception as e:
        logger.error(f"Lỗi khi lấy cached extracted CV data: {e}")
        return None


def cache_advanced_features(jd_hash: str, cv_ids: list, advanced_options: dict, advanced_data: list) -> bool:
    """
    Cache Stage 3 advanced features data - Cache TỪNG CV riêng lẻ
    
    Args:
        jd_hash: Hash của JD
        cv_ids: List các CV IDs (không dùng trong cache key nữa)
        advanced_options: Advanced options được enable
        advanced_data: Advanced features data (array of dicts)
        
    Returns:
        bool: True nếu cache thành công
    """
    try:
        collection = _get_or_create_collection(ADVANCED_FEATURES_COLLECTION)
        
        # Cache TỪNG CV riêng lẻ
        options_str = json.dumps(advanced_options, sort_keys=True)
        options_hash = hashlib.md5(options_str.encode()).hexdigest()
        
        cached_count = 0
        for cv_advanced in advanced_data:
            cv_id = cv_advanced.get('cv_id')
            if not cv_id:
                continue
            
            # Doc ID = jd_hash + cv_id + options_hash (KHÔNG phụ thuộc vào số lượng CVs)
            doc_id = f"advanced_{jd_hash[:16]}_{cv_id}_{options_hash[:8]}"
            
            collection.upsert(
                ids=[doc_id],
                documents=[json.dumps(cv_advanced)],
                metadatas=[{
                    "jd_hash": jd_hash,
                    "cv_id": cv_id,
                    "options_hash": options_hash,
                    "cached_at": hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
                }]
            )
            cached_count += 1
        
        logger.info(f"✓ Cached Stage 3 advanced features for {cached_count} CVs (individually)")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi cache advanced features: {e}")
        return False


def get_cached_advanced_features(jd_hash: str, cv_ids: list, advanced_options: dict) -> Optional[list]:
    """
    Lấy cached Stage 3 advanced features - Lấy TỪNG CV riêng lẻ
    
    Args:
        jd_hash: Hash của JD
        cv_ids: List các CV IDs cần lấy
        advanced_options: Advanced options được enable
        
    Returns:
        Optional[list]: Advanced features data nếu TẤT CẢ CVs đều có cache, None nếu thiếu bất kỳ CV nào
    """
    try:
        collection = _get_or_create_collection(ADVANCED_FEATURES_COLLECTION)
        
        options_str = json.dumps(advanced_options, sort_keys=True)
        options_hash = hashlib.md5(options_str.encode()).hexdigest()
        
        # Lấy cache từng CV
        cached_data = []
        missing_cvs = []
        
        for cv_id in cv_ids:
            doc_id = f"advanced_{jd_hash[:16]}_{cv_id}_{options_hash[:8]}"
            
            result = collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"]
            )
            
            if result['ids'] and len(result['documents']) > 0:
                cv_advanced = json.loads(result['documents'][0])
                cached_data.append(cv_advanced)
            else:
                missing_cvs.append(cv_id)
        
        # Chỉ trả về cache nếu TẤT CẢ CVs đều có cache
        if len(missing_cvs) == 0 and len(cached_data) == len(cv_ids):
            logger.info(f"✓ Cache HIT: Stage 3 advanced features for {len(cv_ids)}/{len(cv_ids)} CVs")
            return cached_data
        else:
            logger.info(f"Cache MISS: Stage 3 advanced features - {len(cached_data)}/{len(cv_ids)} CVs cached, missing {len(missing_cvs)} CVs")
            return None
        
    except Exception as e:
        logger.error(f"Lỗi khi lấy cached advanced features: {e}")
        return None


def cache_jd_requirements(jd_hash: str, requirements: dict) -> bool:
    """
    Cache JD requirements extraction result (Stage 1A)
    
    Args:
        jd_hash: MD5 hash của JD text
        requirements: Extracted requirements JSON
        
    Returns:
        bool: True nếu cache thành công
    """
    try:
        collection = _get_or_create_collection(JD_REQUIREMENTS_COLLECTION)
        
        # Use jd_hash as doc_id
        doc_id = jd_hash
        
        collection.upsert(
            ids=[doc_id],
            documents=[json.dumps(requirements, ensure_ascii=False)],
            metadatas=[{
                "jd_hash": jd_hash,
                "cached_at": time.time()
            }]
        )
        
        logger.info(f"✓ Cache JD requirements: {jd_hash[:16]}...")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi cache JD requirements: {e}")
        return False


def get_cached_jd_requirements(jd_hash: str) -> Optional[dict]:
    """
    Lấy cached JD requirements từ ChromaDB
    
    Args:
        jd_hash: MD5 hash của JD text
        
    Returns:
        dict hoặc None nếu không tìm thấy
    """
    try:
        collection = _get_or_create_collection(JD_REQUIREMENTS_COLLECTION)
        doc_id = jd_hash
        
        result = collection.get(
            ids=[doc_id],
            include=["documents"]
        )
        
        if result and result['documents'] and len(result['documents']) > 0:
            logger.info(f"✓ Cache HIT: JD requirements (hash: {jd_hash[:16]}...)")
            return json.loads(result['documents'][0])
        else:
            return None
            
    except Exception as e:
        logger.warning(f"Lỗi khi lấy cached JD requirements: {e}")
        return None


def clear_cache(collection_name: Optional[str] = None) -> Tuple[int, List[str]]:
    """
    Xóa cache
    
    Args:
        collection_name: Tên collection cần xóa. None = xóa tất cả
        
    Returns:
        Tuple[int, List[str]]: (số collections xóa thành công, list tên collections thất bại)
    """
    failed = []
    success_count = 0
    
    if collection_name:
        collections_to_delete = [collection_name]
    else:
        collections_to_delete = [
            CV_COLLECTION_NAME,
            JD_COLLECTION_NAME,
            JD_REQUIREMENTS_COLLECTION,
            CV_EXTRACTED_DATA_COLLECTION,
            ADVANCED_FEATURES_COLLECTION
        ]
    
    for coll_name in collections_to_delete:
        try:
            client.delete_collection(name=coll_name)
            logger.info(f"✓ Đã xóa collection: {coll_name}")
            success_count += 1
        except Exception as e:
            # Collection không tồn tại hoặc lỗi khác
            logger.warning(f"⚠️  Không thể xóa {coll_name}: {e}")
            failed.append(coll_name)
    
    return success_count, failed
