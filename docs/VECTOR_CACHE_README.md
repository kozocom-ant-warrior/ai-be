# Vector Database Cache - Quick Start

## 📦 Đã implement xong

Source code này **đã có RAG và Vector Cache** sử dụng ChromaDB để cache embeddings.

## 🚀 Quick Commands

### Xem ChromaDB cache
```bash
# Test connection
uv run python tools/test_chroma_connection.py

# View statistics  
uv run python tools/chroma_inspector.py --stats

# List collections
uv run python tools/chroma_inspector.py --list

# View specific collection
uv run python tools/chroma_inspector.py --collection cv_embeddings
```

### Start servers
```bash
# FastAPI server (port 8000)
uv run python main.py

# ChromaDB server (port 8001) - Optional, chỉ cần nếu muốn remote access
uv run chroma run --path ./chroma_db --port 8001
```

## 📊 Cache Strategy

### 1. CV Embeddings (Exact Match)
- ✅ Cache mỗi khi tạo embedding cho CV
- ✅ Dùng MD5 hash để check exact match
- ✅ Tiết kiệm ~95% API cost sau lần đầu
- **Collection**: `cv_embeddings`

### 2. JD Embeddings (Fuzzy Match)  
- ✅ Cache với fuzzy matching (95% similarity)
- ✅ Reuse embedding nếu JD chỉ thay đổi nhỏ (1-2 từ)
- ✅ Tiết kiệm ~20% API cost cho JD minor edits
- **Collection**: `jd_embeddings`

### 3. CV Extracted Data (Exact Match)
- ✅ Cache parsed CV data với JD requirements matching
- ✅ Key: `cv_hash + jd_hash` (phụ thuộc cả CV và JD)
- ✅ Tiết kiệm Stage 1B processing (~$2-3 cho 50 CVs)
- **Collection**: `cv_extracted_data`

### 4. Advanced Features (Exact Match)
- ✅ Cache Stage 3 features (interview questions, CV analysis, job leveling)
- ✅ Key: `jd_hash + cv_id + options_hash`
- ✅ Tiết kiệm Stage 3 processing (~$1-2 cho 5 CVs)
- **Collection**: `advanced_features`
- **Features cached**:
  - `cv_presentation_comment` (object: structure, strengths, issues, highlights, suggestions)
  - `interview_questions` (5 strategic questions)
  - `job_leveling` (array) + `job_leveling_reason` (string)
  - `cert_comment` (certification analysis)

## 💰 Cost Savings

**Without cache (100 CVs, 1 JD):**
```
Stage 0: 100 CV embeddings + 1 JD embedding = $0.20
Stage 1B: 50 CVs extraction (10 batches) = $2.50
Stage 3: 5 CVs advanced features = $1.50
TOTAL: $4.20 per matching
```

**With cache (95% hit rate):**
```
Stage 0: 5 CV embeddings + 0 JD embedding = $0.01
Stage 1B: 0 CVs (all cached) = $0.00
Stage 3: 0 CVs (all cached) = $0.00
TOTAL: $0.01 per matching (420x rẻ hơn!)
```

**Note**: Cache hit rate increases over time as more CVs/JDs are processed.

## 📁 ChromaDB Structure

```
chroma_db/
├── chroma.sqlite3              # Metadata (SQLite)
├── cv_embeddings/              # CV embedding vectors (Stage 0)
│   ├── data_level0.bin
│   └── header.bin
├── jd_embeddings/              # JD embedding vectors (Stage 0)
│   ├── data_level0.bin
│   └── header.bin
├── cv_extracted_data/          # Parsed CV JSONs (Stage 1B)
│   └── ... (extracted requirements matching)
└── advanced_features/          # Advanced analysis (Stage 3)
    └── ... (interview questions, CV comments, job leveling)
```

## 🔍 Cách hoạt động

### Upload CV Flow:
```
1. Upload CV → Extract text → Save to database
2. Generate embedding via OpenAI API ($$$)
3. Cache embedding vào ChromaDB (FREE sau này)
```

### Matching Flow:
```
1. User request matching
2. Check ChromaDB cache
   ├─ Cache hit → Use cached embedding (FREE) ✅
   └─ Cache miss → Call OpenAI API ($$$)
3. Calculate similarity
4. Return top matches
```

## ⚠️ Important Notes

### ChromaDB Server
- ❌ **KHÔNG có built-in Web UI** 
- ✅ Chỉ là REST API endpoint
- ✅ Để xem data, dùng Python scripts (đã tạo sẵn)

### For Local Development
```bash
# Đủ dùng Persistent Client (không cần server)
import chromadb
client = chromadb.PersistentClient(path="./chroma_db")
```

### For Production
```bash
# Start server để team access
uv run chroma run --path ./chroma_db --port 8001
```

## 📚 Documentation

- [3_STAGE_PIPELINE.md](./3_STAGE_PIPELINE.md) - **3-stage pipeline details (READ FIRST!)**
- [CHROMADB_CONNECTION_GUIDE.md](./CHROMADB_CONNECTION_GUIDE.md) - Chi tiết cách connect
- [CHROMADB_VS_FAISS.md](./CHROMADB_VS_FAISS.md) - So sánh ChromaDB vs Faiss
- [JD_CACHE_STRATEGY.md](./JD_CACHE_STRATEGY.md) - Chiến lược cache cho JD
- [VECTOR_DB_GUIDE.md](./VECTOR_DB_GUIDE.md) - Hướng dẫn tổng quan

## 🛠️ Tools

- `tools/test_chroma_connection.py` - Test connection nhanh
- `tools/chroma_inspector.py` - CLI tool để inspect ChromaDB
- `db/vector_db.py` - Module quản lý cache

## ✅ Status

- ✅ ChromaDB cache implemented
- ✅ CV embedding cache (exact match)
- ✅ JD embedding cache (fuzzy match)  
- ✅ CLI tools created
- ✅ Documentation complete
- ⚠️ No Web UI (not available in ChromaDB)

## 🎯 Next Steps

1. Upload CVs: `POST /cv/upload`
2. Run matching: `POST /thinking`
3. Check cache: `uv run python tools/chroma_inspector.py --stats`
4. Enjoy 20x cheaper API cost! 💰
