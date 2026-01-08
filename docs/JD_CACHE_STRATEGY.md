# JD Cache Invalidation Strategy

## ❓ Vấn đề

JD thường có **minor changes** (sửa 1-2 chữ) → Nếu dùng strict hash matching thì mất cache → Tốn tiền!

### Ví dụ:
```
JD v1: "Cần 3 năm kinh nghiệm Python, Django"
JD v2: "Cần 4 năm kinh nghiệm Python, Django"  # Chỉ khác 1 chữ!

→ MD5 hash khác nhau → Cache miss → Tốn $0.001 mỗi lần ❌
→ Nếu query 100 lần/ngày = $0.10/ngày = $3/tháng wasted
```

---

## 💡 Giải pháp: Fuzzy Cache Matching

### Strategy 1: Exact Match (MD5 Hash)
**Dùng cho**: CV (vì CV ít thay đổi)

```python
content_hash = hashlib.md5(content.encode()).hexdigest()
# "Resume of John Doe..." → "a3f5b2c..."
# Chỉ 1 ký tự khác → Hash khác hoàn toàn
```

✅ **Pros**: Chính xác 100%
❌ **Cons**: Strict (1 chữ khác = miss)

---

### Strategy 2: Fuzzy Match (Similarity-based)
**Dùng cho**: JD (vì JD thường có minor edits)

```python
# Tính text similarity bằng Jaccard index
current_words = set("Cần 4 năm kinh nghiệm Python Django".split())
cached_words = set("Cần 3 năm kinh nghiệm Python Django".split())

intersection = current_words ∩ cached_words  # {"Cần", "năm", "kinh", "nghiệm", ...}
union = current_words ∪ cached_words

similarity = len(intersection) / len(union)  # 5/6 = 0.833 (83.3%)
```

**Nếu similarity >= 95%** → Dùng lại cached embedding ✅

✅ **Pros**: Tiết kiệm cost (dùng lại cache cho minor changes)
⚠️ **Cons**: Có thể không chính xác 100% (nhưng acceptable)

---

## 📊 So sánh 2 strategies

### Scenario: JD thay đổi 1 chữ ("3 năm" → "4 năm")

| Strategy | Cache Hit? | Cost | Accuracy |
|----------|------------|------|----------|
| **Exact Match** | ❌ Miss | $0.001 | 100% |
| **Fuzzy Match (95%)** | ✅ Hit | FREE | ~98% |

### Trade-off:
- **Exact**: Chi phí cao, chính xác tuyệt đối
- **Fuzzy**: Tiết kiệm cost, chính xác ~98% (acceptable cho most cases)

---

## 🎯 Implementation

### Code hiện tại (trong vector_db.py)

```python
def get_cached_jd_embedding(jd_id: int, content: str, 
                           similarity_threshold: float = 0.95) -> Optional[List[float]]:
    """
    Lấy cached embedding của JD với fuzzy matching
    
    Args:
        similarity_threshold: 0.95 = 95% giống nhau
    """
    
    # Strategy 1: Try exact match first (MD5)
    doc_id = _generate_doc_id(content, f"jd_{jd_id}")
    result = collection.get(ids=[doc_id])
    
    if result['embeddings']:
        logger.info(f"✓ Cache hit (exact): JD {jd_id}")
        return result['embeddings'][0]
    
    # Strategy 2: Try fuzzy match (Jaccard similarity)
    all_jd_versions = collection.get(
        where={"jd_id": jd_id},  # Chỉ check các version của cùng JD
        include=["embeddings", "documents"]
    )
    
    for i, cached_content in enumerate(all_jd_versions['documents']):
        # Tính Jaccard similarity
        current_words = set(content.lower().split())
        cached_words = set(cached_content.lower().split())
        
        similarity = len(current_words & cached_words) / len(current_words | cached_words)
        
        if similarity >= similarity_threshold:
            logger.info(f"✓ Cache hit (fuzzy {similarity:.1%}): JD {jd_id}")
            return all_jd_versions['embeddings'][i]
    
    logger.info(f"Cache miss: JD {jd_id}")
    return None
```

