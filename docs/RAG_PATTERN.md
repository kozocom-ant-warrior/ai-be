# RAG Pattern Analysis - AI-BE Project

## 📚 Overview

This document explains how the **RAG (Retrieval-Augmented Generation)** pattern is implemented in the AI-BE CV-JD matching system.

## 🎯 RAG Fundamentals

### **R = Retrieval (Truy xuất / Tìm kiếm)**
Tìm các đoạn tài liệu liên quan nhất với câu hỏi từ "kho tri thức" (VectorDB, search index, DB…).
- **Example**: Embed câu hỏi → search top-k chunks → (có thể) rerank

### **A = Augmented (Tăng cường / Bổ sung ngữ cảnh)**
Lấy kết quả truy xuất được và bơm vào ngữ cảnh cho LLM (context window) + áp rule prompt.
- **Example**: Chọn 3–8 chunks tốt nhất, cắt gọn, ghép thành CONTEXT kèm metadata/citation

### **G = Generation (Sinh / Tạo câu trả lời)**
LLM dùng prompt + CONTEXT để tạo câu trả lời (có thể kèm trích dẫn, JSON format, checklist…).
- **Example**: Trả lời "chính sách hoàn tiền" dựa trên các đoạn policy vừa đưa vào

---

## 🔍 RAG Implementation in AI-BE

### **R - RETRIEVAL: STAGE 0 (Vector Similarity Search)**

**Location**: `routers/thinking.py` - `pre_filter_cvs_by_similarity()`

#### **Process Flow**

```python
# 1. Create JD embedding
jd_embedding = get_embedding(jd_text, cache_type="jd")
# → Output: [0.123, -0.456, 0.789, ..., 0.234]  # 1536-D vector

# 2. Create CV embeddings (for ALL CVs)
for cv in cv_data_list:  # 100 CVs
    cv_embedding = get_embedding(
        cv['content'], 
        cache_id=cv['file_id'], 
        cache_type="cv"
    )
    vector_db.cache_cv_embedding(cv['file_id'], cv['filename'], cv['content'], cv_embedding)

# 3. Similarity search (RETRIEVAL)
similar_cvs = vector_db.search_similar_cvs(
    query_embedding=jd_embedding,
    top_k=50  # Retrieve top-50 most similar CVs
)

# 4. Sort by cosine similarity
# Output: Top 50 CVs with similarity scores 0.85-0.92
```

#### **Technical Details**

| Component | Implementation |
|-----------|---------------|
| **VectorDB** | ChromaDB (persistent storage) |
| **Embedding Model** | text-embedding-3-large (1536 dimensions) |
| **Similarity Metric** | Cosine similarity |
| **Query** | JD text (Job Description) |
| **Documents** | CV full text (not chunked) |
| **Top-K** | 50 CVs (if > 50 total, otherwise all) |
| **Cache** | ✅ Both JD and CV embeddings cached |

#### **Retrieval Strategy**

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

**Similarity Score Interpretation:**
- `1.0` = 100% similar (identical)
- `0.8` = 80% similar (highly relevant)
- `0.5` = 50% similar (somewhat relevant)
- `0.0` = 0% similar (completely different)

#### **Cache Strategy**

**JD Embeddings:**
- **Collection**: `jd_embeddings`
- **Cache Key**: MD5 hash of JD text content
- **Doc ID**: `jd_{content_hash[:16]}`
- **Benefit**: Reuse across multiple searches with same JD

**CV Embeddings:**
- **Collection**: `cv_embeddings`
- **Cache Key**: MD5 hash of CV text content
- **Doc ID**: `cv_{file_id}_{content_hash[:16]}`
- **Benefit**: Reuse across different JDs (cross-JD cache)

---

### **A - AUGMENTATION: STAGE 1B (CV Data Extraction)**

**Location**: `routers/thinking.py` - Stage 1B extraction logic

#### **Process Flow**

