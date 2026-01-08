#!/usr/bin/env python3
"""
Test ChromaDB Connection

Script đơn giản để test connection và xem data trong ChromaDB
"""

import chromadb
from pathlib import Path
import sys

# Path to ChromaDB (relative to project root)
CHROMA_DB_PATH = Path(__file__).parent.parent / "db" / "chroma_db"


def test_connection():
    """Test connection to ChromaDB"""
    print("=" * 80)
    print("🔌 Testing ChromaDB Connection")
    print("=" * 80)
    print()
    
    # Check if database exists
    if not CHROMA_DB_PATH.exists():
        print(f"❌ ChromaDB not found at: {CHROMA_DB_PATH}")
        print()
        print("💡 Chưa có cache. Để tạo cache:")
        print("   1. Upload CVs qua API: POST /cv/upload")
        print("   2. Chạy matching: POST /thinking")
        print()
        return False
    
    print(f"✅ ChromaDB found at: {CHROMA_DB_PATH}")
    print()
    
    try:
        # Connect to ChromaDB
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        print("✅ Connected to ChromaDB successfully")
        print()
        
        # List collections
        collections = client.list_collections()
        print(f"📂 Collections: {len(collections)}")
        print("-" * 80)
        
        if not collections:
            print("   (No collections yet)")
            print()
            print("💡 Collections sẽ được tạo tự động khi:")
            print("   - Upload CV lần đầu → 'cv_embeddings'")
            print("   - Upload JD lần đầu → 'jd_embeddings'")
            return True
        
        total_embeddings = 0
        for coll in collections:
            count = coll.count()
            total_embeddings += count
            print(f"  • {coll.name}")
            print(f"    - Total embeddings: {count:,}")
            
            # Get sample if exists
            if count > 0:
                sample = coll.get(limit=3, include=["metadatas", "documents"])
                print(f"    - Sample items:")
                for i, (doc_id, metadata) in enumerate(zip(sample['ids'], sample['metadatas']), 1):
                    filename = metadata.get('filename', 'N/A')
                    file_id = metadata.get('file_id', 'N/A')
                    print(f"      {i}. {filename} (file_id: {file_id})")
            print()
        
        print("-" * 80)
        print(f"📊 Total embeddings across all collections: {total_embeddings:,}")
        print()
        
        # Estimate cache savings
        if total_embeddings > 0:
            # Assuming $0.02 per 1M tokens, average 500 tokens per CV
            tokens_saved = total_embeddings * 500
            cost_saved = (tokens_saved / 1_000_000) * 0.02
            print(f"💰 Estimated API cost saved by cache: ${cost_saved:.4f}")
            print(f"   (Based on {total_embeddings} cached embeddings)")
        
        print()
        print("=" * 80)
        print("✅ ChromaDB is working correctly!")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to ChromaDB: {e}")
        import traceback
        traceback.print_exc()
        return False


def demo_query():
    """Demo: How to query ChromaDB"""
    print()
    print("=" * 80)
    print("📖 How to Query ChromaDB")
    print("=" * 80)
    print()
    
    print("Example 1: Get all CV embeddings")
    print("-" * 40)
    print("""
from vector_db import get_collection_stats

stats = get_collection_stats()
print(stats)
# Output: {'cv_embeddings_count': 10, 'jd_embeddings_count': 2, ...}
    """)
    
    print()
    print("Example 2: Check if CV has cached embedding")
    print("-" * 40)
    print("""
from vector_db import get_cached_cv_embedding

cv_id = 123
cv_content = "Resume of John Doe..."

embedding = get_cached_cv_embedding(cv_id, cv_content)
if embedding:
    print("✅ Cache hit! Using cached embedding")
else:
    print("❌ Cache miss, need to generate new embedding")
    """)
    
    print()
    print("Example 3: Manually add to cache")
    print("-" * 40)
    print("""
from vector_db import cache_cv_embedding

# After generating embedding from OpenAI
embedding = [0.1, 0.2, ..., 0.9]  # 1536-dim vector

cache_cv_embedding(
    file_id=123,
    filename="john_doe.pdf",
    content="Resume content...",
    embedding=embedding
)
    """)
    
    print()
    print("Example 4: Search similar CVs (Advanced)")
    print("-" * 40)
    print("""
from vector_db import search_similar_cvs

# You need a query embedding (e.g., from JD)
jd_embedding = get_embedding("Python Developer JD...")

# Find top 10 similar CVs
similar_cvs = search_similar_cvs(jd_embedding, top_k=10)

for cv in similar_cvs:
    print(f"{cv['filename']}: {cv['similarity']:.2%}")
    """)
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    try:
        success = test_connection()
        
        if success:
            demo_query()
            print()
            print("💡 Next steps:")
            print("   1. View details: python chroma_inspector.py --stats")
            print("   2. Export data: python chroma_inspector.py --export data.json --collection cv_embeddings")
            print("   3. Clear cache: python chroma_inspector.py --clear cv_embeddings")
            print()
    
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
