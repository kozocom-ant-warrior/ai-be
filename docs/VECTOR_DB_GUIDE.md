# Vector Database Cache Guide

## 🎯 Mục đích

Tối ưu hóa **chi phí** và **tốc độ** khi matching CV với JD bằng cách cache embeddings trong ChromaDB.

## 💰 Tiết kiệm chi phí

### Trước khi có cache:
```
100 CVs × 1 JD matching = 100 API calls mỗi lần
Chi phí: ~$0.02/1M tokens × 100 docs × N lần matching
```

### Sau khi có cache:
```
Lần 1: 100 API calls (tạo cache)
Lần 2+: 0 API calls (dùng cache) ✅
Chi phí: Chỉ tốn tiền lần đầu, sau đó FREE
```

## 📊 Cache Optimization Flow

### Flow hiện tại (KHÔNG cache):
```
User Request
    ↓
Extract JD text → API call tạo JD embedding 💰
    ↓
Extract 100 CV texts → 100 API calls tạo embeddings 💰💰💰
    ↓
Tính cosine similarity
    ↓
Return top 50 CVs
```

### Flow MỚI (CÓ cache):
```
User Request
    ↓
Extract JD text → API call tạo JD embedding 💰
    ↓
Extract 100 CV texts
    ↓
    ├─ CV1: Check cache → FOUND ✅ (FREE)
    ├─ CV2: Check cache → FOUND ✅ (FREE)
    ├─ CV3: Check cache → NOT FOUND → API call 💰 → Save to cache
    ├─ CV4: Check cache → FOUND ✅ (FREE)
    └─ ... (95% cache hit rate = 95% FREE!)
    ↓
Tính cosine similarity
    ↓
Return top 50 CVs
```

## 🔧 Implementation Details

### 1. Cache ở bước nào?

**Bước 1: Cache CV Embeddings** (quan trọng nhất)
- **Khi nào**: Ngay sau khi tạo embedding cho CV lần đầu
- **Tại sao**: CVs không thay đổi thường xuyên, dùng lại nhiều lần
- **Lợi ích**: Tiết kiệm 90-95% API calls

**Bước 2: Cache JD Embeddings** (tùy chọn)
- **Khi nào**: Nếu JD được dùng nhiều lần (cùng 1 vị trí tuyển dụng)
- **Tại sao**: JD có thể dùng lại cho nhiều batch CVs
- **Lợi ích**: Tiết kiệm thêm vài API calls

### 2. Cách connect với database.py

**Architecture:**
```
SQLite (database.py)          ChromaDB (vector_db.py)
├─ files table               ├─ cv_embeddings collection
│  ├─ id (primary key)       │  ├─ doc_id: cv_{file_id}_{hash}
│  ├─ filename               │  ├─ embedding: [1536 floats]
│  ├─ content                │  └─ metadata: {file_id, filename, hash}
│  └─ file_type             
└─ Metadata storage          └─ jd_embeddings collection
                                ├─ doc_id: jd_{jd_id}_{hash}
                                ├─ embedding: [1536 floats]
                                └─ metadata: {jd_id, filename, hash}
```

**Workflow kết hợp:**
```python
# 1. Lấy CVs từ SQLite
cvs = get_all_files(file_type='cv')  # database.py

# 2. Cho mỗi CV, kiểm tra cache
for cv in cvs:
    # Thử lấy từ ChromaDB trước
    embedding = vector_db.get_cached_cv_embedding(cv['id'], cv['content'])
    
    if not embedding:
        # Cache miss → Call OpenAI API
        embedding = get_embedding(cv['content'])
        # Lưu vào cache
        vector_db.cache_cv_embedding(cv['id'], cv['filename'], cv['content'], embedding)
```

## 📝 Usage Examples

### Example 1: Upload CV và auto-cache embedding
```python
from vector_db import cache_cv_embedding
from database import save_file_to_database

# Upload CV
file_id = save_file_to_database(...)

# Extract text
cv_text = extract_text_from_file(file_path)

# Tạo embedding
embedding = get_embedding(cv_text)

# Cache ngay
cache_cv_embedding(file_id, filename, cv_text, embedding)
```

### Example 2: Matching với cache
```python
# Lần 1: Cache miss → Call API
embedding1 = get_embedding(cv_text, cache_id=1, cache_type='cv')
# 📊 Cache stats: 0 hits, 1 misses

# Lần 2: Cache hit → FREE
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

### Example 4: Clear cache (khi cần)
```python
from vector_db import clear_cache

# Xóa cache CVs
clear_cache('cv_embeddings')

# Xóa tất cả
clear_cache()
```

## 🚀 Installation

```bash
# Install ChromaDB
pip install chromadb>=0.4.0

# hoặc
pip install -r requirements.txt
```

## ⚙️ Configuration

ChromaDB sẽ tự động tạo folder `chroma_db/` bên cạnh file `data.db`:
```
ai-be/
├── data.db              ← SQLite (metadata)
├── chroma_db/           ← ChromaDB (embeddings cache)
│   ├── cv_embeddings/
│   └── jd_embeddings/
└── cvs/
```

## 🔍 Verification

Để kiểm tra cache có hoạt động:
```python
# Xem logs
# Lần 1: 🔄 Generating new embedding via OpenAI API...
# Lần 2: 📦 Using cached embedding for cv 123
```

## ⚠️ Important Notes

1. **Cache invalidation**: Nếu CV content thay đổi, cache tự động invalid (dùng MD5 hash)
2. **Storage**: ChromaDB lưu persistent, không mất sau khi restart
3. **Performance**: Cache hit = ~instant (< 1ms), API call = ~500-1000ms
4. **Cost**: 1000 CVs × 1 matching với 95% cache hit = chỉ tốn 50 API calls thay vì 1000!

## 📈 Expected Results

**Before cache:**
- 100 CVs matching: ~30-60 seconds
- Cost per matching: ~$0.20

**After cache (95% hit rate):**
- 100 CVs matching: ~5-10 seconds ⚡
- Cost per matching: ~$0.01 💰

**ROI = 6x faster, 20x cheaper!**
