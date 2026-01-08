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
        file_id: ID của file trong SQLite database
        filename: Tên file CV
        content: Nội dung text của CV
        embedding: Embedding vector (1536 chiều)
        
    Returns:
        bool: True nếu cache thành công
    """
    try:
        collection = _get_or_create_collection(CV_COLLECTION_NAME)
        
        doc_id = _generate_doc_id(content, f"cv_{file_id}")
        
        # Upsert: Update nếu đã tồn tại, Insert nếu chưa có
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[{
                "file_id": file_id,
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
        file_id: ID của file trong SQLite database
        content: Nội dung text của CV (để verify hash)
        
    Returns:
        Optional[List[float]]: Embedding vector nếu có trong cache, None nếu không
    """
    try:
        collection = _get_or_create_collection(CV_COLLECTION_NAME)
        
        doc_id = _generate_doc_id(content, f"cv_{file_id}")
        
        result = collection.get(
            ids=[doc_id],
            include=["embeddings", "metadatas"]
        )
        
        if result['ids'] and len(result['embeddings']) > 0:
            # Verify content hash để đảm bảo content không thay đổi
            cached_hash = result['metadatas'][0].get('content_hash')
            current_hash = hashlib.md5(content.encode()).hexdigest()
            
            if cached_hash == current_hash:
                logger.info(f"✓ Cache hit: CV {file_id}")
                return result['embeddings'][0]
            else:
                logger.warning(f"Cache hash mismatch for CV {file_id}, will regenerate")
                return None
        
        logger.info(f"Cache miss: CV {file_id}")
        return None
        
    except Exception as e:
        logger.error(f"Lỗi khi lấy cached CV embedding: {e}")
        return None


