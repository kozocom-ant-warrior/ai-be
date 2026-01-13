# 3-Stage CV-JD Matching Pipeline

## 📋 Overview

Hệ thống sử dụng pipeline 3 giai đoạn để matching CVs với Job Description (JD):

1. **STAGE 0**: Pre-filtering với Vector Similarity Search
2. **STAGE 1**: Requirements Extraction + CV Data Extraction
3. **STAGE 2**: Deterministic Scoring
4. **STAGE 3**: Advanced Features Generation

---

## 🔄 Full Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          INPUT: 100 CVs + JD Text                       │
└─────────────────────────────────────────────────────────────────────────┘
                                      ↓
╔═════════════════════════════════════════════════════════════════════════╗
║                   STAGE 0: Pre-filter (Vector Search)                   ║
╠═════════════════════════════════════════════════════════════════════════╣
║  Model: text-embedding-3-large                                          ║
║  Process:                                                               ║
║    1. Create JD embedding (1536-D vector)                              ║
║    2. Create 100 CV embeddings (1536-D vectors each)                   ║
║    3. ChromaDB similarity search: JD vs all CVs                        ║
║    4. Sort by cosine similarity                                         ║
║    5. Return top 50 CVs                                                 ║
║  ─────────────────────────────────────────────────────────────────────  ║
║  💾 Cache: cv_embeddings (100 entries) + jd_embeddings (1 entry)       ║
║  💰 Cost: ~$0.013 (if cache MISS)                                       ║
║  ⏱️  Time: ~30-60s (cache MISS) / ~1s (cache HIT)                      ║
╠═════════════════════════════════════════════════════════════════════════╣
║  OUTPUT: 50 CVs (similarity: 0.85-0.92)                                 ║
╚═════════════════════════════════════════════════════════════════════════╝
                                      ↓
╔═════════════════════════════════════════════════════════════════════════╗
║              STAGE 1A: Extract JD Requirements (GPT-4o)                 ║
╠═════════════════════════════════════════════════════════════════════════╣
║  Model: gpt-4o                                                          ║
║  Input: JD text                                                         ║
║  Process:                                                               ║
║    Parse JD → Extract requirements JSON                                ║
║    {                                                                    ║
║      "position": "Senior React Developer",                             ║
║      "must_have_requirements": ["React 3+", "TypeScript", ...],        ║
║      "nice_to_have_requirements": ["GraphQL", "AWS", ...],             ║
║      "experience_years_required": 3                                     ║
║    }                                                                    ║
║  ─────────────────────────────────────────────────────────────────────  ║
║  💾 Cache: ❌ No cache                                                  ║
║  💰 Cost: ~$0.01                                                        ║
║  ⏱️  Time: ~2-5s                                                        ║
╠═════════════════════════════════════════════════════════════════════════╣
║  OUTPUT: Requirements JSON                                              ║
╚═════════════════════════════════════════════════════════════════════════╝
                                      ↓
╔═════════════════════════════════════════════════════════════════════════╗
║           STAGE 1B: Extract CV Data (GPT-4o-mini, Batched)              ║
╠═════════════════════════════════════════════════════════════════════════╣
║  Model: gpt-4o-mini                                                     ║
║  Input: 50 CVs + Requirements JSON                                      ║
║  Process:                                                               ║
║    For each batch of 5 CVs:                                            ║
║      1. Check cache: cv_content_hash + jd_hash                         ║
║      2. If MISS → Call GPT-4o-mini                                     ║
║      3. Parse CV → Match with JD requirements                          ║
║         {                                                              ║
║           "cv_id": "cv_abc",                                           ║
║           "candidate_name": "Nguyen Van A",                            ║
║           "experience_years": 4,                                       ║
║           "skills": ["React", "TypeScript"],                           ║
║           "must_have_matched": [                                       ║
║             {"skill": "React", "matched": true, "note": "4 years"},    ║
║             {"skill": "TypeScript", "matched": true}, ...              ║
║           ],                                                           ║
║           "nice_to_have_matched": [...]                                ║
║         }                                                              ║
║      4. Cache result → cv_extracted_data                               ║
║  ─────────────────────────────────────────────────────────────────────  ║
║  💾 Cache: cv_extracted_data (key: cv_hash + jd_hash)                  ║
║  💰 Cost: $0 (cache HIT) / ~$2-3 (cache MISS for 50 CVs)               ║
║  ⏱️  Time: ~1s (cache HIT) / ~60-120s (cache MISS)                     ║
╠═════════════════════════════════════════════════════════════════════════╣
║  OUTPUT: 50 CV JSONs with matched requirements                          ║
╚═════════════════════════════════════════════════════════════════════════╝
                                      ↓
