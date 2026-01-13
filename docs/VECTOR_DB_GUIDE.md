# Vector Database Cache Guide

## 🎯 Purpose

Optimize **cost** and **speed** when matching CV with JD by caching embeddings in ChromaDB.

## 💰 Cost Savings

### Before cache:
```
100 CVs × 1 JD matching = 100 API calls per match
Cost: ~$0.02/1M tokens × 100 docs × N times matching
```

### After cache:
```
1st time: 100 API calls (create cache)
2nd time+: 0 API calls (use cache) ✅
Cost: Only costs money first time, then FREE
```

## 📊 Cache Optimization Flow

### Current Flow (NO cache):
```
User Request
    ↓
Extract JD text → API call to create JD embedding 💰
    ↓
Extract 100 CV texts → 100 API calls to create embeddings 💰💰💰
    ↓
Calculate cosine similarity
    ↓
Return top 50 CVs
```

### NEW Flow (WITH cache):
```
User Request
    ↓
Extract JD text → API call to create JD embedding 💰
    ↓
Extract 100 CV texts
    ↓
    ├─ CV1: Check cache → FOUND ✅ (FREE)
    ├─ CV2: Check cache → FOUND ✅ (FREE)
    ├─ CV3: Check cache → NOT FOUND → API call 💰 → Save to cache
    ├─ CV4: Check cache → FOUND ✅ (FREE)
    └─ ... (95% cache hit rate = 95% FREE!)
    ↓
Calculate cosine similarity
    ↓
Return top 50 CVs
```

## 🔧 Implementation Details

### 1. At which step to cache?

**Step 1: Cache CV Embeddings** (most important)
- **When**: Right after creating embedding for CV first time
- **Why**: CVs don't change often, reused many times
- **Benefit**: Save 90-95% API calls

**Step 2: Cache JD Embeddings** (optional)
- **When**: If JD used multiple times (same job position)
- **Why**: JD can be reused for many CV batches
- **Benefit**: Save a few more API calls

### 2. How to Connect with database.py

**Architecture:**
```
SQLite (database.py)          ChromaDB (vector_db.py)
├─ files table               ├─ cv_embeddings collection
│  ├─ id (primary key)       │  ├─ doc_id: cv_{file_id}_{hash}
│  ├─ filename               │  ├─ embedding: [1536 floats]
│  ├─ content                │  └─ metadata: {file_id, filename, hash}
│  └─ file_type             
└─ Metadata storage          └─ jd_embeddings collection
                                ├─ doc_id: {content_hash}
                                ├─ embedding: [1536 floats]
                                └─ metadata: {filename, content_length, hash}
```

**Combined Workflow:**
```python
# 1. Get CVs from SQLite
cvs = get_all_files(file_type='cv')  # database.py

# 2. For each CV, check cache
for cv in cvs:
    # Try to get from ChromaDB first
    embedding = vector_db.get_cached_cv_embedding(cv['id'], cv['content'])
    
    if not embedding:
        # Cache miss → Call OpenAI API
        embedding = get_embedding(cv['content'])
        # Save to cache
        vector_db.cache_cv_embedding(cv['id'], cv['filename'], cv['content'], embedding)
```

## 📝 Usage Examples

### Example 1: Upload CV and auto-cache embedding
```python
from vector_db import cache_cv_embedding
from database import save_file_to_database

# Upload CV
file_id = save_file_to_database(...)

# Extract text
cv_text = extract_text_from_file(file_path)

# Create embedding
embedding = get_embedding(cv_text)

# Cache immediately
cache_cv_embedding(file_id, filename, cv_text, embedding)
```

### Example 2: Matching with cache
```python
# 1st time: Cache miss → Call API
embedding1 = get_embedding(cv_text, cache_id=1, cache_type='cv')
# 📊 Cache stats: 0 hits, 1 misses

# 2nd time: Cache hit → FREE
embedding2 = get_embedding(cv_text, cache_id=1, cache_type='cv')
# 📊 Cache stats: 1 hits, 0 misses (100% hit rate!)
```

### Example 3: Check cache stats
```python
from vector_db import get_collection_stats

stats = get_collection_stats()
print(stats)
# {
#   'cv_embeddings_count': 150,
#   'jd_embeddings_count': 10,
#   'chroma_db_path': '/path/to/chroma_db'
# }
```

### Example 4: Clear cache (when needed)
```python
from vector_db import clear_cache

# Clear cache CVs
clear_cache('cv_embeddings')

# Clear all
clear_cache()
```

## 🚀 Installation

```bash
# Install ChromaDB
pip install chromadb>=0.4.0

# or
pip install -r requirements.txt
```

## ⚙️ Configuration

ChromaDB will automatically create folder `chroma_db/` next to file `data.db`:
```
ai-be/
├── data.db              ← SQLite (metadata)
├── chroma_db/           ← ChromaDB (embeddings cache)
│   ├── cv_embeddings/
│   └── jd_embeddings/
└── cvs/
```

## 🔍 Verification

To verify cache is working:
```python
# View logs
# 1st time: 🔄 Generating new embedding via OpenAI API...
# 2nd time: 📦 Using cached embedding for cv 123
```

## ⚠️ Important Notes

1. **Cache invalidation**: If CV content changes, cache automatically invalidates (using MD5 hash)
2. **Storage**: ChromaDB saves persistently, not lost after restart
3. **Performance**: Cache hit = ~instant (< 1ms), API call = ~500-1000ms
4. **Cost**: 1000 CVs × 1 matching with 95% cache hit = only costs 50 API calls instead of 1000!

## 📈 Expected Results

**Before cache:**
- 100 CVs matching: ~30-60 seconds
- Cost per matching: ~$0.20

**After cache (95% hit rate):**
- 100 CVs matching: ~5-10 seconds ⚡
- Cost per matching: ~$0.01 💰

**ROI = 6x faster, 20x cheaper!**
