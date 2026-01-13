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
CV_EXTRACTED_DATA_COLLECTION = "cv_extracted_data"  # Cache for extracted CV JSON
ADVANCED_FEATURES_COLLECTION = "advanced_features"  # Cache for Stage 3 advanced features
JD_REQUIREMENTS_COLLECTION = "jd_requirements_data"  # Cache for Stage 1A JD requirements


def _get_or_create_collection(collection_name: str):
    """Get or create collection"""
    try:
        collection = client.get_collection(name=collection_name)
        logger.info(f"Using collection: {collection_name}")
    except Exception:
        collection = client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
        logger.info(f"Created new collection: {collection_name}")
    return collection


def _generate_doc_id(content: str, prefix: str = "") -> str:
    """Generate unique ID from content hash"""
    content_hash = hashlib.md5(content.encode()).hexdigest()
    return f"{prefix}_{content_hash}" if prefix else content_hash


def cache_cv_embedding(file_id: int, filename: str, content: str, embedding: List[float]) -> bool:
    """
    Cache CV embedding to ChromaDB
    
    Args:
        file_id: ID of file in SQLite database
        filename: CV filename
        content: CV text content
        embedding: Embedding vector (1536 dimensions)
        
    Returns:
        bool: True if cached successfully
    """
    try:
        collection = _get_or_create_collection(CV_COLLECTION_NAME)
        
        doc_id = _generate_doc_id(content, f"cv_{file_id}")
        
        # Upsert: Update if exists, Insert if new
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[{
                "file_id": file_id,
                "filename": filename,
                "content_length": len(content),
                "content_hash": hashlib.md5(content.encode()).hexdigest()
            }],
            documents=[content[:1000]]  # Store first 1000 chars preview
        )
        
        logger.info(f"✓ Cached CV embedding: {filename} (ID: {doc_id})")
        return True
        
    except Exception as e:
        logger.error(f"Error caching CV embedding: {e}")
        return False


def get_cached_cv_embedding(file_id: int, content: str) -> Optional[List[float]]:
    """
    Get cached CV embedding from ChromaDB
    
    Args:
        file_id: ID of file in SQLite database
        content: CV text content (to verify hash)
        
    Returns:
        Optional[List[float]]: Embedding vector if cached, None otherwise
    """
    try:
        collection = _get_or_create_collection(CV_COLLECTION_NAME)
        
        doc_id = _generate_doc_id(content, f"cv_{file_id}")
        
        result = collection.get(
            ids=[doc_id],
            include=["embeddings", "metadatas"]
        )
        
        if result['ids'] and len(result['embeddings']) > 0:
            # Verify content hash to ensure content hasn't changed
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
        logger.error(f"Error getting cached CV embedding: {e}")
        return None


def cache_jd_embedding(filename: str, content: str, embedding: List[float]) -> bool:
    """
    Cache JD embedding to ChromaDB
    
    Args:
        filename: JD filename
        content: JD text content
        embedding: Embedding vector (1536 dimensions)
        
    Returns:
        bool: True if cached successfully
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
        logger.error(f"Error caching JD embedding: {e}")
        return False


def get_cached_jd_embedding(content: str) -> Optional[List[float]]:
    """
    Get cached JD embedding from ChromaDB
    
    Strategy: Content-based cache - identical JD 100% → Cache HIT
    
    Args:
        content: JD text content
        
    Returns:
        Optional[List[float]]: Embedding vector if cached, None otherwise
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
        logger.error(f"Error getting cached JD embedding: {e}")
        return None


def search_similar_cvs(query_embedding: List[float], top_k: int = 50) -> List[Dict]:
    """
    Search for similar CVs based on embedding
    
    Args:
        query_embedding: Embedding vector of query (JD)
        top_k: Number of CVs to retrieve
        
    Returns:
        List[Dict]: List of CVs with similarity scores
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
                
                # ChromaDB returns distance (0=most similar), convert to similarity (1=most similar)
                similarity = 1 - distance
                
                similar_cvs.append({
                    'file_id': metadata.get('file_id'),
                    'filename': metadata.get('filename'),
                    'similarity': similarity
                })
        
        logger.info(f"✓ Found {len(similar_cvs)} similar CVs")
        return similar_cvs
        
    except Exception as e:
        logger.error(f"Error searching similar CVs: {e}")
        return []


def get_collection_stats() -> Dict:
    """Get statistics about collections"""
    try:
        cv_collection = _get_or_create_collection(CV_COLLECTION_NAME)
        jd_collection = _get_or_create_collection(JD_COLLECTION_NAME)
        
        return {
            "cv_embeddings_count": cv_collection.count(),
            "jd_embeddings_count": jd_collection.count(),
            "chroma_db_path": str(CHROMA_DB_PATH)
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {}


def cache_extracted_cv_data(file_id: int, content: str, jd_hash: str, extracted_data: dict) -> bool:
    """
    Cache extracted CV data (JSON) to avoid calling OpenAI extraction again
    
    Args:
        file_id: CV file ID
        content: CV text content (to create hash)
        jd_hash: JD hash (since extracted data depends on JD requirements)
        extracted_data: JSON data extracted from OpenAI
        
    Returns:
        bool: True if cached successfully
    """
    try:
        collection = _get_or_create_collection(CV_EXTRACTED_DATA_COLLECTION)
        
        # ID = cv_content_hash + jd_hash (since extraction depends on both CV and JD)
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
        logger.error(f"Error caching extracted CV data: {e}")
        return False


def get_cached_extracted_cv_data(file_id: int, content: str, jd_hash: str) -> Optional[dict]:
    """
    Get cached extracted CV data
    
    Args:
        file_id: CV file ID
        content: CV text content
        jd_hash: JD hash
        
    Returns:
        Optional[dict]: Extracted data if cached, None otherwise
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
        logger.error(f"Error getting cached extracted CV data: {e}")
        return None