```python
# AUGMENTATION: Combine multiple contexts
prompt = prompts.get_cv_extraction_prompt(
    cv_contents=[cv1, cv2, cv3],  # ← CONTEXT 1: Retrieved CVs
    requirements=requirements      # ← CONTEXT 2: JD requirements
)

# Prompt structure:
"""
Analyze the following CVs and match with JD requirements:

Must-have: ["React 3+ years", "TypeScript", ...]  # ← CONTEXT 2
Nice-to-have: ["GraphQL", "AWS", ...]              # ← CONTEXT 2

CV 1:                                               # ← CONTEXT 1
{cv_content_1}

CV 2:                                               # ← CONTEXT 1
{cv_content_2}

Return JSON array with matched requirements...
"""
```

#### **Context Components**

| Context Layer | Source | Purpose |
|---------------|--------|---------|
| **JD Requirements** | Stage 1A extraction | Structure matching criteria |
| **CV Content** | Stage 0 retrieval | Raw candidate information |
| **Prompt Template** | `prompts.py` | Guide LLM behavior |
| **Metadata** | File info | CV identification |

#### **Augmentation Features**

1. **Structured Context**: JSON requirements (not raw JD text)
2. **Batching**: 5-7 CVs per context (balance quality vs cost)
3. **Rich Metadata**: File ID, candidate name, skills extracted
4. **Cache-Aware**: Check cache before augmentation

---

### **A - AUGMENTATION: STAGE 3 (Advanced Features)**

**Location**: `routers/thinking.py` - Stage 3 advanced features logic

#### **Process Flow**

```python
# AUGMENTATION: Multi-layer context
prompt = prompts.get_stage3_advanced_prompt(
    jd_text=jd_text,                    # ← CONTEXT 1: Full JD
    requirements=requirements,          # ← CONTEXT 2: Structured requirements
    cv_data=cv_extracted_data,          # ← CONTEXT 3: Extracted CV (from Stage 1B)
    advanced_options=advanced_options   # ← CONTEXT 4: User preferences
)

# Prompt structure:
"""
Generate advanced analysis for CV:

JD Text:                              # ← CONTEXT 1
{jd_text}

Requirements:                         # ← CONTEXT 2
Must-have: [...]
Nice-to-have: [...]

CV Data:                              # ← CONTEXT 3
Candidate: Nguyen Van A
Skills: [React, TypeScript, ...]
Experience: 4 years
Must-have matched: 4/4
Nice-to-have matched: 3/4

Advanced Options:                     # ← CONTEXT 4
{
  "interviewQuestions": true,
  "cvPresentation": true,
  "jobLeveling": true,
  "certBenefit": true
}

Generate:
- interview_questions (5 strategic questions)
- cv_presentation_comment (structure, strengths, issues, highlights, suggestions)
- job_leveling (["Junior", "Mid", "Senior"])
- cert_comment (certification recommendations)
"""
```

#### **Context Progression**

```
Stage 0 (R):  JD → [Top 50 CVs]
                ↓
Stage 1B (A): JD + Requirements → [Extracted CV Data]
                ↓
Stage 3 (A):  JD + Requirements + Extracted Data + Options → [Rich Context]
                ↓
Stage 3 (G):  Generate advanced features
```

---

### **G - GENERATION: Multiple Stages**

#### **STAGE 1A: Requirements Extraction**

**Model**: gpt-4o  
**Temperature**: 0 (deterministic)  
**Output Format**: JSON

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "Bạn là chuyên gia phân tích JD..."},
        {"role": "user", "content": extraction_prompt}
    ],
    temperature=0,
    max_tokens=6000
)

# Generated output:
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
  "experience_years_required": 3
}
```

**Generation Characteristics:**
- ✅ Structured extraction (not freeform)
- ✅ Deterministic (temperature=0)
- ✅ No retrieval needed (just parse JD)

---

#### **STAGE 1B: CV Data Extraction**

**Model**: gpt-4o-mini  
**Temperature**: 0 (deterministic)  
**Batch Size**: 5-7 CVs per call  
**Output Format**: JSON array

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Bạn là chuyên gia phân tích CV..."},
        {"role": "user", "content": cv_extraction_prompt}
    ],
    temperature=0,
    max_tokens=6000
)

# Generated output (per CV):
{
  "cv_id": "cv_abc123",
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
}
```

