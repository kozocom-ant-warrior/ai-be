# Documentation Directory

This directory contains detailed documentation about the Vector Database Cache implementation.

## 📚 Files

### `VECTOR_CACHE_README.md`
**Quick start guide** - Overview of vector cache implementation.

**Contents:**
- ✅ Implementation status
- 🚀 Quick commands
- 📊 Cache strategy
- 💰 Cost savings
- 🔍 How it works

**Read this file first!**

---

### `CHROMADB_CONNECTION_GUIDE.md`
**Connection guide** - Details on various ways to connect to ChromaDB.

**Contents:**
- 🔌 3 connection modes (Persistent, HTTP, In-Memory)
- 🔍 4 methods to view data
- 🛠️ Tools & Libraries
- 📊 Inspect ChromaDB structure
- 🚀 Quick start examples
- 🔧 Troubleshooting

---

### `CHROMADB_VS_FAISS.md`
**Comparison guide** - ChromaDB vs Faiss comparison.

**Contents:**
- 📊 Feature comparison table
- 💻 Code examples
- 🔥 Benchmark results
- 💰 Development cost comparison
- 📈 Migration path
- 🎓 When to use which

**Read when considering migrating to Faiss**

---

### `JD_CACHE_STRATEGY.md`
**Cache invalidation strategy** - Explains fuzzy matching for JD cache.

**Contents:**
- ❓ Problem statement
- 💡 Solution (Exact vs Fuzzy matching)
- 📊 Comparison & trade-offs
- 🎯 Implementation details
- 🔍 Examples
- ⚙️ Tuning threshold
- 📈 Expected savings

**Read to understand why JD cache uses fuzzy matching**

---

### `VECTOR_DB_GUIDE.md`
**Original implementation guide** - Initial comprehensive guide.

**Contents:**
- 🎯 Purpose
- 💰 Cost savings
- 📊 Cache optimization flow
- 🔧 Implementation details
- 📝 Usage examples

---

## 🗂️ Reading Order

**For beginners:**
1. `VECTOR_CACHE_README.md` - Quick overview
2. `CHROMADB_CONNECTION_GUIDE.md` - How to connect & view data
3. `VECTOR_DB_GUIDE.md` - Detailed implementation

**For advanced users:**
1. `JD_CACHE_STRATEGY.md` - Understanding fuzzy cache
2. `CHROMADB_VS_FAISS.md` - Scaling considerations

---

## 🔄 Updates

When updating implementation:
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
