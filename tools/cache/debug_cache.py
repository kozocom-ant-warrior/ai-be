#!/usr/bin/env python3
"""Debug cache issue - check why cache miss"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from db import vector_db
from db.database import get_all_files
import hashlib

def main():
    print("=" * 80)
    print("🔍 DEBUG CACHE ISSUE")
    print("=" * 80)
    
    # Get first CV from database
    cv_files, total = get_all_files(limit=5, offset=0, file_type="cv")
    
    if total == 0:
        print("❌ No CVs in database")
        return
    
    print(f"📄 Found {total} CVs in database")
    print()
    
    # Test JD hash - DÙNG JD THỰC TẾ ĐÃ CACHE
    # Lấy từ cached entry
    collection = vector_db._get_or_create_collection(vector_db.CV_EXTRACTED_DATA_COLLECTION)
    sample = collection.get(limit=1, include=["metadatas"])
    
    if not sample['ids']:
        print("❌ No cached entries to test")
        return
    
    jd_hash = sample['metadatas'][0].get('jd_hash')
    print(f"🔑 Using cached JD hash: {jd_hash}")
    print()
    
    # Check cache cho từng CV
    for idx, cv_file in enumerate(cv_files[:5], 1):
        file_id = cv_file['id']
        filename = cv_file.get('original_filename', 'unknown')
        content = cv_file.get('content', '')
        
        if not content:
            print(f"{idx}. ❌ {filename}: No content in database")
            continue
        
        # Calculate hashes
        content_hash = hashlib.md5(content.encode()).hexdigest()
        doc_id = f"cv_{content_hash[:16]}_{jd_hash[:16]}"
        
        print(f"{idx}. {filename}")
        print(f"   file_id: {file_id}")
        print(f"   content_hash: {content_hash[:16]}...")
        print(f"   doc_id: {doc_id}")
        
        # Check cache
        cached = vector_db.get_cached_extracted_cv_data(file_id, content, jd_hash)
        
        if cached:
            print(f"   ✅ Cache HIT")
        else:
            print(f"   ❌ Cache MISS")
        print()
    
    # List all cached doc IDs
    print("=" * 80)
    print("📦 CACHED ENTRIES IN cv_extracted_data")
    print("=" * 80)
    
    collection = vector_db._get_or_create_collection(vector_db.CV_EXTRACTED_DATA_COLLECTION)
    all_data = collection.get(include=["metadatas"])
    
    if not all_data['ids']:
        print("❌ No cached entries")
        return
    
    print(f"Total cached: {len(all_data['ids'])}")
    print()
    
    for i, (doc_id, metadata) in enumerate(zip(all_data['ids'], all_data['metadatas']), 1):
        print(f"{i}. {doc_id}")
        print(f"   jd_hash: {metadata.get('jd_hash')}")
        print(f"   content_hash: {metadata.get('content_hash', 'N/A')[:16]}...")
        print(f"   file_id: {metadata.get('file_id')}")
        print()
        
        if i >= 10:  # Limit to first 10
            print(f"... and {len(all_data['ids']) - 10} more")
            break
    
    print("=" * 80)


if __name__ == "__main__":
    main()