**Generation Characteristics:**
- ✅ Batch generation (5-7 CVs at once)
- ✅ Structured matching (per requirement)
- ✅ Rich metadata (notes, evidence)
- ✅ Binary matching (true/false) + explanation

---

#### **STAGE 3: Advanced Features Generation**

**Model**: gpt-4o-mini  
**Temperature**: 0.1 (slightly creative)  
**Batch Size**: 1 CV per call  
**Output Format**: Complex nested JSON

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Bạn là chuyên gia phân tích CV..."},
        {"role": "user", "content": stage3_prompt}
    ],
    temperature=0.1,
    max_tokens=6000
)

# Generated output (per CV):
{
  "cv_id": "cv_abc123",
  "interview_questions": [
    "Describe your experience with React Hooks and how you've used them in production.",
    "How do you handle state management in large React applications?",
    "Explain your approach to TypeScript type safety in complex components.",
    "What's your experience with GraphQL and how did you integrate it with React?",
    "Describe a challenging bug you encountered with TypeScript and how you fixed it."
  ],
  "cv_presentation_comment": {
    "structure": "Chronological format, 4 main sections (Contact, Experience, Skills, Projects), clear headings",
    "strengths": [
      "Quantified achievements (10K users, 30% performance improvement)",
      "Well-categorized technical skills by proficiency level",
      "Detailed project descriptions with tech stack"
    ],
    "issues": [
      "Experience section too lengthy (could condense older roles)",
      "Missing professional summary at the top",
      "Education section lacks GPA or honors"
    ],
    "highlights": "Standout project: Real-time Chat Application with 10K concurrent users using React, WebSocket, and Redis",
    "suggestions": [
      "Add 2-3 sentence professional summary at the top",
      "Shorten experience descriptions for roles older than 3 years",
      "Include links to GitHub profile and portfolio projects"
    ]
  },
  "job_leveling": ["Junior", "Mid"],
  "job_leveling_reason": "4 years of professional experience with strong technical skills (React, TypeScript). Successfully delivered complex projects. However, lacks team leadership or architecture design experience, suggesting Mid-level at most.",
  "cert_comment": "Candidate has no certifications in React or cloud technologies. Recommend: AWS Certified Developer Associate would complement technical skills and increase profile value by 15-20%. React Advanced Patterns certification would demonstrate mastery."
}
```

**Generation Characteristics:**
- ✅ Multi-field generation (5+ fields)
- ✅ Nested objects (cv_presentation_comment)
- ✅ Arrays (interview_questions, job_leveling, strengths, issues)
- ✅ Creative + analytical (temperature=0.1)
- ✅ Contextual recommendations

---

## 📊 Complete RAG Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│  INPUT: JD Text (Job Description) + 100 CVs                              │
└──────────────────────────────────────────────────────────────────────────┘
                                   ↓
╔══════════════════════════════════════════════════════════════════════════╗
║  🔍 R - RETRIEVAL (STAGE 0: Vector Similarity Search)                    ║
╠══════════════════════════════════════════════════════════════════════════╣
║  1. Embed JD text → 1536-D vector (text-embedding-3-large)               ║
║  2. Embed 100 CVs → 100 × 1536-D vectors                                 ║
║  3. Store in ChromaDB (cv_embeddings + jd_embeddings collections)        ║
║  4. Query ChromaDB: similarity search (cosine distance)                  ║
║  5. Sort by similarity score (1.0 = most similar)                        ║
║  6. Return top-50 CVs                                                    ║
║                                                                          ║
║  💾 Cache: CV embeddings (reuse across JDs)                              ║
║          JD embeddings (reuse across searches)                          ║
║  💰 Cost: ~$0.0066 (cache MISS) / $0 (cache HIT)                         ║
║  ⏱️  Time: ~30-60s (MISS) / ~1s (HIT)                                    ║
╚══════════════════════════════════════════════════════════════════════════╝
                                   ↓
                  ┌────────────────────────────────────┐
                  │  RETRIEVED: Top 50 CVs             │
                  │  (similarity: 0.85-0.92)           │
                  └────────────────────────────────────┘
                                   ↓
╔══════════════════════════════════════════════════════════════════════════╗
║  🔧 A - AUGMENTATION (STAGE 1A: JD Requirements Extraction)              ║
╠══════════════════════════════════════════════════════════════════════════╣
║  CONTEXT = JD Text (full)                                                ║
║                                                                          ║
║  Prompt: "Extract must-have and nice-to-have requirements from JD..."   ║
║  Model: gpt-4o (high accuracy)                                           ║
║  Output: Structured requirements JSON                                    ║
║                                                                          ║
║  💰 Cost: ~$0.003                                                        ║
║  ⏱️  Time: ~3-5s                                                         ║
╚══════════════════════════════════════════════════════════════════════════╝
                                   ↓
                  ┌────────────────────────────────────┐
                  │  AUGMENTED: Structured Requirements│
                  │  - Must-have: 7 items              │
                  │  - Nice-to-have: 2 items           │
                  └────────────────────────────────────┘
                                   ↓
╔══════════════════════════════════════════════════════════════════════════╗
║  🔧 A - AUGMENTATION (STAGE 1B: CV Data Extraction)                      ║
╠══════════════════════════════════════════════════════════════════════════╣
║  CONTEXT = JD Requirements (from Stage 1A)                               ║
║          + CV Content (from Retrieval - 50 CVs)                          ║
║          + Prompt template                                               ║
║                                                                          ║
║  Batching: Process 5-7 CVs per API call                                 ║
║  Prompt: "Analyze CVs and match with JD requirements..."                ║
║  Model: gpt-4o-mini (cost-effective)                                     ║
║  Output: Extracted CV data with matched requirements                     ║
║                                                                          ║
║  💾 Cache: cv_extracted_data (key: cv_hash + jd_hash)                    ║
║  💰 Cost: ~$0.012 for 41 CVs (cache MISS) / $0 (HIT)                     ║
║  ⏱️  Time: ~300-350s (MISS) / ~1s (HIT)                                  ║
╚══════════════════════════════════════════════════════════════════════════╝
                                   ↓
                  ┌────────────────────────────────────┐
                  │  AUGMENTED: 50 Extracted CV JSONs  │
                  │  Each with:                        │
                  │  - Matched must-haves (7/7)        │
                  │  - Matched nice-to-haves (2/4)     │
                  │  - Skills, experience, education   │
                  └────────────────────────────────────┘
                                   ↓
╔══════════════════════════════════════════════════════════════════════════╗
║  ⚙️  SCORING (STAGE 2: Deterministic Scoring - No AI)                    ║
╠══════════════════════════════════════════════════════════════════════════╣
║  1. Calculate score per CV: must_have_match × 90 + nice_to_have × 10    ║
║  2. Sort by score (descending)                                           ║
║  3. Filter CVs with score = 0                                            ║
║  4. Return top-5 CVs                                                     ║
║                                                                          ║
║  💰 Cost: FREE (pure Python logic)                                       ║
║  ⏱️  Time: < 0.1s                                                        ║
╚══════════════════════════════════════════════════════════════════════════╝
                                   ↓
                  ┌────────────────────────────────────┐
                  │  SCORED: Top 5 CVs                 │
                  │  - CV 1: 97.5/100                  │
                  │  - CV 2: 92.0/100                  │
                  │  - CV 3: 88.5/100                  │
                  └────────────────────────────────────┘
                                   ↓
╔══════════════════════════════════════════════════════════════════════════╗
║  🔧 A - AUGMENTATION (STAGE 3: Advanced Features)                        ║
╠══════════════════════════════════════════════════════════════════════════╣
║  CONTEXT = JD Text (full)                                                ║
║          + JD Requirements (structured)                                  ║
║          + CV Extracted Data (from Stage 1B)                             ║
║          + Advanced Options (user preferences)                           ║
║                                                                          ║
║  Batching: 1 CV per API call (complex nested JSON)                      ║
║  Prompt: "Generate interview questions, presentation analysis..."       ║
║  Model: gpt-4o-mini (temperature=0.1)                                    ║
╚══════════════════════════════════════════════════════════════════════════╝
                                   ↓
╔══════════════════════════════════════════════════════════════════════════╗
║  ✨ G - GENERATION (STAGE 3: Advanced Features)                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Generate for each CV:                                                   ║
║  - interview_questions (5 strategic questions)                           ║
║  - cv_presentation_comment (nested object):                              ║
║    {structure, strengths[], issues[], highlights, suggestions[]}        ║
║  - job_leveling (array: ["Junior", "Mid", "Senior"])                    ║
║  - job_leveling_reason (30-50 words)                                     ║
║  - cert_comment (certification recommendations)                          ║
║                                                                          ║
║  💾 Cache: advanced_features (key: jd_hash + cv_id + options_hash)       ║
║  💰 Cost: ~$0.015 for 5 CVs (MISS) / $0 (HIT)                            ║
║  ⏱️  Time: ~7-10s (MISS) / ~1s (HIT)                                     ║
╚══════════════════════════════════════════════════════════════════════════╝
                                   ↓
┌──────────────────────────────────────────────────────────────────────────┐
│  OUTPUT: Top 5 CVs with Advanced Features                                │
│                                                                          │
│  - Candidate info (name, email, phone, experience)                       │
│  - Score (0-100) + matched requirements                                  │
│  - Interview questions (5 personalized)                                  │
│  - CV presentation analysis (structure, strengths, issues, suggestions)  │
│  - Job leveling recommendation + reasoning                               │
│  - Certification recommendations                                         │
│                                                                          │
│  💰 Total Cost (cache MISS): ~$0.017-0.043 (41-50 CVs)                   │
│  💰 Total Cost (cache HIT): ~$0.003                                      │
│  ⏱️  Total Time (cache MISS): ~340-425s (5.7-7.1 minutes)                │
│  ⏱️  Total Time (cache HIT): ~5-8s                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Comparison: Traditional RAG vs AI-BE

| Component | Traditional RAG | AI-BE Implementation |
|-----------|----------------|---------------------|
| **Use Case** | Question answering (docs) | CV-JD matching |
| **Query** | User question | Job Description (JD) |
| **Documents** | Text chunks (500-1000 tokens) | Whole CVs (no chunking) |
| **VectorDB** | Pinecone/Weaviate/Chroma | ChromaDB (persistent) |
| **Embedding** | text-embedding-ada-002 | text-embedding-3-large |
| **Top-K** | 3-5 chunks | 50 CVs |
| **Reranking** | ✅ Often used (cross-encoder) | ❌ Not implemented |
| **Augmentation** | Concatenate chunks | Multi-layer context (JD + Requirements + CV + Options) |
| **Generation** | Answer question (markdown) | Generate structured JSON (5+ fields) |
| **Output Format** | Free text | Structured JSON (nested objects, arrays) |
| **Caching** | ❌ Rarely cached | ✅ Multi-stage cache (R + A + G) |
| **Batching** | ❌ Usually 1 query | ✅ 5-7 CVs per batch (Stage 1B) |

---

## 💪 Strengths of Implementation

### **1. Comprehensive Caching Strategy**

```
┌─────────────────────────────────────────────┐
│  CACHE LAYER 1: Embeddings (R)              │
│  - CV embeddings: Reuse across JDs          │
│  - JD embeddings: Reuse across searches     │
│  - Hit rate: ~80-90% (stable CVs)           │
└─────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────┐
│  CACHE LAYER 2: Extracted Data (A)          │
│  - CV + JD hash: Reuse same combinations    │
│  - Hit rate: ~50-70% (JD changes often)     │
└─────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────┐
│  CACHE LAYER 3: Advanced Features (G)       │
│  - CV + JD + options: Reuse exact configs   │
│  - Hit rate: ~30-50% (options vary)         │
└─────────────────────────────────────────────┘
```

**Result**: 93% cost savings when cache hits!

### **2. Structured Generation**

- ✅ JSON schema validation
- ✅ Nested objects (cv_presentation_comment)
- ✅ Arrays with specific lengths (5 interview questions)
- ✅ Enum types (job_leveling: ["Junior", "Mid", "Senior"])

### **3. Efficient Batching**

| Stage | Batch Size | Reasoning |
|-------|-----------|-----------|
| Stage 1B | 5-7 CVs | Balance: Quality vs API calls |
| Stage 3 | 1 CV | Complex nested JSON, avoid truncation |

### **4. Multi-Stage Augmentation**

Each stage builds on previous:
1. Stage 0: Raw similarity → Top-50 CVs
2. Stage 1A: JD → Structured requirements
3. Stage 1B: Requirements + CVs → Matched data
4. Stage 3: All above → Advanced features

---

## 🚀 Potential Improvements

### **1. Add Reranking (After Retrieval)**

```python
# Current: Stage 0 → 50 CVs directly to Stage 1B

