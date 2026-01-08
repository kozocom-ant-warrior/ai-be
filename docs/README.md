# Documentation Directory

Thư mục chứa tài liệu chi tiết về Vector Database Cache implementation.

## 📚 Files

### `VECTOR_CACHE_README.md`
**Quick start guide** - Tổng quan về vector cache implementation.

**Nội dung:**
- ✅ Tình trạng implementation
- 🚀 Quick commands
- 📊 Cache strategy
- 💰 Cost savings
- 🔍 How it works

**Đọc file này trước!**

---

### `CHROMADB_CONNECTION_GUIDE.md`
**Connection guide** - Chi tiết các cách connect vào ChromaDB.

**Nội dung:**
- 🔌 3 connection modes (Persistent, HTTP, In-Memory)
- 🔍 4 methods để xem data
- 🛠️ Tools & Libraries
- 📊 Inspect ChromaDB structure
- 🚀 Quick start examples
- 🔧 Troubleshooting

---

### `CHROMADB_VS_FAISS.md`
**Comparison guide** - So sánh ChromaDB vs Faiss.

**Nội dung:**
- 📊 Feature comparison table
- 💻 Code examples
- 🔥 Benchmark results
- 💰 Development cost comparison
- 📈 Migration path
- 🎓 When to use which

**Đọc khi cân nhắc migrate sang Faiss**

---

### `JD_CACHE_STRATEGY.md`
**Cache invalidation strategy** - Giải thích fuzzy matching cho JD cache.

**Nội dung:**
- ❓ Problem statement
- 💡 Solution (Exact vs Fuzzy matching)
- 📊 Comparison & trade-offs
- 🎯 Implementation details
- 🔍 Examples
- ⚙️ Tuning threshold
- 📈 Expected savings

**Đọc để hiểu tại sao JD cache dùng fuzzy matching**

---

### `VECTOR_DB_GUIDE.md`
**Original implementation guide** - Hướng dẫn tổng quan ban đầu.

**Nội dung:**
- 🎯 Purpose
- 💰 Cost savings
- 📊 Cache optimization flow
- 🔧 Implementation details
- 📝 Usage examples

---

## 🗂️ Reading Order

**Cho người mới:**
1. `VECTOR_CACHE_README.md` - Quick overview
2. `CHROMADB_CONNECTION_GUIDE.md` - How to connect & view data
3. `VECTOR_DB_GUIDE.md` - Detailed implementation

**Cho advanced users:**
1. `JD_CACHE_STRATEGY.md` - Understanding fuzzy cache
2. `CHROMADB_VS_FAISS.md` - Scaling considerations

---

## 🔄 Updates

Khi update implementation:
1. Update relevant `.md` files
2. Keep examples in sync with code
3. Update cost estimates if pricing changes
4. Add migration notes if breaking changes

---

## 📝 Contribution

Khi thêm features:
1. Document trong file `.md` phù hợp
2. Thêm examples cụ thể
3. Update `VECTOR_CACHE_README.md` nếu cần
4. Giữ documentation ngắn gọn và actionable

---

## 🔗 Related

- **Tools:** [../tools/](../tools/) - CLI tools để inspect ChromaDB
- **Code:** [../db/vector_db.py](../db/vector_db.py) - Vector DB module
- **Config:** [../config.py](../config.py) - Configuration
