# Multi-Language Cache Strategy

## 📌 Problem

When changing `PROMPT_LANGUAGE`, the system needs to ensure:
1. **Don't use cache from wrong language**
2. **Each language has separate cache** to avoid conflicts
3. **Response in correct language** matching the request

## ❓ Frequently Asked Questions

### Q: If I set `PROMPT_LANGUAGE=en`, send to OpenAI, save cache. Then switch to `PROMPT_LANGUAGE=vi`, will it call OpenAI again?

**A: YES, the system will call OpenAI again because:**

#### Try 1: `PROMPT_LANGUAGE=en`
```python
jd_text = "Need 3 years Python experience"
PROMPT_LANGUAGE = "en"

# Cache key includes language
cache_key = f"{jd_text}_en"
jd_hash = md5("Need 3 years Python experience_en") = "abc123..."

# Call OpenAI with English prompt
# Response: {"role_type": "Backend Developer", "must_have_requirements": [...]}
# → Cache with key "abc123"
```

#### Try 2: `PROMPT_LANGUAGE=vi` (same JD text)
```python
jd_text = "Need 3 years Python experience"  # Same text
PROMPT_LANGUAGE = "vi"  # DIFFERENT language!

# Cache key DIFFERENT because language is different
cache_key = f"{jd_text}_vi"
jd_hash = md5("Need 3 years Python experience_vi") = "xyz789..."  # DIFFERENT hash!

# Cache not found with key "xyz789"
# → Call OpenAI again with Vietnamese prompt
# Response: {"role_type": "Lập trình viên Backend", "must_have_requirements": [...]}
# → Cache with key "xyz789"
```

### Q: Why not share cache between languages?

**A: Because response content is DIFFERENT:**

| Language | JD Text | Prompt | Response |
|----------|---------|--------|----------|
| `en` | "Need 3 years Python" | English prompt | `{"role_type": "Backend Developer", ...}` |
| `vi` | "Need 3 years Python" | Vietnamese prompt | `{"role_type": "Lập trình viên Backend", ...}` |
| `ja` | "Need 3 years Python" | Japanese prompt | `{"role_type": "バックエンドエンジニア", ...}` |

→ **Same JD but different language responses** → Need separate cache!

## 🔧 Implementation

### Cache Keys with PROMPT_LANGUAGE

All cache keys include `PROMPT_LANGUAGE`:

```python
from config import PROMPT_LANGUAGE

# 1. Stage 1: JD Embedding Cache
jd_cache_key = f"{jd_text}_{PROMPT_LANGUAGE}"
jd_hash = hashlib.md5(jd_cache_key.encode('utf-8')).hexdigest()

# 2. Stage 1A: JD Requirements Cache
jd_cache_key_stage1a = f"{jd_text}_{PROMPT_LANGUAGE}"
jd_hash_for_stage1a = hashlib.md5(jd_cache_key_stage1a.encode('utf-8')).hexdigest()

# 3. Stage 1B: CV Extraction Cache
jd_cache_key = f"{jd_text}_{PROMPT_LANGUAGE}"
jd_hash = hashlib.md5(jd_cache_key.encode('utf-8')).hexdigest()

# 4. Stage 3: Advanced Features Cache
options_str = json.dumps(advanced_options, sort_keys=True) + f"_lang_{PROMPT_LANGUAGE}"
options_hash = hashlib.md5(options_str.encode()).hexdigest()
```

### CV Embedding Cache

**Note:** CV embeddings **DO NOT** depend on `PROMPT_LANGUAGE` because:
- Embeddings are only used for similarity calculation (vector search)
- CV content does not change based on prompt language
- CV embedding cache is based on `cv_content` hash

```python
# CV embedding cache - DOES NOT include PROMPT_LANGUAGE
content_hash = hashlib.md5(cv_content.encode()).hexdigest()
cached_embedding = vector_db.get_cached_cv_embedding(cv_id, cv_content)
```

## 💰 Cost Impact

### Scenario: Changing language for the same JD

**Try 1: PROMPT_LANGUAGE=vi**
```
Stage 1A: Extract JD requirements → Call OpenAI → Cache
Stage 1B: Extract 50 CVs → Call OpenAI → Cache
Stage 3: Advanced features for 5 CVs → Call OpenAI → Cache
Total: ~$4.00
```

**Try 2: PROMPT_LANGUAGE=en (same JD)**
```
Stage 1A: Cache MISS (different language) → Call OpenAI → ~$0.50
Stage 1B: Cache MISS (different language) → Call OpenAI → ~$2.50
Stage 3: Cache MISS (different language) → Call OpenAI → ~$1.50
Total: ~$4.50
```

**Try 3: PROMPT_LANGUAGE=en (same JD, same language)**
```
Stage 1A: Cache HIT → FREE
Stage 1B: Cache HIT → FREE
Stage 3: Cache HIT → FREE
Total: ~$0.00 ✅
```

→ **Cost incurred only on first language switch**, subsequent uses of the same language are FREE!

## 🎯 Best Practices

### 1. Choose language before starting
```bash
# Set in .env BEFORE running
PROMPT_LANGUAGE=vi  # Or en, ja
```

### 2. Avoid frequent language switching
- Changing language = Clear cache = Costs money
- Should stick with 1 language per project

### 3. Clear cache when needed
```bash
# Clear specific language cache (coming soon)
uv run python tools/cache/clear_cache.py --language vi

# Clear all cache
uv run python tools/cache/clear_cache.py --all
```

## 📊 Cache Statistics by Language

```bash
# View cache stats per language (coming soon)
uv run python tools/cache/chroma_inspector.py --stats --language vi
uv run python tools/cache/chroma_inspector.py --stats --language en
uv run python tools/cache/chroma_inspector.py --stats --language ja
```

## ⚡ Performance

| Scenario | Cache Behavior | Cost | Speed |
|----------|----------------|------|-------|
| Same JD + Same language | ✅ Cache HIT | FREE | Instant |
| Same JD + Different language | ❌ Cache MISS | Full cost | ~10-30s |
| Different JD + Same language | ❌ Cache MISS | Full cost | ~10-30s |
| Different JD + Different language | ❌ Cache MISS | Full cost | ~10-30s |

## 🔍 Debugging

### Check cache key
```python
from config import PROMPT_LANGUAGE
import hashlib

jd_text = "Your JD text here"
cache_key = f"{jd_text}_{PROMPT_LANGUAGE}"
jd_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()

print(f"Language: {PROMPT_LANGUAGE}")
print(f"Cache key: {cache_key[:50]}...")
print(f"Hash: {jd_hash}")
```

### Logs
When running the API, check logs:
```
🔍 JD TEXT DEBUG:
   Length: 500 chars
   PROMPT_LANGUAGE: vi
   MD5 Hash (with lang): abc123...
   
📦 Cache HIT: JD requirements (lang=vi)
```