def cache_jd_requirements(jd_hash: str, requirements: dict) -> bool:
    """
    Cache Stage 1A JD requirements extraction
    
    Args:
        jd_hash: JD text hash
        requirements: Requirements data extracted from JD
        
    Returns:
        bool: True if cached successfully
    """
    try:
        collection = _get_or_create_collection(JD_REQUIREMENTS_COLLECTION)
        
        doc_id = f"jd_req_{jd_hash[:16]}"
        
        collection.upsert(
            ids=[doc_id],
            documents=[json.dumps(requirements)],
            metadatas=[{
                "jd_hash": jd_hash,
                "cached_at": time.time()
            }]
        )
        
        logger.info(f"✓ Cached JD requirements: {doc_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error caching JD requirements: {e}")
        return False


def get_cached_jd_requirements(jd_hash: str) -> Optional[dict]:
    """
    Get cached JD requirements
    
    Args:
        jd_hash: JD text hash
        
    Returns:
        Optional[dict]: Requirements data if cached, None otherwise
    """
    try:
        collection = _get_or_create_collection(JD_REQUIREMENTS_COLLECTION)
        
        doc_id = f"jd_req_{jd_hash[:16]}"
        
        result = collection.get(
            ids=[doc_id],
            include=["documents", "metadatas"]
        )
        
        if result['ids'] and len(result['documents']) > 0:
            requirements = json.loads(result['documents'][0])
            logger.debug(f"✓ Cache HIT: JD requirements (hash: {jd_hash[:16]}...)")
            return requirements
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting cached JD requirements: {e}")
        return None


def cache_advanced_features(jd_hash: str, cv_ids: list, advanced_options: dict, advanced_data: list) -> bool:
    """
    Cache Stage 3 advanced features data
    
    Args:
        jd_hash: JD hash
        cv_ids: List of CV IDs
        advanced_options: Advanced options enabled
        advanced_data: Advanced features data (array of dicts)
        
    Returns:
        bool: True if cached successfully
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
        logger.error(f"Error caching advanced features: {e}")
        return False


def get_cached_advanced_features(jd_hash: str, cv_ids: list, advanced_options: dict) -> Optional[list]:
    """
    Get cached Stage 3 advanced features
    
    Args:
        jd_hash: JD hash
        cv_ids: List of CV IDs
        advanced_options: Advanced options enabled
        
    Returns:
        Optional[list]: Advanced features data if cached, None otherwise
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
            logger.info(f"✓ Cache HIT: Stage 3 advanced features for {len(cv_ids)} CVs (key: {doc_id})")
            return advanced_data
        
        logger.info(f"❌ Cache MISS: Stage 3 (key: {doc_id})")
        return None
        
    except Exception as e:
        logger.error(f"Error getting cached advanced features: {e}")
        return None


def clear_cache(collection_name: Optional[str] = None):
    """
    Clear cache
    
    Args:
        collection_name: Collection name to clear. None = clear all
        
    Returns:
        tuple: (success_count, failed_collections)
    """
    failed = []
    success_count = 0
    
    try:
        if collection_name:
            try:
                client.delete_collection(name=collection_name)
                logger.info(f"✓ Deleted collection: {collection_name}")
                success_count = 1
            except Exception as e:
                logger.warning(f"Error deleting collection {collection_name}: {e}")
                failed.append(collection_name)
        else:
            # Clear all collections
            all_collections = [
                CV_COLLECTION_NAME,
                JD_COLLECTION_NAME, 
                CV_EXTRACTED_DATA_COLLECTION,
                ADVANCED_FEATURES_COLLECTION,
                JD_REQUIREMENTS_COLLECTION
            ]
            
            for coll_name in all_collections:
                try:
                    client.delete_collection(name=coll_name)
                    logger.info(f"✓ Deleted collection: {coll_name}")
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Error deleting collection {coll_name}: {e}")
                    failed.append(coll_name)
            
            if success_count > 0:
                logger.info(f"✓ Deleted {success_count} collection(s)")
                
        return success_count, failed
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return 0, failed