╔═════════════════════════════════════════════════════════════════════════╗
║            STAGE 2: Deterministic Scoring (Pure Python)                 ║
╠═════════════════════════════════════════════════════════════════════════╣
║  Model: ❌ No AI (Python logic only)                                    ║
║  Input: 50 CV JSONs from Stage 1B                                       ║
║  Process:                                                               ║
║    For each CV:                                                         ║
║      must_have_percentage = matched / total                            ║
║      base_score = must_have_percentage × 90                            ║
║      nice_to_have_bonus = (matched / total) × 10                       ║
║      total_score = base_score + nice_to_have_bonus                     ║
║      Apply penalties for missing must-haves                            ║
║    Sort by score (descending)                                           ║
║    Filter CVs with score = 0                                            ║
║  ─────────────────────────────────────────────────────────────────────  ║
║  💾 Cache: ❌ No cache needed                                           ║
║  💰 Cost: FREE                                                          ║
║  ⏱️  Time: < 0.1s                                                       ║
╠═════════════════════════════════════════════════════════════════════════╣
║  OUTPUT: 48 CVs sorted by score (2 filtered out)                        ║
║          CV 1: 97.5, CV 2: 92.0, CV 3: 88.5, ..., CV 48: 15.0          ║
╚═════════════════════════════════════════════════════════════════════════╝
                                      ↓
╔═════════════════════════════════════════════════════════════════════════╗
║      STAGE 3: Advanced Features (GPT-4o-mini, Batched Per-CV)           ║
╠═════════════════════════════════════════════════════════════════════════╣
║  Model: gpt-4o-mini (max_tokens=6000, temperature=0.1)                  ║
║  Input: Top 5 CVs (max_cv_count) + JD + Requirements + Options          ║
║  Batch Size: 1 CV per batch (STAGE3_BATCH_SIZE = 1)                     ║
║  Process:                                                               ║
║    For each of top 5 CVs (in batches of 1):                            ║
║      1. Check cache: jd_hash + cv_id + options_hash                    ║
║      2. If MISS → Call GPT to generate:                                ║
║         - cv_presentation_comment (OBJECT):                            ║
║           {                                                            ║
║             "structure": "Layout/sections analysis",                  ║
║             "strengths": ["Point 1", "Point 2", "Point 3"],           ║
║             "issues": ["Issue 1", "Issue 2", "Issue 3"],              ║
║             "highlights": "Notable projects/achievements",            ║
║             "suggestions": ["Action 1", "Action 2", "Action 3"]       ║
║           }                                                            ║
║         - interview_questions (5 strategic questions)                  ║
║         - job_leveling (array: ["Junior", "Mid"])                     ║
║         - job_leveling_reason (string: 30-50 words)                   ║
║         - cert_comment (certification analysis)                        ║
║      3. Extract JSON using find/rfind to handle multiple ``` markers  ║
║      4. Cache result → advanced_features                              ║
║  ─────────────────────────────────────────────────────────────────────  ║
║  💾 Cache: advanced_features (key: jd_hash + cv_id + options_hash)     ║
║  💰 Cost: $0 (cache HIT) / ~$1-2 (cache MISS for 5 CVs)                ║
║  ⏱️  Time: ~1s (cache HIT) / ~15-25s (cache MISS, 5 batches × 3-5s)   ║
║  🔧 Why Batch=1: Complex nested JSON structure + max_tokens limit      ║
╠═════════════════════════════════════════════════════════════════════════╣
║  OUTPUT: Top 5 CVs with advanced features                               ║
║          {                                                              ║
║            "cv_id": "cv_abc",                                           ║
║            "candidate_name": "Nguyen Van A",                            ║
║            "score": 97.5,                                               ║
║            "cv_presentation_comment": {                                ║
║              "structure": "Chronological, 4 sections, clear",          ║
║              "strengths": ["Metrics in projects", "Categorized skills"],║
║              "issues": ["Too long experience section"],                ║
║              "highlights": "Real-time Chat App with 10K users",        ║
║              "suggestions": ["Add summary", "Shorten old projects"]    ║
║            },                                                           ║
║            "interview_questions": ["Q1", "Q2", "Q3", "Q4", "Q5"],     ║
║            "job_leveling": ["Junior", "Mid"],                          ║
║            "job_leveling_reason": "2 years exp. Strong React/TS...",  ║
║            "cert_comment": "Suggest AWS Certified Developer..."        ║
║          }                                                              ║
╚═════════════════════════════════════════════════════════════════════════╝
                                      ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                    FINAL RESPONSE: Top 5 CVs                            │
│                                                                         │
│  💰 Total Cost (cache MISS): ~$3-5                                      │
│  💰 Total Cost (cache HIT): ~$0.01                                      │
│  ⏱️  Total Time (cache MISS): ~100-200s (1.5-3.5 minutes)              │
│  ⏱️  Total Time (cache HIT): ~3-5s                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📍 STAGE 0: Pre-filter (Vector Search)

### **Mục đích**
- Giảm số lượng CVs cần xử lý chi tiết (từ 100 → 50)
- Sử dụng semantic similarity để lọc CVs liên quan nhất
- Cache embeddings để tái sử dụng

### **Input**
- `cv_data_list`: List of CV objects (text content)
- `jd_text`: Job Description text
- `top_n`: Number of top CVs to return (default: 50)

### **Process**

#### 1. **Tạo JD Embedding**
```python
# Call OpenAI text-embedding-3-large
jd_embedding = vector_db.get_or_create_jd_embedding(jd_text)

