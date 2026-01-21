# AI CV Matching System - Technical Documentation

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [AI Models & Configuration](#ai-models--configuration)
4. [Vector Database Architecture](#vector-database-architecture)
5. [3-Stage Processing Pipeline](#3-stage-processing-pipeline)
6. [Caching Strategy](#caching-strategy)
7. [API Specifications](#api-specifications)
8. [Performance Metrics](#performance-metrics)
9. [Security & Authentication](#security--authentication)
10. [Deployment Guide](#deployment-guide)

---

## 1. System Overview

### Purpose
An AI-powered CV matching system that analyzes candidate resumes against job descriptions using semantic search, natural language processing, and deterministic scoring algorithms.

### Tech Stack Summary

```
┌─────────────┬──────────────┬──────────────┐
│  FRONTEND   │   BACKEND    │  AI ENGINE   │
├─────────────┼──────────────┼──────────────┤
│ Next.js 16  │ FastAPI      │ OpenAI API   │
│ TypeScript  │ Python 3.x   │ ChromaDB     │
│ Tailwind 4  │ SQLite       │ RAG Pipeline │
│ AWS Cognito │ Uvicorn      │ Embeddings   │
└─────────────┴──────────────┴──────────────┘
```

### Key Features
- **Semantic CV Search**: Vector similarity using OpenAI embeddings (1536-D)
- **Multi-stage Processing**: 4-stage hybrid AI + deterministic pipeline
- **Intelligent Caching**: ChromaDB vector cache with 95% cost reduction
- **Multi-language Support**: English, Vietnamese, Japanese prompts
- **Scalable Architecture**: Handle 100+ CVs in 5-6 minutes (cache MISS) or 3-5 seconds (cache HIT)

---

## 2. Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────┐
│         FRONTEND LAYER                   │
│  Next.js 16 + TypeScript + Tailwind     │
│  AWS Cognito Authentication             │
└──────────────┬──────────────────────────┘
               │
               ▼
      HTTP/REST API (CORS enabled)
               │
               ▼
┌─────────────────────────────────────────┐
│         BACKEND LAYER                    │
│  FastAPI + Uvicorn (Port 8000)          │
│                                          │
│  ┌──────────┬──────────┬─────────────┐ │
│  │CV Router │JD Router │Thinking     │ │
│  │  /cv/*   │  /jd/*   │Router       │ │
│  │          │          │ /thinking/* │ │
│  └──────────┴──────────┴─────────────┘ │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│    3-STAGE AI PROCESSING ENGINE         │
│                                          │
│  Stage 0: Vector Similarity Search       │
│  Stage 1A: JD Requirements Extraction   │
│  Stage 1B: CV Data Extraction (Batched) │
│  Stage 2: Deterministic Scoring         │
│  Stage 3: Advanced Features (Optional)  │
└──────┬────────┬────────┬────────────────┘
       │        │        │        
       ▼        ▼        ▼        ▼
┌─────────┐┌─────────┐┌─────────┐┌─────────┐
│ SQLite  ││ChromaDB ││OpenAI   ││  File   │
│Database ││Vector DB││   API   ││ Storage │
│         ││         ││         ││         │
│Metadata ││4 Caches ││3 Models ││CV/JD    │
│File info││Vectors  ││Prompts  ││PDF/DOCX │
└─────────┘└─────────┘└─────────┘└─────────┘
```

### Data Flow

```
1. User uploads CV (PDF/DOCX) via Frontend
2. FastAPI extracts text (PyPDF2/python-docx)
3. Store metadata in SQLite + content in database
4. User submits JD text + matching request
5. Stage 0: Generate embeddings → ChromaDB cache
6. Stage 0: Vector similarity search → Top 50 CVs
7. Stage 1A: Extract JD requirements (GPT-4o)
8. Stage 1B: Extract CV data in batches (GPT-4o-mini)
9. Stage 2: Deterministic scoring (Python logic)
10. Stage 3: Advanced features for top CVs (GPT-4o-mini)
11. Return sorted results to Frontend
```

---

## 3. AI Models & Configuration

### OpenAI Models

| Model | Purpose | Context | Token Limit | Cost (per 1K tokens) |
|-------|---------|---------|-------------|---------------------|
| **text-embedding-3-large** | Vector embeddings | Stage 0 | 8,191 input | $0.13 input |
| **gpt-4o** | JD requirements extraction | Stage 1A | 128K context | $2.50 input / $10.00 output |
| **gpt-4o-mini** | CV data extraction, Advanced features | Stage 1B, 3 | 128K context | $0.150 input / $0.600 output |

### Model Selection Strategy

```python
# config.py
OPENAI_MODEL = "gpt-4o"              # Stage 1A (JD extraction - complex)
OPENAI_MINI_MODEL = "gpt-4o-mini"    # Stage 1B, 3 (CV extraction - simple)
OPENAI_EMBEDDING_MODEL = "text-embedding-3-large"  # Stage 0 (embeddings)
```

**Rationale:**
- **Stage 1A**: Uses GPT-4o (expensive) because JD requirements are complex and critical
- **Stage 1B**: Uses GPT-4o-mini (cheap) because CV extraction follows structured template
- **Stage 3**: Uses GPT-4o-mini (cheap) for additional features like interview questions

### Temperature & Token Settings

```python
# Stage 1A: JD Requirements Extraction
temperature = 0.1      # Low randomness for consistent structure
max_tokens = 6000      # Complex JSON output

# Stage 1B: CV Data Extraction (Batched)
temperature = 0.1      # Consistent extraction
max_tokens = 6000      # JSON array for multiple CVs

# Stage 3: Advanced Features
temperature = 0.1      # Deterministic features
max_tokens = 6000      # Large object with nested structure
```

### Multi-language Prompt System

```python
# config.py
PROMPT_LANGUAGE = os.getenv("PROMPT_LANGUAGE", "en")  # vi, en, ja

# prompts.py - Dynamic loader
SUPPORTED_LANGUAGES = {
    "vi": "prompts.vi",
    "en": "prompts.en", 
    "ja": "prompts.ja"
}

# Auto-loads correct module based on PROMPT_LANGUAGE
from prompts import get_extraction_prompt  # Automatically uses correct language
```

**Features:**
- ✅ Separate prompt files per language
- ✅ Dynamic module loading at runtime
- ✅ Environment variable configuration
- ✅ Consistent API across languages

---

## 4. Vector Database Architecture

### ChromaDB Configuration

```python
# db/vector_db.py
client = chromadb.PersistentClient(
    path="./chroma_db",
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)
```

### Collections

| Collection | Purpose | Cache Key | Similarity Match |
|-----------|---------|-----------|-----------------|
| `cv_embeddings` | CV vector cache | `md5(cv_content)` | Exact (100%) |
| `jd_embeddings` | JD vector cache | `md5(jd_text + lang)` | Fuzzy (95%) |
| `cv_extracted_data` | CV parsed JSONs | `cv_hash + jd_hash` | Exact (100%) |
| `advanced_features` | Stage 3 features | `jd_hash + cv_id + options_hash` | Exact (100%) |
| `jd_requirements_data` | JD requirements | `jd_hash + lang` | Exact (100%) |

### Vector Embedding Specifications

```python
# Embedding dimensions
EMBEDDING_DIMENSION = 1536  # text-embedding-3-large

# Similarity metric
SIMILARITY_METRIC = "cosine"  # ChromaDB default

# Embedding generation
def get_embedding(text: str) -> List[float]:
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=clean_text_for_embedding(text)  # Remove emojis, special chars
    )
    return response.data[0].embedding  # Returns 1536-D vector
```

### Cache Key Generation

```python
# CV Embeddings - Exact Match
cv_hash = hashlib.md5(cv_content.encode()).hexdigest()
doc_id = f"cv_{file_id}_{cv_hash[:16]}"

# JD Embeddings - Language-aware
jd_cache_key = f"{jd_text}_{PROMPT_LANGUAGE}"
jd_hash = hashlib.md5(jd_cache_key.encode()).hexdigest()
doc_id = f"jd_{jd_hash[:16]}"

# CV Extracted Data - Dependent on both CV and JD
cache_key = f"{cv_hash}_{jd_hash}"

# Advanced Features - Dependent on JD, CV, and options
cache_key = f"{jd_hash}_{cv_id}_{options_hash}"
```

### Similarity Search Algorithm

```python
# Cosine similarity calculation
def cosine_similarity(vec1: list, vec2: list) -> float:
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    
    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)
    
    return float(dot_product / (norm1 * norm2))

# ChromaDB query
results = collection.query(
    query_embeddings=[jd_embedding],
    n_results=50,  # Top 50 most similar CVs
    include=['embeddings', 'metadatas', 'distances']
)
```

---

## 5. 3-Stage Processing Pipeline

### Stage 0: Vector Similarity Search (Pre-filtering)

**Purpose:** Reduce 100 CVs → 50 CVs using semantic similarity

**Process:**
```python
1. Generate JD embedding (1536-D vector)
2. Generate CV embeddings for all CVs (check cache first)
3. Calculate cosine similarity: JD vs each CV
4. Sort by similarity (descending)
5. Return top 50 CVs (similarity > 0.85)
```

**Caching:**
- **Cache HIT**: ~1 second (retrieve from ChromaDB)
- **Cache MISS**: ~30-60 seconds (call OpenAI API for 100 CVs)

**Cost Optimization:**
```python
# First run (100 CVs)
Cost = 100 CVs × $0.0001 + 1 JD × $0.0001 = $0.0101

# Second run (cached)
Cost = $0 (all from cache)

# Savings: 100% after first run
```

---

### Stage 1A: JD Requirements Extraction

**Model:** GPT-4o (gpt-4o)

**Input:**
```
JD text + Response requirement
```

**Output:**
```json
{
  "role_type": "Senior React Developer",
  "must_have_requirements": [
    {
      "skill": "React",
      "years": 3,
      "description": "3+ years of React development experience"
    },
    {
      "skill": "TypeScript",
      "years": null,
      "description": "Strong TypeScript skills"
    }
  ],
  "nice_to_have_requirements": [
    {
      "skill": "GraphQL",
      "years": null,
      "description": "GraphQL API experience preferred"
    }
  ]
}
```

**Caching:**
- **Key:** `md5(jd_text + PROMPT_LANGUAGE)`
- **Collection:** `jd_requirements_data`
- **Hit Rate:** ~80% (same JD reused)

**Performance:**
- Cache HIT: < 0.1s
- Cache MISS: ~2-5s (GPT-4o call)

---

### Stage 1B: CV Data Extraction (Batched)

**Model:** GPT-4o-mini

**Batch Size:** 5 CVs per API call

**Input:**
```
5 CV texts + JD requirements JSON
```

**Output (per CV):**
```json
{
  "cv_id": "cv_abc",
  "candidate_name": "Nguyen Van A",
  "email": "nguyen.vana@email.com",
  "phone": "0123456789",
  "experience_years": 4,
  "current_position": "Frontend Developer",
  "skills": ["React", "TypeScript", "Redux", "Next.js"],
  "must_have_matched": [
    {
      "skill": "React",
      "matched": true,
      "years": 4,
      "note": "4 years React experience at Company X"
    },
    {
      "skill": "TypeScript",
      "matched": true,
      "years": 3,
      "note": "Used TypeScript in all recent projects"
    }
  ],
  "nice_to_have_matched": [
    {
      "skill": "GraphQL",
      "matched": false,
      "note": "No GraphQL experience mentioned"
    }
  ]
}
```

**Batching Strategy:**
```python
# 50 CVs → 10 batches of 5 CVs each
BATCH_SIZE = 5
total_batches = math.ceil(50 / BATCH_SIZE)  # 10 batches

for batch in batches:
    # Check cache for each CV first
    cached_cvs = [check_cache(cv) for cv in batch]
    uncached_cvs = [cv for cv in batch if not cached]
    
    if uncached_cvs:
        # Call OpenAI for uncached CVs only
        results = call_openai(uncached_cvs, requirements)
        
        # Save to cache
        for result in results:
            cache_result(result)
```

**Caching:**
- **Key:** `md5(cv_content) + md5(jd_text)`
- **Collection:** `cv_extracted_data`
- **Hit Rate:** ~95% (same CVs + JD reused)

**Performance:**
- Cache HIT (all 50 CVs): ~1s
- Cache MISS (50 CVs): ~300-350s (10 batches × 30-35s each)
- Partial MISS (25 CVs): ~150-175s (5 batches)

---

### Stage 2: Deterministic Scoring

**Model:** ❌ No AI (Pure Python logic)

**Algorithm:**
```python
class CVScoringEngine:
    def calculate_score(self, cv_data: dict) -> dict:
        # Count matched requirements
        must_have_matched = [m for m in cv_data['must_have_matched'] if m['matched']]
        nice_to_have_matched = [m for m in cv_data['nice_to_have_matched'] if m['matched']]
        
        # Calculate must-have percentage
        must_have_pct = len(must_have_matched) / total_must_haves
        
        # Base score (0-90 points from must-haves)
        base_score = must_have_pct * 90
        
        # Bonus (0-10 points from nice-to-haves)
        nice_bonus = (len(nice_to_have_matched) / total_nice_haves) * 10
        
        # Total score
        total_score = base_score + nice_bonus
        
        # Apply penalties for missing must-haves
        missing_count = total_must_haves - len(must_have_matched)
        if missing_count == 1:
            total_score = min(total_score, 85)
        elif missing_count == 2:
            total_score = min(total_score, 70)
        elif missing_count >= 3:
            total_score = min(total_score, 60)
        
        return total_score
```

**Scoring Rules:**

| Must-Have Match % | Base Score | Max Final Score |
|------------------|------------|-----------------|
| 100% (all matched) | 90 | 100 (with bonuses) |
| 80% (1 missing) | 72 | 85 (capped) |
| 60% (2 missing) | 54 | 70 (capped) |
| < 60% (3+ missing) | < 54 | 60 (capped) |

**Performance:**
- Time: < 0.1 seconds (50 CVs)
- Cost: FREE (no API calls)

**Output:**
```python
[
  {"cv_id": "cv_1", "score": 97.5, ...},
  {"cv_id": "cv_2", "score": 92.0, ...},
  {"cv_id": "cv_3", "score": 88.5, ...},
  # ... sorted by score descending
  {"cv_id": "cv_48", "score": 15.0, ...}
]
# CVs with score = 0 are filtered out
```

---

### Stage 3: Advanced Features (Optional)

**Model:** GPT-4o-mini

**Batch Size:** 1 CV per API call (complex nested JSON structure)

**Input:**
```
Top 5 CVs (based on max_cv_count) + JD + Requirements + Advanced Options
```

**Output (per CV):**
```json
{
  "cv_id": "cv_abc",
  "cv_presentation_comment": {
    "structure": "Chronological format, 4 sections: Summary, Experience, Skills, Education",
    "strengths": [
      "Clear project descriptions with metrics",
      "Well-organized skills by category",
      "Demonstrates progression in roles"
    ],
    "issues": [
      "Experience section too long (3 pages)",
      "Missing LinkedIn/GitHub links",
      "No professional summary at top"
    ],
    "highlights": "Real-time Chat Application serving 10K concurrent users",
    "suggestions": [
      "Add 3-4 sentence professional summary",
      "Shorten older job experiences (> 3 years ago)",
      "Add quantifiable achievements to each role"
    ]
  },
  "interview_questions": [
    "Can you explain the architecture of your real-time chat application?",
    "How did you handle state management in large React applications?",
    "Describe a challenging TypeScript type issue you solved.",
    "What's your experience with performance optimization in React?",
    "How do you approach testing in frontend applications?"
  ],
  "job_leveling": ["Junior", "Mid"],
  "job_leveling_reason": "4 years experience with strong React/TypeScript skills, but limited senior-level responsibilities like architecture design or mentoring",
  "cert_comment": "Suggest pursuing AWS Certified Developer or React Advanced Patterns certification to strengthen cloud/architecture skills"
}
```

**Advanced Features Breakdown:**

| Feature | Type | Description |
|---------|------|-------------|
| `cv_presentation_comment` | Object | CV structure analysis with 5 sub-fields |
| `interview_questions` | Array[5] | Strategic interview questions |
| `job_leveling` | Array | Suitable levels (e.g., ["Junior", "Mid"]) |
| `job_leveling_reason` | String | 30-50 word justification |
| `cert_comment` | String | Certification recommendations |

**Caching:**
- **Key:** `md5(jd_text) + cv_id + md5(advanced_options)`
- **Collection:** `advanced_features`
- **Hit Rate:** ~90% (same CVs + JD + options)

**Performance:**
- Cache HIT (5 CVs): ~1s
- Cache MISS (5 CVs): ~7-10s (5 batches × 1.5s each)

**Why Batch Size = 1?**
- Complex nested JSON structure (cv_presentation_comment object)
- High max_tokens requirement (6000 tokens per CV)
- Risk of incomplete JSON with multiple CVs
- Better reliability with single CV per call

---

## 6. Caching Strategy

### Cache Hit Rate by Stage

| Stage | Cache Type | Hit Rate | Savings |
|-------|-----------|---------|---------|
| Stage 0 | CV embeddings | 95% | ~$0.01 per run |
| Stage 0 | JD embeddings | 80% | ~$0.0001 per run |
| Stage 1A | JD requirements | 80% | ~$0.003 per run |
| Stage 1B | CV extracted data | 95% | ~$0.012-0.018 per run |
| Stage 3 | Advanced features | 90% | ~$0.015 per run |

### Cost Comparison

**Without Cache (100 CVs, 1 JD):**
```
Stage 0: 100 CV embeddings + 1 JD = $0.0101
Stage 1A: JD extraction (GPT-4o) = $0.003
Stage 1B: 50 CVs extraction (10 batches, GPT-4o-mini) = $0.018
Stage 3: 5 CVs advanced features (GPT-4o-mini) = $0.015
─────────────────────────────────────────────────
TOTAL: ~$0.046 per run
```

**With Cache (95% hit rate):**
```
Stage 0: 5 CV embeddings + 0 JD = $0.0005
Stage 1A: Cached = $0
Stage 1B: Cached = $0
Stage 3: Cached = $0
─────────────────────────────────────────────────
TOTAL: ~$0.0005 per run (92x cheaper!)
```

### Cache Invalidation Strategy

```python
# CV Embeddings - NEVER invalidate (content-based hash)
# Rationale: CV content doesn't change

# JD Embeddings - Fuzzy match (95% similarity)
def should_use_cached_jd(jd_text: str) -> bool:
    # Check for similar JD in cache
    similar_jds = vector_db.find_similar_jds(jd_text, threshold=0.95)
    return len(similar_jds) > 0

# CV Extracted Data - Invalidate when JD changes
# Key: cv_hash + jd_hash (both must match)

# Advanced Features - Invalidate when JD or options change
# Key: jd_hash + cv_id + options_hash (all must match)
```

---

## 7. API Specifications

### Frontend → Backend Communication

**Base URL:** `http://localhost:8000`

**CORS Configuration:**
```python
CORS_ORIGINS = [
    "http://localhost:3000",  # Next.js dev
    "http://localhost:3001",
    "http://localhost:5173",  # Vite dev
    # Add production origins
]
```

---

### 📤 Upload CV Endpoint

**POST** `/cv/upload`

**Headers:**
```
Content-Type: multipart/form-data
```

**Request:**
```json
{
  "file": <binary PDF/DOCX>,
  "filename": "nguyen_van_a_cv.pdf"
}
```

**Response:**
```json
{
  "success": true,
  "message": "CV uploaded successfully",
  "file": {
    "id": 123,
    "original_filename": "nguyen_van_a_cv.pdf",
    "file_path": "cvs/cv_123_nguyen_van_a.pdf",
    "file_type": "cv",
    "uploaded_at": "2026-01-14T10:30:00Z",
    "content_length": 15234
  }
}
```

---

### 📤 Upload JD Endpoint

**POST** `/jd/upload`

**Request:**
```json
{
  "file": <binary PDF/DOCX/TXT>,
  "filename": "senior_react_jd.pdf"
}
```

**Response:**
```json
{
  "success": true,
  "message": "JD uploaded successfully",
  "file": {
    "id": 45,
    "original_filename": "senior_react_jd.pdf",
    "file_path": "jds/jd_45_senior_react.pdf",
    "file_type": "jd",
    "uploaded_at": "2026-01-14T10:32:00Z"
  }
}
```

---

### 🧠 Thinking (CV Matching) Endpoint

**POST** `/thinking/`

**Headers:**
```
Content-Type: multipart/form-data
```

**Request:**
```json
{
  "jd_text": "We are looking for a Senior React Developer with 3+ years...",
  "response_requirement": "Get top 5 CVs",
  "max_cv_count": "5",
  "advanced_options": {
    "include_interview_questions": true,
    "include_cv_analysis": true,
    "include_job_leveling": true,
    "include_cert_recommendations": true
  }
}
```

**Response:**
```json
{
  "status": "success",
  "total_cvs_processed": 100,
  "total_cvs_after_filtering": 50,
  "cv_mappings": [
    {
      "cv_id": "cv_123",
      "candidate_name": "Nguyen Van A",
      "email": "nguyen.vana@email.com",
      "phone": "0123456789",
      "score": 97.5,
      "similarity": 0.92,
      "experience_years": 4,
      "current_position": "Frontend Developer",
      "matched_requirements": [
        "React - 4 years experience",
        "TypeScript - Used in all projects",
        "Redux - State management expert"
      ],
      "missing_requirements": [
        "GraphQL - No experience mentioned"
      ],
      "skills": ["React", "TypeScript", "Redux", "Next.js"],
      "mapping_description": "Nguyen Van A meets 9/10 must-have requirements (missing 1). Additionally meets 3/5 nice-to-have requirements.",
      "cv_presentation_comment": {
        "structure": "Chronological, 4 sections",
        "strengths": ["Clear metrics", "Organized skills"],
        "issues": ["Too long experience section"],
        "highlights": "Real-time Chat App (10K users)",
        "suggestions": ["Add summary", "Shorten old projects"]
      },
      "interview_questions": [
        "Explain your chat app architecture",
        "How do you handle React state in large apps?",
        "Describe a TypeScript challenge you solved",
        "Performance optimization techniques?",
        "Your approach to frontend testing?"
      ],
      "job_leveling": ["Junior", "Mid"],
      "job_leveling_reason": "4 years exp with strong React/TS, but limited senior responsibilities",
      "cert_comment": "Suggest AWS Certified Developer for cloud skills"
    }
    // ... 4 more CVs
  ],
  "processing_time_seconds": 8.5,
  "cache_stats": {
    "stage0_cache_hit_rate": 0.95,
    "stage1b_cache_hit_rate": 1.0,
    "stage3_cache_hit_rate": 1.0
  }
}
```

---

### 📊 Get All CVs Endpoint

**GET** `/cv/list?limit=100&offset=0`

**Response:**
```json
{
  "files": [
    {
      "id": 123,
      "original_filename": "nguyen_van_a_cv.pdf",
      "file_type": "cv",
      "uploaded_at": "2026-01-14T10:30:00Z"
    }
  ],
  "total": 150,
  "limit": 100,
  "offset": 0
}
```

---

## 8. Performance Metrics

### Latency Breakdown

**Cache MISS (First run, 100 CVs):**
```
Stage 0 (Embeddings): ~30-60s
  - CV embeddings: ~30-50s (100 API calls)
  - JD embedding: ~1s (1 API call)
  - Similarity search: ~1s

Stage 1A (JD Extraction): ~2-5s
  - GPT-4o call: ~2-5s

Stage 1B (CV Extraction): ~300-350s (5-6 minutes)
  - 10 batches × 30-35s per batch
  - GPT-4o-mini calls

Stage 2 (Scoring): < 0.1s
  - Pure Python logic

Stage 3 (Advanced Features): ~7-10s
  - 5 CVs × 1.5s per CV
  - GPT-4o-mini calls

─────────────────────────────────────────────
TOTAL: ~340-430s (5.6-7.2 minutes)
```

**Cache HIT (Subsequent runs):**
```
Stage 0: ~1s (retrieve from ChromaDB)
Stage 1A: < 0.1s (retrieve from cache)
Stage 1B: ~1s (retrieve from cache)
Stage 2: < 0.1s (compute)
Stage 3: ~1s (retrieve from cache)

─────────────────────────────────────────────
TOTAL: ~3-5s (160x faster!)
```

### Scalability

| CVs | Stage 0 (MISS) | Stage 1B (MISS) | Total (MISS) | Total (HIT) |
|-----|----------------|-----------------|--------------|-------------|
| 10 | ~5-10s | ~60-70s | ~70-80s | ~3s |
| 50 | ~20-30s | ~300-350s | ~330-390s | ~3s |
| 100 | ~30-60s | ~600-700s | ~640-770s | ~4s |
| 200 | ~60-120s | ~1200-1400s | ~1270-1530s | ~5s |

**Note:** Cache HIT performance is near-constant regardless of CV count.

---

## 9. Security & Authentication

### Frontend Authentication (AWS Cognito)

```typescript
// src/configs/amplify.ts
import { Amplify } from 'aws-amplify';

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID,
      userPoolClientId: process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID,
      loginWith: {
        oauth: {
          domain: process.env.NEXT_PUBLIC_COGNITO_DOMAIN,
          scopes: ['email', 'openid', 'profile'],
          redirectSignIn: ['http://localhost:3000/'],
          redirectSignOut: ['http://localhost:3000/'],
          responseType: 'code'
        }
      }
    }
  }
});
```

### Backend API Security

```python
# config.py
CORS_ORIGINS = [
    "http://localhost:3000",
    # Add production frontend URL
]

# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Environment Variables

```bash
# .env (Backend)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_MINI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
PROMPT_LANGUAGE=en  # or vi, ja

# .env.local (Frontend)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_COGNITO_USER_POOL_ID=us-east-1_...
NEXT_PUBLIC_COGNITO_CLIENT_ID=...
NEXT_PUBLIC_COGNITO_DOMAIN=...
```

### Data Privacy

- ✅ CV content stored in local SQLite database
- ✅ Embeddings cached in local ChromaDB
- ❌ No CV data sent to third parties (except OpenAI for processing)
- ✅ HTTPS recommended for production
- ✅ User authentication via AWS Cognito

---

## 10. Deployment Guide

### Local Development

**Backend:**
```bash
cd ai-be

# Install dependencies
uv sync  # or pip install -r requirements.txt

# Create .env file
echo "OPENAI_API_KEY=sk-..." > .env

# Run server
uv run python main.py
# Server runs on http://localhost:8000
```

**Frontend:**
```bash
cd ai-fe

# Install dependencies
npm install

# Create .env.local
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local

# Run dev server
npm run dev
# Frontend runs on http://localhost:3000
```

---

### Production Deployment

#### Backend (Recommended: AWS Lambda + API Gateway)

**Option 1: AWS Lambda (Serverless)**
```bash
# Install AWS SAM CLI
brew install aws-sam-cli

# Deploy
sam build
sam deploy --guided
```

**Option 2: Docker + EC2**
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build and run
docker build -t ai-cv-backend .
docker run -p 8000:8000 ai-cv-backend
```

---

#### Frontend (Recommended: Vercel)

**Option 1: Vercel (Recommended for Next.js)**
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

**Option 2: AWS Amplify**
```bash
# Connect GitHub repo to AWS Amplify
# Auto-deploy on push to main branch
```

---

### Database Migration

**SQLite → PostgreSQL (for production)**

```python
# Update config.py
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")

# Use SQLAlchemy for ORM
from sqlalchemy import create_engine
engine = create_engine(DATABASE_URL)
```

---

### ChromaDB Production Setup

**Option 1: Persistent Client (Single server)**
```python
# db/vector_db.py
client = chromadb.PersistentClient(path="./chroma_db")
```

**Option 2: ChromaDB Server (Multi-server)**
```bash
# Start ChromaDB server
uv run chroma run --path ./chroma_db --port 8001

# Update client
client = chromadb.HttpClient(host="localhost", port=8001)
```

---

### Monitoring & Logging

```python
# Add logging to production
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
```

**Recommended Tools:**
- **Sentry**: Error tracking
- **CloudWatch**: AWS logs
- **Datadog**: Performance monitoring

---

## 📚 Additional Documentation

- [3_STAGE_PIPELINE.md](./3_STAGE_PIPELINE.md) - Detailed pipeline explanation
- [VECTOR_CACHE_README.md](./VECTOR_CACHE_README.md) - Cache strategy & tools
- [CHROMADB_CONNECTION_GUIDE.md](./CHROMADB_CONNECTION_GUIDE.md) - ChromaDB setup
- [MULTI_LANGUAGE_PROMPTS.md](./MULTI_LANGUAGE_PROMPTS.md) - Multi-language support

---

## 🔧 Troubleshooting

### Common Issues

**1. OpenAI Rate Limit**
```
Solution: Implement exponential backoff retry (already included)
```

**2. ChromaDB Lock Error**
```bash
# Clear ChromaDB lock
rm -rf chroma_db/.chroma.lock
```

**3. Out of Memory (Large CVs)**
```python
# Limit CV text length
cv_text = cv_text[:10000]  # First 10K chars
```

**4. CORS Error**
```python
# Add frontend origin to CORS_ORIGINS in config.py
CORS_ORIGINS = ["https://your-frontend.com"]
```

---

## 📈 Future Enhancements

- [ ] Support for more file formats (TXT, RTF)
- [ ] Real-time streaming responses (SSE)
- [ ] Batch CV upload (ZIP file)
- [ ] Export results to Excel/PDF
- [ ] Custom scoring algorithms per company
- [ ] Multi-tenant support (company isolation)
- [ ] GraphQL API option
- [ ] WebSocket for live updates

---

**Last Updated:** January 14, 2026  
**Version:** 1.0.0  
**Maintained by:** AI-BE Development Team