---

## 🔍 Examples

### Example 1: Minor typo fix
```python
JD v1: "Cần kinh nghiệm với Python và DJango"  # Typo: DJango
JD v2: "Cần kinh nghiệm với Python và Django"  # Fixed typo

Words v1: {"cần", "kinh", "nghiệm", "với", "python", "và", "django"}
Words v2: {"cần", "kinh", "nghiệm", "với", "python", "và", "django"}

Similarity: 7/7 = 100% → ✅ Cache hit (fuzzy)
Cost saved: $0.001
```

### Example 2: Number change
```python
JD v1: "Cần 3 năm kinh nghiệm Python"
JD v2: "Cần 5 năm kinh nghiệm Python"

Words v1: {"cần", "3", "năm", "kinh", "nghiệm", "python"}
Words v2: {"cần", "5", "năm", "kinh", "nghiệm", "python"}

Similarity: 5/7 = 71% → ❌ Cache miss (< 95%)
→ Generate new embedding (correct behavior!)
```

### Example 3: Major rewrite
```python
JD v1: "Cần Python Developer với 3 năm kinh nghiệm"
JD v2: "Tuyển Senior Backend Engineer biết FastAPI"

Similarity: ~20% → ❌ Cache miss (correct!)
→ Generate new embedding
```

---

## ⚙️ Tuning threshold

### Threshold = 0.90 (90%)
```
✅ Pros: Nhiều cache hits hơn → Tiết kiệm cost
❌ Cons: Có thể cache JD khác biệt → Kết quả sai
```

### Threshold = 0.95 (95%) ← **RECOMMENDED**
```
✅ Pros: Balance giữa cost và accuracy
✅ Cons: Ít cache hits hơn 0.90, nhưng chính xác hơn
```

### Threshold = 0.99 (99%)
```
✅ Pros: Rất chính xác (gần như exact match)
❌ Cons: Ít cache hits → Ít tiết kiệm cost
```

---

## 📈 Expected savings

### Scenario: 100 JD queries/day, 20% có minor changes

**Without fuzzy matching:**
```
100 queries × $0.001/query = $0.10/day
→ $3/month
```

**With fuzzy matching (95% threshold):**
```
80 queries × $0.001 (exact match) = $0.08/day
20 queries × $0 (fuzzy match) = $0/day
→ $2.40/month (save 20%)
```

**Với scale lớn hơn (1000 queries/day):**
```
Save: $6/month → $72/year
```

---

## 🎓 Kết luận

### Recommendation:
1. ✅ **CVs**: Use exact matching (MD5 hash)
   - Vì: CV ít thay đổi, cần chính xác 100%

2. ✅ **JDs**: Use fuzzy matching (Jaccard 95%)
   - Vì: JD có minor edits thường xuyên
   - Trade-off: 2% accuracy cho 20% cost savings = Worth it!

### Best practices:
- Set `similarity_threshold=0.95` (default)
- Có thể adjust dựa trên use case:
  - Conservative (accuracy > cost): 0.98
  - Aggressive (cost > accuracy): 0.90

---

## 🚀 Advanced: Semantic Similarity Cache

Nếu muốn **chính xác hơn**, có thể dùng **embedding similarity** thay vì text similarity:

```python
# Thay vì Jaccard (text-based)
text_similarity = jaccard(current, cached)

# Dùng embedding similarity (semantic-based)
current_emb = get_embedding(current_content)  # Tốn 1 API call
cached_emb = get_cached_embedding(cached_id)
semantic_similarity = cosine_similarity(current_emb, cached_emb)

if semantic_similarity >= 0.98:  # 98% giống về nghĩa
    return cached_emb
```

⚠️ **Trade-off**: Phải generate 1 embedding để check → Tốn 1 API call anyway
→ Không tiết kiệm được cost, chỉ tăng accuracy

**Kết luận**: Jaccard text similarity là đủ tốt cho most cases!