# Output: [0.123, -0.456, 0.789, ..., 0.234]  # 1536 dimensions
```

**Cache Strategy:**
- **Collection**: `jd_embeddings`
- **Cache Key**: `jd_content_hash` (MD5 of JD text)
- **Doc ID**: `jd_{hash[:16]}`
- **Stored**: Embedding vector (1536-D)

#### 2. **Tạo CV Embeddings** (for ALL CVs)
```python
# QUAN TRỌNG: Luôn tạo embeddings cho TẤT CẢ CVs (100 CVs)
# Để cache cho lần sau, không phụ thuộc vào filtering
for cv in cv_data_list:  # 100 CVs
    vector_db.cache_cv_embedding(cv['file_id'], cv['content'])
```

**Cache Strategy:**
- **Collection**: `cv_embeddings`
- **Cache Key**: `cv_content_hash` (MD5 of CV text)
- **Doc ID**: `cv_{hash[:16]}`
- **Stored**: Embedding vector (1536-D)
- **Metadata**: `file_id`, `filename`, `content_hash`

#### 3. **Vector Similarity Search**
```python
# ChromaDB query
results = collection.query(
    query_embeddings=[jd_embedding],  # JD vector
    n_results=top_n,                   # 50
    include=["metadatas", "distances"]
)

# Calculate similarity from distance
for distance in results['distances'][0]:
    similarity = 1 - distance  # Cosine similarity (0-1)
```

**Similarity Score:**
- `1.0` = 100% similar (identical)
- `0.8` = 80% similar (highly relevant)
- `0.5` = 50% similar (somewhat relevant)
- `0.0` = 0% similar (completely different)

#### 4. **Filter Logic**
```python
PRE_FILTER_THRESHOLD = 50

if len(cv_data_list) > PRE_FILTER_THRESHOLD:
    # Filter to top 50
    top_n = PRE_FILTER_TOP_N  # 50
else:
    # Keep all CVs (no filtering)
    top_n = len(cv_data_list)  # e.g., 41
```

### **Output**
- **Top N CVs** (sorted by similarity)
- Example: 50 CVs with similarity scores 0.85-0.92

### **Cost**
| Item | Model | Cost per call | Total (100 CVs) |
|------|-------|---------------|-----------------|
| JD embedding | text-embedding-3-large | ~$0.00013 | $0.00013 |
| CV embeddings (100) | text-embedding-3-large | ~$0.00013 each | $0.013 |
| **TOTAL** | | | **~$0.013** |

### **Cache Benefits**
- **Cache HIT (JD)**: $0 (no OpenAI call)
- **Cache HIT (CV)**: $0 per CV
- **Reuse**: JD embeddings reusable across sessions, CV embeddings reusable with different JDs

---

## 📍 STAGE 1A: JD Requirements Extraction

### **Mục đích**
- Extract structured requirements từ JD text
- Phân loại: must-have vs nice-to-have
- Cung cấp context cho CV matching

### **Input**
- `jd_text`: Job Description text
- `response_requirement`: User's request/question (optional)

### **Process**

#### **Call GPT-4o**
```python
# Prompt: prompts.get_extraction_prompt(jd_text, response_requirement)
response = client.chat.completions.create(
    model="gpt-4o",  # High accuracy model
    messages=[
        {"role": "system", "content": "Bạn là chuyên gia phân tích JD..."},
        {"role": "user", "content": extraction_prompt}
    ],
    temperature=0,  # Deterministic
    max_tokens=6000
)
```

**Prompt Structure:**
```
Phân tích Job Description sau và trích xuất:
1. Vị trí tuyển dụng
2. Must-have requirements (bắt buộc)
3. Nice-to-have requirements (ưu tiên)
4. Yêu cầu về kinh nghiệm (số năm)

JD Text: {jd_text}

Trả về JSON:
{
  "position": "Senior React Developer",
  "must_have_requirements": ["React 3+ years", "TypeScript", ...],
  "nice_to_have_requirements": ["GraphQL", "AWS", ...],
  "experience_years_required": 3
}
```

### **Output Example**
```json
{
  "position": "Senior React Developer",
  "must_have_requirements": [
    "React 3+ years",
    "TypeScript",
    "RESTful API",
    "Git"
  ],
  "nice_to_have_requirements": [
    "GraphQL",
    "AWS/GCP",
    "CI/CD",
    "Agile/Scrum"
  ],
  "experience_years_required": 3,
  "additional_context": "Ưu tiên ứng viên có kinh nghiệm fintech"
}
```

### **Cache Strategy**
- ❌ **KHÔNG cache** (mỗi request có thể có response_requirement khác nhau)
- ⏱️ **Processing time**: ~2-5s

### **Cost**
| Item | Model | Tokens | Cost |
|------|-------|--------|------|
| JD extraction | gpt-4o | ~500 input + 200 output | ~$0.01 |

---

## 📍 STAGE 1B: CV Data Extraction

### **Mục đích**
- Extract structured data từ CV text
- Match CV skills/experience với JD requirements
- Đánh giá matched vs missing requirements

### **Input**
- `cv_data_list`: Top 50 CVs (from Stage 0)
- `requirements`: Requirements JSON (from Stage 1A)
- `jd_hash`: MD5 hash of JD text

### **Process**

#### 1. **Batch Processing**
```python
BATCH_SIZE = 5  # Process 5 CVs per API call

