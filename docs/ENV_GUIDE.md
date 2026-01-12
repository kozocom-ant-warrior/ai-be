# Environment Variables Guide

## 📝 Required Variables

Tạo file `.env` trong thư mục root:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=sk-...your-key-here...

# Model Configuration (Optional - có default values)
OPENAI_MODEL=gpt-4o                      # Main model cho JD extraction
OPENAI_MINI_MODEL=gpt-4o-mini            # Cheaper model cho CV extraction  
OPENAI_EMBEDDING_MODEL=text-embedding-3-small  # Embedding model
```

---

## ⚙️ Model Configuration

### OPENAI_MODEL
**Default:** `gpt-4o`  
**Purpose:** JD extraction và requirement analysis  
**Cost:** $2.50 input / $10.00 output per 1M tokens

**Alternatives:**
- `gpt-4o`: High accuracy (recommended)
- `gpt-4-turbo`: Good balance
- `gpt-3.5-turbo`: Budget option (less accurate)

### OPENAI_MINI_MODEL  
**Default:** `gpt-4o-mini`  
**Purpose:** CV extraction và matching  
**Cost:** $0.150 input / $0.600 output per 1M tokens (16x cheaper!)

**Alternatives:**
- `gpt-4o-mini`: Best value (recommended)
- `gpt-3.5-turbo`: Even cheaper but less accurate

### OPENAI_EMBEDDING_MODEL
**Default:** `text-embedding-3-small`  
**Purpose:** Generate embeddings cho vector similarity  
**Cost:** $0.02 per 1M tokens

**Alternatives:**
- `text-embedding-3-small`: Small, fast (recommended)
- `text-embedding-3-large`: Better quality, expensive
- `text-embedding-ada-002`: Legacy model

---

## 💰 Cost Optimization

### Scenario 1: Production (High Accuracy)
```bash
OPENAI_MODEL=gpt-4o
OPENAI_MINI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```
**Cost:** ~$0.20 per 100 CVs matching

### Scenario 2: Development (Budget)
```bash
OPENAI_MODEL=gpt-4o-mini
OPENAI_MINI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```
**Cost:** ~$0.03 per 100 CVs matching (6x cheaper)

### Scenario 3: Testing (Ultra Budget)
```bash
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_MINI_MODEL=gpt-3.5-turbo
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002
```
**Cost:** ~$0.01 per 100 CVs matching (20x cheaper, lower quality)

---

## 🔍 How Models Are Used

### Stage 1A: JD Extraction
```python
# Uses OPENAI_MODEL (gpt-4o)
# 1 call per matching session
# Extract requirements từ JD
```

### Stage 1B: CV Extraction  
```python
# Uses OPENAI_MINI_MODEL (gpt-4o-mini)
# ~7 calls per 100 CVs (batch processing)
# Extract data từ CVs và match với requirements
```

### Vector Similarity (Pre-filter)
```python
# Uses OPENAI_EMBEDDING_MODEL (text-embedding-3-small)
# 1 call per CV (but cached after first time!)
# Generate embeddings cho similarity search
```

---

## 📊 Token Usage Examples

### 100 CVs Matching Session:

**Stage 1A (JD):**
- Input: ~500 tokens
- Output: ~200 tokens
- Cost: $0.002 (với gpt-4o)

**Stage 1B (CVs):**
- Input: ~50,000 tokens (7 batches × 7 CVs)
- Output: ~15,000 tokens
- Cost: $0.017 (với gpt-4o-mini)

**Embeddings:**
- First time: ~50,000 tokens (100 CVs)
- Cost: $0.001 (cached sau đó = FREE!)

**Total:** ~$0.020 per session (sau khi có cache)

---

## 🚀 Quick Setup

```bash
# 1. Copy example env
cp .env.example .env

# 2. Edit với API key của bạn
nano .env

# 3. (Optional) Customize models nếu muốn
# Nếu không set, sẽ dùng default values

# 4. Restart server
uv run python main.py
```

---

## ✅ Verification

Check models đang được dùng:
```bash
# Xem logs khi server start
uv run python main.py

# Output sẽ hiển thị:
# Đang gọi OpenAI (gpt-4o) để extract requirements...
# Đang gọi OpenAI API (gpt-4o-mini) cho batch 1...
# Generating new embedding via OpenAI API (text-embedding-3-small)...
```

---

## 🔧 Troubleshooting

### "Model not found"
- Check model name spelling trong `.env`
- Verify OpenAI API key có quyền access model đó

### "Rate limit exceeded"  
- Giảm BATCH_SIZE trong thinking.py
- Hoặc đổi sang model rẻ hơn (ít rate limit)

### Costs too high
- Enable vector cache (đã có sẵn)
- Đổi OPENAI_MODEL sang gpt-4o-mini
- Giảm số CVs process mỗi lần

---

## 📚 References

- [OpenAI Pricing](https://openai.com/pricing)
- [Model Comparison](https://platform.openai.com/docs/models)
- [Best Practices](https://platform.openai.com/docs/guides/rate-limits)
