# Multi-Language Prompt System

## 🌍 Overview

The system supports 3 languages for prompts:
- 🇻🇳 **Vietnamese** (`vi`) - Default
- 🇬🇧 **English** (`en`)
- 🇯🇵 **Japanese** (`ja`)

## 🚀 Usage

### 1. Configure language in `.env`

```bash
# Choose language: vi, en, or ja
PROMPT_LANGUAGE=vi
```

### 2. Import and use (code remains unchanged)

```python
# Import as usual
from prompts import get_extraction_prompt, get_cv_matching_prompt

# Use functions as before
prompt = get_extraction_prompt(jd_text, response_requirement)
```

The system automatically loads the appropriate prompt file!

## 📁 File Structure

```
ai-be/
├── prompts.py           # Dynamic loader (auto-selects language)
├── prompts.vi.py        # Vietnamese prompts
├── prompts.en.py        # English prompts  
└── prompts.ja.py        # Japanese prompts
```

## 🔄 How It Works

```python
# 1. Load PROMPT_LANGUAGE from .env
PROMPT_LANGUAGE = os.getenv("PROMPT_LANGUAGE", "vi")

# 2. Dynamic loader selects corresponding file
if PROMPT_LANGUAGE == "vi":
    load prompts.vi.py
elif PROMPT_LANGUAGE == "en":
    load prompts.en.py
elif PROMPT_LANGUAGE == "ja":
    load prompts.ja.py

# 3. Export all functions
get_extraction_prompt = _prompt_module.get_extraction_prompt
get_cv_matching_prompt = _prompt_module.get_cv_matching_prompt
...
```

## ⚙️ Exported Functions

All prompt files export the following functions:

```python
# Stage 1A: Extract JD requirements
get_extraction_prompt(jd_text, response_requirement) -> str

# Stage 1B: Extract CV data and match
get_cv_extraction_prompt(cv_contents_text, requirements) -> str

# Stage 2: Match CV with JD (legacy single-stage)
get_cv_matching_prompt(jd_text, response_requirement, cv_contents_text, advanced_options) -> str

# Stage 3: Advanced features
get_stage3_advanced_prompt(cv_data_list, jd_text, requirements, advanced_options) -> str

# System message
get_system_message() -> str

# Helper
format_cv_contents(cv_data_list) -> str
```

## 🧪 Testing

### Test each language:

```bash
# Vietnamese (default)
uv run python -c "from prompts import get_extraction_prompt; print('✅ VI works')"

# English
PROMPT_LANGUAGE=en uv run python -c "from prompts import get_extraction_prompt; print('✅ EN works')"

# Japanese
PROMPT_LANGUAGE=ja uv run python -c "from prompts import get_extraction_prompt; print('✅ JA works')"
```

### Expected output:

```
✅ Loaded prompt module: prompts.vi (language: vi)
✅ VI works
```

## 💾 Cache Strategy

### ⚠️ IMPORTANT: Each language has its own cache!

When changing `PROMPT_LANGUAGE`, cache will **MISS** because the cache key includes the language:

```python
# Cache key format
cache_key = f"{jd_text}_{PROMPT_LANGUAGE}"
```

### Example:

**Try 1: `PROMPT_LANGUAGE=en`**
```
JD: "Need 3 years Python"
Cache key: md5("Need 3 years Python_en") = "abc123..."
→ Call OpenAI (English prompt) → Cache result
```

**Try 2: `PROMPT_LANGUAGE=vi` (same JD)**
```
JD: "Need 3 years Python"  
Cache key: md5("Need 3 years Python_vi") = "xyz789..."  # DIFFERENT!
→ Cache MISS → Call OpenAI (Vietnamese prompt) → Cache result
```

**Try 3: `PROMPT_LANGUAGE=en` (back to English)**
```
JD: "Need 3 years Python"
Cache key: md5("Need 3 years Python_en") = "abc123..."  # Same as Try 1!
→ Cache HIT → Reuse result from Try 1 (FREE!)
```

### 💰 Cost Impact

| Scenario | Cache | Cost |
|----------|-------|------|
| First time with new language | MISS | ~$4.00 |
| Reuse same language | HIT | FREE |
| Switch to different language | MISS | ~$4.00 |
| Switch back to previous language | HIT | FREE |

📖 **Details:** See [MULTI_LANGUAGE_CACHE.md](MULTI_LANGUAGE_CACHE.md)

## 🎯 Best Practices

### ✅ DO:
- Set `PROMPT_LANGUAGE` in `.env` **BEFORE** running server
- Stick with 1 language per project
- Test with other languages before deployment

### ❌ DON'T:
- Change `PROMPT_LANGUAGE` frequently (wastes cache = wastes money)
- Forget to restart server after changing language
- Mix responses from multiple languages

## 🔧 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'prompts.vi'"

**Cause:** File `prompts.vi.py` does not exist

**Fix:**
```bash
# Check file exists
ls -la prompts.*.py

# Should see:
# prompts.vi.py
# prompts.en.py
# prompts.ja.py
```

### Error: "PROMPT_LANGUAGE 'xyz' is not supported"

**Cause:** Invalid `PROMPT_LANGUAGE` value

**Fix:** Only use: `vi`, `en`, or `ja`

```bash
# .env
PROMPT_LANGUAGE=vi  # ✅ Valid
# PROMPT_LANGUAGE=fr  # ❌ Invalid (not supported)
```

### Server not loading new language

**Cause:** Server cached `prompts.py` module

**Fix:** Restart server
```bash
# Stop server (Ctrl+C)
# Start again
uv run python main.py
```

## 📊 Monitoring

### Check current language:

```bash
# View logs when starting server
uv run python main.py

# Output:
# ✅ Loaded prompt module: prompts.vi (language: vi)
```

### Check cache statistics:

```bash
# View cache for each language
uv run python tools/cache/chroma_inspector.py --stats
```

## 🆕 Adding New Language

### 1. Create new prompt file

```bash
# Copy from template
cp prompts.vi.py prompts.fr.py  # French

# Edit file and translate all prompts
```

### 2. Update `prompts.py`

```python
SUPPORTED_LANGUAGES = {
    "vi": "prompts.vi",
    "en": "prompts.en",
    "ja": "prompts.ja",
    "fr": "prompts.fr",  # Add this line
}
```

### 3. Test

```bash
PROMPT_LANGUAGE=fr uv run python -c "from prompts import get_extraction_prompt; print('✅ FR works')"
```

## 📚 Related Docs

- [MULTI_LANGUAGE_CACHE.md](MULTI_LANGUAGE_CACHE.md) - Cache strategy details
- [VECTOR_CACHE_README.md](VECTOR_CACHE_README.md) - Vector cache system
- [JD_CACHE_STRATEGY.md](JD_CACHE_STRATEGY.md) - JD cache strategy (deprecated)

## ❓ FAQ

**Q: Is cache shared between languages?**  
A: No. Each language has its own cache to avoid conflicts.

**Q: Does changing language affect CV embeddings?**  
A: No. CV embeddings do not depend on PROMPT_LANGUAGE (only depend on CV content).

**Q: Which language should I use?**  
A: Depends on your team/client. If JD and CV are in Vietnamese → use `vi`. If English → use `en`.

**Q: Is performance different between languages?**  
A: No. Performance only depends on OpenAI API, not on prompt language.