# Split 50 CVs into 10 batches
batches = [cv_data_list[i:i+BATCH_SIZE] for i in range(0, len(cv_data_list), BATCH_SIZE)]
```

#### 2. **Cache Check (Per CV)**
```python
for cv in batch:
    cv_content_hash = hashlib.md5(cv['content'].encode()).hexdigest()
    doc_id = f"cv_{cv_content_hash[:16]}_{jd_hash[:16]}"
    
    cached_data = vector_db.get_cached_extracted_cv_data(
        cv['file_id'], 
        cv['content'], 
        jd_hash
    )
    
    if cached_data:
        # Cache HIT → Skip OpenAI call
        batch_cached_cvs.append(cached_data)
    else:
        # Cache MISS → Need to call OpenAI
        batch_uncached_cvs.append(cv)
```

**Cache Strategy:**
- **Collection**: `cv_extracted_data`
- **Cache Key**: `cv_content_hash + jd_content_hash`
- **Doc ID**: `cv_{cv_hash[:16]}_{jd_hash[:16]}`
- **Stored**: Extracted JSON (as string)
- **Metadata**: `file_id`, `content_hash`, `jd_hash`, `extracted_at`

⚠️ **QUAN TRỌNG**: Cache phụ thuộc cả CV và JD
- JD thay đổi → `jd_hash` mới → Cache MISS → Phải extract lại!

#### 3. **Call GPT-4o-mini** (for uncached CVs only)
```python
# Prompt: prompts.get_cv_extraction_prompt(cv_contents, requirements)
response = client.chat.completions.create(
    model="gpt-4o-mini",  # Cost-effective model
    messages=[
        {"role": "system", "content": "Bạn là chuyên gia phân tích CV..."},
        {"role": "user", "content": cv_extraction_prompt}
    ],
    temperature=0,
    max_tokens=6000
)
```

**Prompt Structure:**
```
Phân tích CVs sau và đối chiếu với JD requirements:

Must-have: ["React 3+ years", "TypeScript", ...]
Nice-to-have: ["GraphQL", "AWS", ...]

CV 1:
{cv_content_1}

CV 2:
{cv_content_2}

...

Trả về JSON array:
[
  {
    "cv_id": "cv_xxx",
    "candidate_name": "Nguyen Van A",
    "email": "nguyenvana@example.com",
    "phone": "+84 123 456 789",
    "position": "Senior Frontend Developer",
    "experience_years": 4,
    "skills": ["React", "TypeScript", "GraphQL"],
    "education": {
      "degree": "Bachelor of Computer Science",
      "university": "HCMUT",
      "graduation_year": 2019
    },
    "must_have_matched": [
      {"skill": "React", "matched": true, "note": "4 years experience"},
      {"skill": "TypeScript", "matched": true, "note": "Used in 3 projects"},
      {"skill": "RESTful API", "matched": true, "note": "Extensive experience"},
      {"skill": "Git", "matched": true, "note": "GitHub profile active"}
    ],
    "nice_to_have_matched": [
      {"skill": "GraphQL", "matched": true, "note": "Used in Apollo Client"},
      {"skill": "AWS/GCP", "matched": false, "note": "No cloud experience mentioned"},
      {"skill": "CI/CD", "matched": true, "note": "Jenkins, GitHub Actions"},
      {"skill": "Agile/Scrum", "matched": true, "note": "3 years in Scrum teams"}
    ]
  },
  ...
]
```

#### 4. **Cache Results**
```python
for cv_data in batch_cv_data:
    cv_original = next((cv for cv in batch_uncached_cvs if cv['cv_id'] == cv_data['cv_id']), None)
    if cv_original:
        vector_db.cache_extracted_cv_data(
            cv_original['file_id'],
            cv_original['content'],
            jd_hash,
            cv_data  # Extracted JSON
        )
```

### **Output Example**
```json
{
  "cv_id": "cv_abc123",
  "candidate_name": "Nguyen Van A",
  "experience_years": 4,
  "must_have_matched": [
    {"skill": "React", "matched": true, "note": "4 years"},
    {"skill": "TypeScript", "matched": true, "note": "3 projects"},
    {"skill": "RESTful API", "matched": true, "note": "Extensive"},
    {"skill": "Git", "matched": true, "note": "Active GitHub"}
  ],
  "nice_to_have_matched": [
    {"skill": "GraphQL", "matched": true, "note": "Apollo Client"},
    {"skill": "AWS/GCP", "matched": false, "note": "No mention"},
    {"skill": "CI/CD", "matched": true, "note": "Jenkins"},
    {"skill": "Agile/Scrum", "matched": true, "note": "3 years"}
  ]
}
```

### **Cache Statistics Example**
```
📊 CV EXTRACTION CACHE STATISTICS:
   Cache Hits: 35/50 (70.0%)
   Cache Misses: 15/50
   💰 Saved: ~17,500 tokens (estimated)