def cache_jd_embedding(jd_id: int, filename: str, content: str, embedding: List[float]) -> bool:
    """
    Cache embedding của JD vào ChromaDB
    
    Args:
        jd_id: ID của JD trong SQLite database
        filename: Tên file JD
        content: Nội dung text của JD
        embedding: Embedding vector (1536 chiều)
        
    Returns:
        bool: True nếu cache thành công
    """
    try:
        collection = _get_or_create_collection(JD_COLLECTION_NAME)
        
        doc_id = _generate_doc_id(content, f"jd_{jd_id}")
        
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[{
                "jd_id": jd_id,
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


def get_cached_jd_embedding(jd_id: int, content: str, similarity_threshold: float = 0.95) -> Optional[List[float]]:
    """
    Lấy cached embedding của JD từ ChromaDB với fuzzy matching
    
    Strategy: Nếu JD mới ~95% giống JD cũ → Dùng lại cache (tiết kiệm API cost)
    
    Args:
        jd_id: ID của JD trong SQLite database
        content: Nội dung text của JD
        similarity_threshold: Ngưỡng similarity để dùng lại cache (0.95 = 95% giống)
        
    Returns:
        Optional[List[float]]: Embedding vector nếu có trong cache, None nếu không
    """
    try:
        collection = _get_or_create_collection(JD_COLLECTION_NAME)
        
        # Strategy 1: Exact match (MD5 hash)
        doc_id = _generate_doc_id(content, f"jd_{jd_id}")
        
        result = collection.get(
            ids=[doc_id],
            include=["embeddings", "metadatas"]
        )
        
        if result['ids'] and len(result['embeddings']) > 0:
            # doc_id already includes content hash, so if found, it's guaranteed to match
            logger.info(f"✓ Cache hit (exact): JD {jd_id}")
            return result['embeddings'][0]
        
        # Strategy 2: Fuzzy match - Tìm JD tương tự bằng text similarity
        # Dùng simple character-based similarity (không cần embedding)
        # Chỉ check JDs của cùng jd_id (version khác nhau của cùng 1 JD)
        all_jd_results = collection.get(
            where={"jd_id": jd_id},  # Chỉ check các version của cùng JD
            include=["embeddings", "metadatas", "documents"]
        )
        
        if all_jd_results['ids'] and len(all_jd_results['ids']) > 0:
            current_content_lower = content.lower().strip()
            
            for i, cached_doc_id in enumerate(all_jd_results['ids']):
                cached_content = all_jd_results['documents'][i]
                cached_content_lower = cached_content.lower().strip()
                
                # Tính text similarity đơn giản (Jaccard similarity)
                current_words = set(current_content_lower.split())
                cached_words = set(cached_content_lower.split())
                
                if len(current_words) == 0 or len(cached_words) == 0:
                    continue
                
                intersection = current_words.intersection(cached_words)
                union = current_words.union(cached_words)
                text_similarity = len(intersection) / len(union) if len(union) > 0 else 0
                
                # Nếu >= threshold, dùng lại cached embedding
                if text_similarity >= similarity_threshold:
                    logger.info(f"✓ Cache hit (fuzzy {text_similarity:.1%}): JD {jd_id} - Reusing similar JD embedding")
                    return all_jd_results['embeddings'][i]
        
        logger.info(f"Cache miss: JD {jd_id} (no exact or similar match)")
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
        file_id: ID của CV file
        content: Nội dung text của CV (để tạo hash)
        jd_hash: Hash của JD (vì extracted data phụ thuộc vào JD requirements)
        extracted_data: JSON data đã extract từ OpenAI
        
    Returns:
        bool: True nếu cache thành công
    """
    try:
        collection = _get_or_create_collection(CV_EXTRACTED_DATA_COLLECTION)
        
        # ID = cv_content_hash + jd_hash (vì extraction phụ thuộc cả CV lẫn JD)
        content_hash = hashlib.md5(content.encode()).hexdigest()
        doc_id = f"cv_{file_id}_{content_hash[:8]}_{jd_hash[:8]}"
        
        collection.upsert(
            ids=[doc_id],
            documents=[str(extracted_data)],  # Store as string
            metadatas=[{
                "file_id": file_id,
                "content_hash": content_hash,
                "jd_hash": jd_hash,
                "extracted_at": hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
            }]
        )
        
        logger.debug(f"✓ Cached extracted CV data: file_id={file_id}")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi cache extracted CV data: {e}")
        return False


def get_cached_extracted_cv_data(file_id: int, content: str, jd_hash: str) -> Optional[dict]:
    """
    Lấy cached extracted CV data
    
    Args:
        file_id: ID của CV file
        content: Nội dung text của CV
        jd_hash: Hash của JD
        
    Returns:
        Optional[dict]: Extracted data nếu có trong cache, None nếu không
    """
    try:
        collection = _get_or_create_collection(CV_EXTRACTED_DATA_COLLECTION)
        
        content_hash = hashlib.md5(content.encode()).hexdigest()
        doc_id = f"cv_{file_id}_{content_hash[:8]}_{jd_hash[:8]}"
        
        result = collection.get(
            ids=[doc_id],
            include=["documents", "metadatas"]
        )
        
        if result['ids'] and len(result['documents']) > 0:
            # Verify content hash
            cached_content_hash = result['metadatas'][0].get('content_hash')
            if cached_content_hash == content_hash:
                import ast
                extracted_data = ast.literal_eval(result['documents'][0])
                logger.debug(f"✓ Cache hit: Extracted CV data for file_id={file_id}")
                return extracted_data
            else:
                logger.warning(f"Cache content hash mismatch for CV {file_id}")
                return None
        
        return None
        
    except Exception as e:
        logger.error(f"Lỗi khi lấy cached extracted CV data: {e}")
        return None


def cache_advanced_features(jd_hash: str, cv_ids: list, advanced_options: dict, advanced_data: list) -> bool:
    """
    Cache Stage 3 advanced features data
    
    Args:
        jd_hash: Hash của JD
        cv_ids: List các CV IDs
        advanced_options: Advanced options được enable
        advanced_data: Advanced features data (array of dicts)
        
    Returns:
        bool: True nếu cache thành công
    """
    try:
        collection = _get_or_create_collection(ADVANCED_FEATURES_COLLECTION)
        
        # Create unique ID based on JD + CV IDs + options
        cv_ids_str = "_".join(sorted([str(id) for id in cv_ids]))
        cv_ids_hash = hashlib.md5(cv_ids_str.encode()).hexdigest()
        options_str = json.dumps(advanced_options, sort_keys=True)
        options_hash = hashlib.md5(options_str.encode()).hexdigest()
        
        doc_id = f"advanced_{jd_hash[:8]}_{cv_ids_hash[:8]}_{options_hash[:8]}"
        
        collection.upsert(
            ids=[doc_id],
            documents=[json.dumps(advanced_data)],
            metadatas=[{
                "jd_hash": jd_hash,
                "cv_count": len(cv_ids),
                "options_hash": options_hash,
                "cached_at": hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
            }]
        )
        
        logger.info(f"✓ Cached Stage 3 advanced features for {len(cv_ids)} CVs")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi cache advanced features: {e}")
        return False


def get_cached_advanced_features(jd_hash: str, cv_ids: list, advanced_options: dict) -> Optional[list]:
    """
    Lấy cached Stage 3 advanced features
    
    Args:
        jd_hash: Hash của JD
        cv_ids: List các CV IDs
        advanced_options: Advanced options được enable
        
    Returns:
        Optional[list]: Advanced features data nếu có trong cache, None nếu không
    """
    try:
        collection = _get_or_create_collection(ADVANCED_FEATURES_COLLECTION)
        
        cv_ids_str = "_".join(sorted([str(id) for id in cv_ids]))
        cv_ids_hash = hashlib.md5(cv_ids_str.encode()).hexdigest()
        options_str = json.dumps(advanced_options, sort_keys=True)
        options_hash = hashlib.md5(options_str.encode()).hexdigest()
        
        doc_id = f"advanced_{jd_hash[:8]}_{cv_ids_hash[:8]}_{options_hash[:8]}"
        
        result = collection.get(
            ids=[doc_id],
            include=["documents", "metadatas"]
        )
        
        if result['ids'] and len(result['documents']) > 0:
            advanced_data = json.loads(result['documents'][0])
            logger.info(f"✓ Cache hit: Stage 3 advanced features for {len(cv_ids)} CVs")
            return advanced_data
        
        logger.info(f"Cache miss: Stage 3 advanced features")
        return None
        
    except Exception as e:
        logger.error(f"Lỗi khi lấy cached advanced features: {e}")
        return None


def clear_cache(collection_name: Optional[str] = None):
    """
    Xóa cache
    
    Args:
        collection_name: Tên collection cần xóa. None = xóa tất cả
    """
    try:
        if collection_name:
            client.delete_collection(name=collection_name)
            logger.info(f"✓ Đã xóa collection: {collection_name}")
        else:
            client.delete_collection(name=CV_COLLECTION_NAME)
            client.delete_collection(name=JD_COLLECTION_NAME)
            client.delete_collection(name=CV_EXTRACTED_DATA_COLLECTION)
            client.delete_collection(name=ADVANCED_FEATURES_COLLECTION)
            logger.info("✓ Đã xóa tất cả cache")
    except Exception as e:
        logger.warning(f"Lỗi khi xóa cache: {e}")
