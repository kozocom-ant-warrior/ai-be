"""Script to clear all caches after doc_id format change"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import vector_db

def main():
    print("🗑️  Clearing ALL caches after doc_id format change...")
    print("=" * 80)
    print("BREAKING CHANGES:")
    print("  1. CV embedding: 'cv_{file_id}_{hash}' → '{hash}' (duplicate detection)")
    print("  2. CV extraction: 'cv_{file_id}_{cv_hash}_{jd_hash}' → 'cv_{cv_hash}_{jd_hash}'")
    print("  3. JD embedding: 'jd_{jd_id}_{hash}' → '{hash}' (already updated)")
    print("")
    print("Impact:")
    print("  ✅ Enables duplicate detection for identical CVs")
    print("  ✅ Fixes Stage 1B extraction cache (was 0% hit rate)")
    print("  ⚠️  All existing caches will be invalidated")
    print("=" * 80)
    
    # Confirm
    response = input("\n⚠️  Clear ALL caches (CV + JD + Extraction + Advanced)? (y/N): ")
    
    if response.lower() != 'y':
        print("❌ Cancelled")
        return
    
    # Clear all caches
    vector_db.clear_cache()  # Clear all collections
    
    print("\n✅ All caches cleared successfully!")
    print("\n📊 Next run will:")
    print("  • Generate embeddings for all CVs/JDs (one-time cost)")
    print("  • Cache with new format (content-based)")
    print("  • Enable duplicate detection")
    print("  • Fix Stage 1B extraction cache performance")

if __name__ == "__main__":
    main()