```

### **Cost**
| Scenario | CVs to extract | Model | Cost |
|----------|----------------|-------|------|
| Cache MISS (all 50) | 50 CVs | gpt-4o-mini | ~$2-3 |
| Cache HIT (all 50) | 0 CVs | - | $0 |
| Partial (30 hit, 20 miss) | 20 CVs | gpt-4o-mini | ~$0.8-1.2 |

---

## 📍 STAGE 2: Deterministic Scoring

### **Mục đích**
- Tính điểm cho từng CV dựa trên matched requirements
- Sắp xếp CVs theo score (cao → thấp)
- Filter CVs có score = 0

### **Input**
- `extracted_cvs`: List of 50 CV JSONs (from Stage 1B)
- `requirements`: Requirements JSON (from Stage 1A)
- `advanced_options`: User preferences

### **Process**

#### **Scoring Logic** (Pure Python - NO AI calls)

```python
class CVScoringEngine:
    def calculate_score(self, cv_data: dict) -> dict:
        # 1. Count matched requirements
        must_have_matched = [m for m in cv_data['must_have_matched'] if m['matched']]
        must_have_missing = [m for m in cv_data['must_have_matched'] if not m['matched']]
        nice_to_have_matched = [m for m in cv_data['nice_to_have_matched'] if m['matched']]
        
        # 2. Calculate must-have percentage
        if must_have_count > 0:
            must_have_percentage = len(must_have_matched) / must_have_count
        else:
            must_have_percentage = 1.0
        
        # 3. Base score (0-90 points)
        base_score = must_have_percentage * 90
        
        # 4. Nice-to-have bonus (0-10 points)
        if nice_to_have_count > 0:
            nice_to_have_bonus = (len(nice_to_have_matched) / nice_to_have_count) * 10
        else:
            nice_to_have_bonus = 0
        
        # 5. Total score
        total_score = min(100, base_score + nice_to_have_bonus)
        
        # 6. Apply penalties for missing must-haves
        missing_count = len(must_have_missing)
        if missing_count == 1:
            total_score = min(total_score, 85)  # Max 85 if missing 1
        elif missing_count == 2:
            total_score = min(total_score, 70)  # Max 70 if missing 2
        elif missing_count >= 3:
            total_score = min(total_score, 60)  # Max 60 if missing 3+
        
        return {
            "score": round(total_score, 1),
            "matched_requirements": [...],
            "missing_requirements": [...]
        }
```

#### **Scoring Examples**

| Must-have (4 total) | Nice-to-have (4 total) | Base Score | Bonus | Penalty | **Final Score** |
|---------------------|------------------------|------------|-------|---------|-----------------|
| 4/4 matched (100%) | 3/4 matched (75%) | 90.0 | 7.5 | None | **97.5** |
| 4/4 matched (100%) | 0/4 matched (0%) | 90.0 | 0.0 | None | **90.0** |
| 3/4 matched (75%) | 4/4 matched (100%) | 67.5 | 10.0 | -1 missing → max 85 | **77.5** |
| 2/4 matched (50%) | 4/4 matched (100%) | 45.0 | 10.0 | -2 missing → max 70 | **55.0** |
| 1/4 matched (25%) | 4/4 matched (100%) | 22.5 | 10.0 | -3 missing → max 60 | **32.5** |
| 0/4 matched (0%) | 4/4 matched (100%) | 0.0 | 10.0 | -4 missing → max 60 | **10.0** |

#### **Filter CVs with Score = 0**
```python
cv_list = [cv for cv in cv_list if cv.get('score', 0) > 0]
```

#### **Sort by Score**
```python
cv_list.sort(key=lambda x: x.get('score', 0), reverse=True)
```

### **Output**
- **Sorted list** of CVs with scores
- Example: 48 CVs (2 filtered out with score = 0)

### **Cache Strategy**
- ❌ **KHÔNG cache** (tính toán nhanh, không cần cache)

### **Cost**
- ✅ **FREE** (no AI calls, pure Python logic)
- ⏱️ **Processing time**: < 0.1s

---

## 📍 STAGE 3: Advanced Features Generation

### **Mục đích**
- Generate advanced features cho top N CVs (based on `max_cv_count`)
- Interview questions tailored cho từng CV
- CV presentation comments
- Certification benefits analysis
- Rank assessment

### **Input**
- `cv_list`: Sorted CVs (from Stage 2)
- `max_cv_count`: Number of CVs to return (e.g., 5)
- `jd_text`: Job Description text
- `requirements`: Requirements JSON
- `advanced_options`: User preferences
  - `interviewQuestions`: true/false
  - `cvPresentation`: true/false
  - `certBenefit`: true/false
  - `jobLeveling`: true/false

### **Process**

#### 1. **Select Top N CVs**
```python
top_cvs = cv_list[:max_cv_count]  # e.g., top 5 CVs
```

#### 2. **Cache Check (Per CV)**
```python
options_str = json.dumps(advanced_options, sort_keys=True)
options_hash = hashlib.md5(options_str.encode()).hexdigest()

for cv in top_cvs:
    doc_id = f"advanced_{jd_hash[:16]}_{cv_id}_{options_hash[:8]}"
    
    result = collection.get(ids=[doc_id], include=["documents"])
    
    if result['ids']:
        # Cache HIT
        cached_cvs.append(json.loads(result['documents'][0]))
    else:
        # Cache MISS
        uncached_cvs.append(cv)
