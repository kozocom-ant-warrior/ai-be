# Tools Directory

Thư mục chứa các công cụ CLI để quản lý và inspect ChromaDB cache.

## 📁 Files

### `test_chroma_connection.py`
Script test connection đến ChromaDB và hiển thị thống kê cơ bản.

**Usage:**
```bash
uv run python tools/test_chroma_connection.py
```

**Output:**
- ✅ ChromaDB connection status
- 📊 Number of collections
- 📄 Number of embeddings cached
- 💰 Estimated API cost saved

---

### `chroma_inspector.py`
CLI tool để inspect, export, và quản lý ChromaDB collections.

**Usage:**
```bash
# List all collections
uv run python tools/chroma_inspector.py --list

# Show statistics
uv run python tools/chroma_inspector.py --stats

# View collection details
uv run python tools/chroma_inspector.py --collection cv_embeddings

# View with custom limit
uv run python tools/chroma_inspector.py --collection cv_embeddings --limit 20

# Export to JSON
uv run python tools/chroma_inspector.py --export output.json --collection cv_embeddings

# Clear collection
uv run python tools/chroma_inspector.py --clear cv_embeddings

# Clear without confirmation prompt
uv run python tools/chroma_inspector.py --clear cv_embeddings --yes
```

**Features:**
- List all ChromaDB collections
- View detailed statistics
- Inspect collection contents
- Export data to JSON
- Clear/delete collections
- Custom result limits

---

## 🚀 Quick Start

1. **Check if ChromaDB is set up:**
   ```bash
   uv run python tools/test_chroma_connection.py
   ```

2. **View cache statistics:**
   ```bash
   uv run python tools/chroma_inspector.py --stats
   ```

3. **Export cache for backup:**
   ```bash
   uv run python tools/chroma_inspector.py --export backup.json --collection cv_embeddings
   ```

---

## 📝 Notes

- ChromaDB path: `../chroma_db/` (relative to project root)
- Collections:
  - `cv_embeddings`: CV embedding cache
  - `jd_embeddings`: JD embedding cache
- Tools run from project root, not from tools directory

---

## 🔧 Development

Để modify tools:
1. Edit Python scripts trong thư mục này
2. Test bằng: `uv run python tools/<script_name>.py`
3. Update README.md nếu có thay đổi usage

---

## 📚 Related Documentation

See [../docs/](../docs/) for detailed guides on ChromaDB and vector caching.