# Improved: Stage 0 → 50 CVs → Reranker → Top 30 CVs → Stage 1B
from sentence_transformers import CrossEncoder

reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
scores = reranker.predict([(jd_text, cv_text) for cv in top_50_cvs])
reranked_cvs = sorted(zip(top_50_cvs, scores), key=lambda x: x[1], reverse=True)[:30]
```

**Benefit**: Better ranking accuracy (cross-encoder > bi-encoder)

### **2. Implement CV Chunking**

```python
# Current: Embed whole CV (~2000 tokens)

# Improved: Chunk CV by sections
chunks = [
    cv["summary"],       # ~100 tokens
    cv["experience"],    # ~800 tokens
    cv["skills"],        # ~200 tokens
    cv["projects"]       # ~500 tokens
]
embeddings = [embed(chunk) for chunk in chunks]
```

**Benefit**: Better semantic matching for specific JD aspects

### **3. Hybrid Search (Semantic + Keyword)**

```python
# Current: Pure semantic search (embeddings only)

# Improved: Combine semantic + keyword
def hybrid_search(jd_text, cvs):
    # Semantic: embedding similarity
    semantic_scores = vector_db.search_similar_cvs(jd_embedding)
    
    # Keyword: BM25 or ElasticSearch
    keyword_scores = bm25_search(jd_text, cvs)
    
    # Combine: weighted average
    final_scores = 0.7 * semantic_scores + 0.3 * keyword_scores
    return final_scores