```

**Cache Strategy:**
- **Collection**: `advanced_features`
- **Cache Key**: `jd_hash + cv_id + options_hash`
- **Doc ID**: `advanced_{jd_hash[:16]}_{cv_id}_{options_hash[:8]}`
- **Stored**: Advanced features JSON (as string)
- **Metadata**: `jd_hash`, `cv_id`, `options_hash`, `generated_at`

⚠️ **QUAN TRỌNG**: Cache phụ thuộc JD, CV, VÀ advanced_options
- JD thay đổi → Cache MISS
- CV thay đổi → Cache MISS
- Options thay đổi → Cache MISS

#### 3. **Call GPT-4o-mini** (for uncached CVs only)
```python
# Prompt: prompts.get_stage3_advanced_prompt(...)
response = client.chat.completions.create(
    model="gpt-4o-mini",  # or "gpt-4o" for higher quality
    messages=[
        {"role": "system", "content": "Bạn là chuyên gia tuyển dụng AI..."},
        {"role": "user", "content": advanced_prompt}
    ],
    temperature=0,
    max_tokens=6000
)
```

**Prompt Structure (if all options enabled):**
```
Tạo advanced features cho CVs sau:

JD: {jd_text}
Requirements: {requirements}

CV 1: Nguyen Van A
- Skills: React, TypeScript, GraphQL
- Experience: 4 years
- Must-have matched: 4/4
- Nice-to-have matched: 3/4
...

Options enabled:
- Interview Questions: true
- CV Presentation: true
- Cert Benefit: true
- Rank assessment: true
- Detect Duplicate: true

Trả về JSON array:
[
  {
    "cv_id": "cv_abc123",
    "interview_questions": [
      "Describe your experience with React Hooks and custom hooks.",
      "How do you handle state management in large React applications?",
      "Explain a challenging bug you encountered with TypeScript and how you fixed it."
    ],
    "cv_presentation_comment": "Ứng viên có profile mạnh với 4 năm kinh nghiệm React và TypeScript. Đáp ứng đầy đủ must-have requirements. Điểm nổi bật là kinh nghiệm với GraphQL và CI/CD. Thiếu kinh nghiệm cloud (AWS/GCP) nhưng không quan trọng.",
    "cert_comment": "Ứng viên chưa có certification về React hoặc AWS. Đề xuất: AWS Certified Developer Associate sẽ bổ sung kiến thức cloud, tăng giá trị profile lên 15-20%.",
    "job_leveling": [
      "Fresher",
      "Junior",
      "Middle",
      "Senior"
    ],
    "duplicate_warning": null
  },
  ...
]
```

#### 4. **Cache Results** (Per CV)
```python
vector_db.cache_advanced_features(
    jd_hash,
    uncached_cv_ids,
    advanced_options,
    newly_generated  # List of advanced JSONs
)
```

#### 5. **Merge with CV List**
```python
for cv_item in cv_list:
    cv_id = cv_item['cv_id']
    if cv_id in advanced_dict:
        advanced_item = advanced_dict[cv_id]
        
        if advanced_options.get("interviewQuestions"):
            cv_item["interview_questions"] = advanced_item["interview_questions"]
        
        if advanced_options.get("cvPresentation"):
            cv_item["cv_presentation_comment"] = advanced_item["cv_presentation_comment"]
        
        # ... merge other fields
