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

### CV Embeddings (Exact Match)
- ✅ Cache mỗi khi tạo embedding cho CV
- ✅ Dùng MD5 hash để check exact match
- ✅ Tiết kiệm ~95% API cost sau lần đầu

### JD Embeddings (Fuzzy Match)  
- ✅ Cache với fuzzy matching (95% similarity)
- ✅ Reuse embedding nếu JD chỉ thay đổi nhỏ (1-2 từ)
- ✅ Tiết kiệm ~20% API cost cho JD minor edits

## 💰 Cost Savings

**Without cache:**
```
100 CVs × 1 matching = 100 API calls = $0.20
```

**With cache (95% hit rate):**
```
100 CVs × 1 matching = 5 API calls = $0.01 (20x rẻ hơn!)
```

## 📁 ChromaDB Structure

```
chroma_db/
├── chroma.sqlite3           # Metadata (SQLite)
├── cv_embeddings/           # CV embedding vectors
│   ├── data_level0.bin
│   └── header.bin
└── jd_embeddings/           # JD embedding vectors
    ├── data_level0.bin
    └── header.bin
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