```

**Benefit**: Catch exact skill matches (e.g., "React 3+ years")

### **4. Metadata Filtering (Pre-filter)**

```python
# Current: Embed all 100 CVs → Filter by similarity

# Improved: Filter by metadata first
def pre_filter_by_metadata(cvs, jd_requirements):
    filtered = []
    for cv in cvs:
        # Hard filters
        if cv["experience_years"] < jd_requirements["experience_years_required"]:
            continue
        
        # Must-have skills filter
        has_critical_skills = any(
            skill in cv["skills"] 
            for skill in jd_requirements["critical_skills"]
        )
        if not has_critical_skills:
            continue
        
        filtered.append(cv)
    
    return filtered  # e.g., 100 → 60 CVs

# Then: Embed only 60 CVs → Similarity search
```

**Benefit**: Reduce embedding cost + improve precision

### **5. Add Citations/Evidence**

```python
# Current: Generate match notes ("4 years experience")

# Improved: Add evidence with line numbers
{
  "skill": "React",
  "matched": true,
  "note": "4 years experience",
  "evidence": "Line 15-17: 'Worked with React.js for 4 years at Company X, building 10+ production apps'",
  "confidence": 0.95
}
```

**Benefit**: Explainability + verification

---

## 📝 Code References

| Component | File | Function/Class | Lines |
|-----------|------|----------------|-------|
| **R - Embedding** | `routers/thinking.py` | `get_embedding()` | 216-270 |
| **R - Vector Search** | `db/vector_db.py` | `search_similar_cvs()` | 210-250 |
| **R - Cache CV** | `db/vector_db.py` | `cache_cv_embedding()` | 60-93 |
| **R - Cache JD** | `db/vector_db.py` | `cache_jd_embedding()` | 140-175 |
| **A - Stage 1A** | `routers/thinking.py` | JD extraction logic | 663-705 |
| **A - Stage 1B** | `routers/thinking.py` | CV extraction batching | 707-870 |
| **A - Stage 3** | `routers/thinking.py` | Advanced features | 980-1100 |
| **A - Prompt Templates** | `prompts.py` | All prompt functions | 1-400 |
| **G - GPT Calls** | `routers/thinking.py` | `client.chat.completions.create()` | Multiple |
| **Cache Strategy** | `db/vector_db.py` | All cache functions | Full file |

---

## 📊 Performance Metrics

### **Cache Impact**

| Scenario | Retrieval (R) | Augmentation (A) | Generation (G) | Total Cost | Total Time |
|----------|---------------|------------------|----------------|------------|------------|
| **All MISS** | $0.0066 | $0.015 | $0.015 | **$0.037** | **340-425s** |
| **All HIT** | $0 | $0 | $0 | **$0.003** | **5-8s** |
| **Savings** | - | - | - | **93%** | **98%** |

### **Cost Breakdown (41 CVs, Cache MISS)**

```
Stage 0 (R):  $0.0066  (18%)  ████████
Stage 1A (A): $0.0044  (12%)  █████
Stage 1B (A): $0.0123  (33%)  ██████████████
Stage 2:      $0       (0%)   
Stage 3 (G):  $0.0134  (36%)  ███████████████
────────────────────────────────────────────
TOTAL:        $0.0367  (100%)
```

**Insight**: Stage 1B + Stage 3 account for 69% of cost

### **Time Breakdown (41 CVs, Cache MISS)**

```
Stage 0 (R):  30-60s   (9-14%)   ███
Stage 1A (A): 3-5s     (1%)      
Stage 1B (A): 300-350s (88-82%)  ███████████████████████████████
Stage 2:      <0.1s    (0%)      
Stage 3 (G):  7-10s    (2-3%)    █
──────────────────────────────────────────────
TOTAL:        340-425s (100%)
```

**Insight**: Stage 1B is the bottleneck (88% of time)

---

## 🎓 Best Practices Applied

### **1. Cache-First Strategy**
```python
# Always check cache before generating
cached = vector_db.get_cached_cv_embedding(file_id, content)
if cached:
    return cached