```

### **Output Example**
```json
{
  "cv_id": "cv_abc123",
  "candidate_name": "Nguyen Van A",
  "score": 97.5,
  "interview_questions": [
    "Describe your experience with React Hooks...",
    "How do you handle state management...",
    "Explain a challenging TypeScript bug..."
  ],
  "cv_presentation_comment": "Ứng viên có profile mạnh với 4 năm kinh nghiệm...",
  "cert_comment": "Ứng viên chưa có certification về React hoặc AWS...",
  "job_leveling": [
      "Fresher",
      "Junior",
      "Middle",
      "Senior"
    ],
  "duplicate_warning": null
}
```

### **Cache Statistics Example**
```
Cache status: 3 hits, 2 misses
🔄 Generating advanced features for 2 uncached CVs...
✓ Cached Stage 3 advanced features for 2 newly generated CVs
Total advanced data: 3 cached + 2 new = 5 CVs
```

### **Cost**
| Scenario | CVs to generate | Model | Cost |
|----------|-----------------|-------|------|
| Cache MISS (all 5) | 5 CVs | gpt-4o-mini | ~$1-2 |
| Cache HIT (all 5) | 0 CVs | - | $0 |
| Partial (3 hit, 2 miss) | 2 CVs | gpt-4o-mini | ~$0.4-0.8 |

---

## 📊 Total Cost Analysis

### **Scenario 1: First Request (All Cache MISS)**
| Stage | Activity | Model | Cost |
|-------|----------|-------|------|
| 0 | JD embedding (1) | text-embedding-3-large | $0.0001 |
| 0 | CV embeddings (100) | text-embedding-3-large | $0.013 |
| 1A | JD extraction | gpt-4o | $0.01 |
| 1B | CV extraction (50) | gpt-4o-mini | $2-3 |
| 2 | Scoring | Python | $0 |
| 3 | Advanced (5) | gpt-4o-mini | $1-2 |
| **TOTAL** | | | **~$3-5** |

### **Scenario 2: Second Request (Same JD, Same CVs)**
| Stage | Activity | Model | Cost |
|-------|----------|-------|------|
| 0 | JD embedding (cache HIT) | - | $0 |
| 0 | CV embeddings (cache HIT) | - | $0 |
| 1A | JD extraction | gpt-4o | $0.01 |
| 1B | CV extraction (cache HIT) | - | $0 |
| 2 | Scoring | Python | $0 |
| 3 | Advanced (cache HIT) | - | $0 |
| **TOTAL** | | | **~$0.01** |

**Savings: 99.7%!** 🎉

### **Scenario 3: Different JD, Same CVs**
| Stage | Activity | Model | Cost |
|-------|----------|-------|------|
| 0 | JD embedding (new) | text-embedding-3-large | $0.0001 |
| 0 | CV embeddings (cache HIT) | - | $0 |
| 1A | JD extraction | gpt-4o | $0.01 |
| 1B | CV extraction (MISS - jd_hash changed!) | gpt-4o-mini | $2-3 |
| 2 | Scoring | Python | $0 |
| 3 | Advanced (MISS - jd_hash changed!) | gpt-4o-mini | $1-2 |
| **TOTAL** | | | **~$3-5** |

⚠️ **Problem**: CV extraction cache phụ thuộc `jd_hash` → JD thay đổi → Cache MISS!

---

## ⚠️ Known Issues & Limitations

### **Issue 1: cv_extracted_data Cache Key includes JD Hash**

**Problem:**
```python
doc_id = f"cv_{cv_hash[:16]}_{jd_hash[:16]}"
```

- JD thay đổi từ "2+ years" → "3+ years"
- `jd_hash` thay đổi
- **Cache MISS** cho tất cả 50 CVs
- Phải extract lại → Tốn $2-3

**Trade-offs:**

| Option | Pros | Cons |
|--------|------|------|
| **Keep jd_hash** (current) | ✅ Extraction chính xác cho từng JD<br>✅ Must-have matching theo JD cụ thể | ❌ Tốn token khi đổi JD<br>❌ Cache kém hiệu quả |
| **Remove jd_hash** | ✅ Tiết kiệm token (cache cross-JD)<br>✅ Faster response | ❌ Extraction generic<br>❌ Matching kém chính xác |

**Current decision**: Keep jd_hash for accuracy

### **Issue 2: advanced_features Cache Key includes Options**

**Problem:**
```python
doc_id = f"advanced_{jd_hash[:16]}_{cv_id}_{options_hash[:8]}"
```

- User toggle `interviewQuestions`: false → true
- `options_hash` thay đổi
- **Cache MISS** cho tất cả 5 CVs

**Workaround**: Encourage users to decide options upfront

### **Issue 3: Stage 3 Batch Size Optimization**

**Evolution:**
```python
# V1: Multiple CVs per batch (faster but risky)
STAGE3_BATCH_SIZE = 5  # ⚠️ JSON truncation risk

# V2: Reduced for complex prompts
STAGE3_BATCH_SIZE = 2  # Still truncating

# V3: Current - 1 CV per batch (stable)
STAGE3_BATCH_SIZE = 1  # ✅ No truncation
```

**Problem:** 
Complex nested JSON structure (cv_presentation_comment object with 5 fields) + lengthy prompts caused GPT to truncate responses even with max_tokens=16000.

**Solution:**
1. Reduced batch size from 5 → 1 CV per batch
2. Optimized prompts (removed verbose examples, shortened requirements)
3. max_tokens=6000 (sufficient for 1 CV)
4. JSON extraction using find()/rfind() instead of split() to handle multiple ``` markers

**Trade-offs:**
- ✅ Pros: Stable JSON parsing, complete responses
- ❌ Cons: 5x more API calls (5 CVs = 5 batches), slower by ~10-15s

### **Issue 4: Prompt Size Optimization**

**Problem:**
```python
# OLD: Verbose prompts (~2000 tokens)
- cv_presentation_comment: "Phân tích CHUYÊN SÂU về CV (100-150 từ)..."
- GOOD EXAMPLE: 300+ words of examples
- job_leveling_reason: "50-80 từ" with detailed rubrics
```

**Solution:**
```python
# NEW: Concise prompts (~800 tokens, 60% reduction)
- cv_presentation_comment: "OBJECT - mỗi field 1-2 câu" (no examples)
- PHƯƠNG PHÁP: 4 steps instead of 15 lines
- job_leveling_reason: "2-3 câu (30-50 từ)"
```

**Result:**
- More tokens for output (6000 now sufficient vs 16000 before)
- Faster responses (less input processing)
- Quality maintained (instructions still clear)

### **Issue 5: Pre-filter Threshold Fixed at 50**

**Problem:**
```python
PRE_FILTER_THRESHOLD = 50
```

- < 50 CVs: No filtering (process all)
- > 50 CVs: Filter to top 50

**Limitation**: Không dynamic based on JD complexity hoặc user requirements

---

## 🚀 Performance Metrics

