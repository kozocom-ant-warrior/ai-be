# Tools Directory

This directory contains CLI tools for managing, testing, and inspecting the CV-JD matching system.

## 🧪 Testing Strategy by Stage

The system uses a 3-stage pipeline. Here's what gets tested and why:

| Stage | Type | Test File | Reason |
|-------|------|-----------|--------|
| **Stage 0** | Vector Search | `test_chroma_connection.py` | Test ChromaDB connection and setup |
| **Stage 1A** | OpenAI API (JD) | `test_jd_text_input.py` | Test JD text extraction |
| **Stage 1B** | OpenAI API (CV) | `test_thinking.sh` | Integration test (full pipeline) |
| **Stage 2** | Pure Python Logic | `test_two_stage.py` | **Unit test for scoring algorithm** |
| **Stage 3** | OpenAI API (Advanced) | `test_thinking.sh` | Integration test (full pipeline) |
| **Utils** | Text Processing | `test_emoji_cleaning.py` | Test emoji removal logic |

**Why only Stage 2 has unit tests?**
- **Stages 0, 1, 3**: External APIs (OpenAI, ChromaDB) → Use integration tests instead
- **Stage 2**: Pure Python logic → **Can and must** be unit tested for correctness

---

## 📁 Files

### Testing Tools

#### `test_two_stage.py`
Unit test for Stage 2 deterministic scoring logic.

**Usage:**
```bash
uv run python tools/testing/test_two_stage.py
```

**What it tests:**
- CVScoringEngine scoring algorithm
- Deterministic behavior (same input → same output)
- Score ranges for different match scenarios

---

#### `test_emoji_cleaning.py`
Test emoji and special character removal logic.

**Usage:**
```bash
uv run python tools/testing/test_emoji_cleaning.py
```

**What it tests:**
- `clean_text_for_embedding()` function from utils.py
- Emoji removal from CV/JD text
- Unicode character handling

---

#### `test_jd_text_input.py`
Test JD text extraction and processing.

**Usage:**
```bash
uv run python tools/testing/test_jd_text_input.py
```

---

#### `test_thinking.sh`
Integration test for the full CV-JD matching pipeline.

**Usage:**
```bash
bash tools/testing/test_thinking.sh
```

**What it tests:**
- Full `/thinking` API endpoint
- All 3 stages working together
- Response format validation

---

### Cache Management Tools

#### `test_chroma_connection.py`
Test ChromaDB connection and display basic statistics.

**Usage:**
```bash
uv run python tools/cache/test_chroma_connection.py
```

**Output:**
- ✅ ChromaDB connection status
- 📊 Number of collections
- 📄 Number of embeddings cached
- 💰 Estimated API cost saved

---

#### `chroma_inspector.py`
CLI tool để inspect, export, và quản lý ChromaDB collections.

**Usage:**
```bash
# List all collections
uv run python tools/cache/chroma_inspector.py --list

# Show statistics
uv run python tools/cache/chroma_inspector.py --stats

# View collection details
uv run python tools/cache/chroma_inspector.py --collection cv_embeddings

# View with custom limit
uv run python tools/cache/chroma_inspector.py --collection cv_embeddings --limit 20

# Export to JSON
uv run python tools/cache/chroma_inspector.py --export output.json --collection cv_embeddings

# Clear collection
uv run python tools/cache/chroma_inspector.py --clear cv_embeddings

# Clear without confirmation prompt
uv run python tools/cache/chroma_inspector.py --clear cv_embeddings --yes
```

**Features:**
- List all ChromaDB collections
- View detailed statistics
- Inspect collection contents
- Export data to JSON
- Clear/delete collections
- Custom result limits

---

#### `clear_cache.py`
Delete all cached embeddings and extracted data.

**Usage:**
```bash
uv run python tools/cache/clear_cache.py
```

**When to use:**
- After changing OpenAI models
- After modifying prompt templates
- When cache becomes corrupted

---

#### `debug_cache.py`
Debug tool to troubleshoot cache miss issues.

**Usage:**
```bash
uv run python tools/cache/debug_cache.py
```

**When to use:**
- Cache not working as expected
- Investigating why cache misses occur
- Checking hash matching logic
- View detailed cache hit/miss analysis

---

## 🚀 Quick Start

1. **Check if ChromaDB is set up:**
   ```bash
   uv run python tools/cache/test_chroma_connection.py
   ```

2. **View cache statistics:**
   ```bash
   uv run python tools/cache/chroma_inspector.py --stats
   ```

3. **Export cache for backup:**
   ```bash
   uv run python tools/cache/chroma_inspector.py --export backup.json --collection cv_embeddings
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