else:
    generate_new()
```

### **2. Structured Prompts**
```python
# Use structured context (JSON) instead of raw text
prompt = f"""
Requirements (JSON):
{json.dumps(requirements, indent=2)}

CV Content:
{cv_text}
"""
```

### **3. Error Handling**
```python
# Graceful degradation
try:
    result = json.loads(response)
except JSONDecodeError:
    logger.error("Failed to parse JSON, using fallback")
    result = extract_json_with_regex(response)
```

### **4. Batch Optimization**
```python
# Process multiple items together
batches = [cvs[i:i+7] for i in range(0, len(cvs), 7)]
for batch in batches:
    process_batch(batch)  # 1 API call for 7 CVs
```

### **5. Cost Tracking**
```python
# Track token usage for cost analysis
logger.info(f"📊 Tokens: {input_tokens} in + {output_tokens} out")
logger.info(f"💰 Cost: ${total_cost:.4f}")
```

---

## 🎯 Conclusion

The AI-BE project implements a **sophisticated RAG pattern** with:

✅ **R (Retrieval)**: Vector similarity search with ChromaDB, top-50 CVs, comprehensive caching  
✅ **A (Augmentation)**: Multi-layer context (JD + Requirements + CV + Options), structured prompts  
✅ **G (Generation)**: Complex nested JSON generation, multiple stages, batching optimization

**Key Differentiators:**
- Multi-stage RAG (not just 1-shot R+A+G)
- Extensive caching at every layer
- Structured generation (JSON schema)
- Hybrid approach (RAG + deterministic scoring)

**Result**: 93% cost savings with cache, 5.7-minute processing (cache miss) vs 5-second (cache hit)