### **Processing Time** (41 CVs, Cache MISS)
| Stage | Time | Notes |
|-------|------|-------|
| Stage 0 | ~30-60s | CV embeddings (41 calls) |
| Stage 1A | ~2-5s | JD extraction (1 call) |
| Stage 1B | ~60-120s | CV extraction (8-9 batches × 5 CVs) |
| Stage 2 | < 0.1s | Pure Python |
| Stage 3 | ~15-25s | Advanced features (5 batches × 1 CV, 3-5s each) |
| **TOTAL** | **~110-215s** | **1.8-3.6 minutes** |

### **Processing Time** (41 CVs, Cache HIT)
| Stage | Time | Notes |
|-------|------|-------|
| Stage 0 | ~1s | Cache lookup |
| Stage 1A | ~2-5s | JD extraction (1 call) |
| Stage 1B | ~1s | Cache lookup |
| Stage 2 | < 0.1s | Pure Python |
| Stage 3 | ~1s | Cache lookup |
| **TOTAL** | **~3-5s** | **97% faster!** |

---

## 📝 Code References

| Stage | File | Function/Class | Lines |
|-------|------|----------------|-------|
| Stage 0 | `routers/thinking.py` | `pre_filter_cvs_by_similarity()` | 294-387 |
| Stage 0 | `db/vector_db.py` | `get_or_create_jd_embedding()` | 165-200 |
| Stage 0 | `db/vector_db.py` | `cache_cv_embedding()` | 93-130 |
| Stage 1A | `routers/thinking.py` | JD extraction logic | 663-705 |
| Stage 1A | `prompts.py` | `get_extraction_prompt()` | 70-98 |
| Stage 1B | `routers/thinking.py` | CV extraction batching | 707-870 |
| Stage 1B | `prompts.py` | `get_cv_extraction_prompt()` | 100-145 |
| Stage 1B | `db/vector_db.py` | `cache_extracted_cv_data()` | 275-310 |
| Stage 1B | `db/vector_db.py` | `get_cached_extracted_cv_data()` | 313-360 |
| Stage 2 | `routers/thinking.py` | `CVScoringEngine` class | 40-285 |
| Stage 3 | `routers/thinking.py` | Advanced features logic | 980-1100 |
| Stage 3 | `prompts.py` | `get_stage3_advanced_prompt()` | 200-350 |
| Stage 3 | `db/vector_db.py` | `cache_advanced_features()` | 363-420 |

---

## 🎓 Best Practices

### **For Users**

1. **Minimize JD changes**: Reuse JD text để maximize cache hit rate
2. **Decide options upfront**: Tránh toggle advanced_options nhiều lần
3. **Upload CVs in batches**: Embeddings cache cross-JD, upload nhiều CVs 1 lần
4. **Reuse JDs**: Same JD + same CVs → 99% cost savings

### **For Developers**

1. **Monitor cache hit rates**: Log cache statistics để optimize
2. **Adjust batch size**: 
   - Stage 1B: BATCH_SIZE = 5 optimal cho GPT-4o-mini
   - Stage 3: STAGE3_BATCH_SIZE = 1 for complex JSON structures
3. **Handle rate limits**: Implement exponential backoff retry
4. **Validate JSON parsing**: Always handle `json.JSONDecodeError`
5. **Test cache invalidation**: Ensure cache keys correctly reflect dependencies
6. **Optimize prompts**: Keep prompts concise (~800 tokens) to maximize output tokens
7. **JSON extraction**: Use find()/rfind() instead of split() for robustness

---

## 🔧 Configuration

### **Environment Variables**
```python
OPENAI_MODEL = "gpt-4o"  # High accuracy for JD extraction
OPENAI_MINI_MODEL = "gpt-4o-mini"  # Cost-effective for CV extraction
BATCH_SIZE = 5  # CVs per API call (Stage 1B)
STAGE3_BATCH_SIZE = 1  # CVs per API call (Stage 3 - reduced for complex JSON)
PRE_FILTER_THRESHOLD = 50  # When to apply vector filtering
PRE_FILTER_TOP_N = 50  # Number of CVs to keep after filtering

# Stage 3 GPT settings
STAGE3_MAX_TOKENS = 6000  # Sufficient for 1 CV with complex structure
STAGE3_TEMPERATURE = 0.1  # Slight creativity for better JSON completion
```

### **Cache Collections**
```python
CV_COLLECTION_NAME = "cv_embeddings"  # CV vectors
JD_COLLECTION_NAME = "jd_embeddings"  # JD vectors
CV_EXTRACTED_DATA_COLLECTION = "cv_extracted_data"  # Extracted CV JSONs
ADVANCED_FEATURES_COLLECTION = "advanced_features"  # Advanced features JSONs
```

---

## 📚 Related Documentation

- [VECTOR_DB_GUIDE.md](./VECTOR_DB_GUIDE.md) - ChromaDB setup and operations
- [CHROMADB_VS_FAISS.md](./CHROMADB_VS_FAISS.md) - Why ChromaDB was chosen
- [JD_CACHE_STRATEGY.md](./JD_CACHE_STRATEGY.md) - JD caching optimization
- [VECTOR_CACHE_README.md](./VECTOR_CACHE_README.md) - Cache invalidation strategies
