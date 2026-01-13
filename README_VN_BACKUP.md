# AI-BE - CV-JD Matching API

API for uploading CV and JD (Job Description) files, analyzing matching scores using AI (OpenAI GPT), and vector similarity (ChromaDB).

## 📋 Requirements

- **Python 3.8+** (khuyến nghị 3.11+)
- **pip** hoặc **uv** (Python package manager)
- **OS**: Linux, Windows, macOS

## 🚀 Installation and Running Guide

### 1. Clone repository

```bash
git clone <repository-url>
cd ai-be
```

### 2. Install dependencies

**Linux / Windows:**

```bash
# Using pip
pip install -r requirements.txt

# Or if using specific Python 3
python3 -m pip install -r requirements.txt
```

**macOS (recommended to use uv):**

```bash
# Step 1: Install uv (modern package manager, faster than pip)
brew install uv
# or: curl -LsSf https://astral.sh/uv/install.sh | sh

# Step 2: Install dependencies
uv pip install -r requirements.txt
```

> **macOS Note**: `uv` helps manage Python versions automatically and installs packages much faster than pip. However, you can still use `pip` like on Linux/Windows.

### 3. Configure environment variables

Create a `.env` file in the project root directory:

```bash
# Linux/macOS
touch .env

# Windows
type nul > .env
```

Then edit the `.env` file and add your OpenAI API key:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
OPENAI_MINI_MODEL=gpt-4o-mini
```

**Notes:** 
- The `.env` file should not be committed to git (already in `.gitignore`)
- Use `gpt-4o` for high accuracy, `gpt-4o-mini` for cost savings

### 4. Run the application

**Linux / Windows:**

```bash
# Run directly
python3 main.py

# Or use uvicorn with auto-reload (development)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**macOS (with uv):**

```bash
# Run with uv (automatically manages Python version)
uv run python main.py

# Or use uvicorn with auto-reload (development)
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**uvicorn parameters:**
- `--reload`: Auto-reload when code changes (development only)
- `--host 0.0.0.0`: Allow access from any IP address
- `--port 8000`: Default port

### 5PI Base URL**: `http://localhost:8000`
- **API Documentation (Swagger UI)**: `http://localhost:8000/docs`
- **API Documentation (ReDoc)**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

## 📁 Cấu trúc project

```
ai-be/
├── main.py                   # Entry point chính của ứng dụng
├── config.py                 # Cấu hình (OpenAI, database, CORS)
├── models.py                 # Pydantic models cho API responses
├── utils.py                  # Utility functions (extract text từ PDF/DOCX)
├── prompts.py                # OpenAI prompt templates (3-stage approach)
├── requirements.txt          # Python dependencies
├── .env                      # Biến môi trường (KHÔNG commit)
├── .gitignore               # Git ignore rules
├── routers/
│   ├── __init__.py
│   ├── cv.py                # Routes cho CV upload (multiple files)
│   ├── jd.py                # Routes cho JD upload (1 file)
│   └── thinking.py          # Routes cho CV-JD matching (AI-powered)
├── db/
│   ├── __init__.py          # Database package init
│   ├── database.py          # SQLite operations
│   ├── vector_db.py         # ChromaDB vector operations + cache
│   🎯 CV-JD Matching (AI-powered)

- `POST /thinking/` - **Match CVs with JD using AI (THREE-STAGE HYBRID)**
  - Input: JD text, response requirements, advanced options
  - Output: Ranked CVs with scores, matched/missing requirements, advanced features
  - Features:
    - **Stage 1A**: Extract JD requirements (gpt-4o)
    - **Stage 1B**: Extract CV data (gpt-4o-mini, batch processing)
    - **Stage 2**: Deterministic scoring (no API cost)
    - **Stage 3**: Advanced features (conditional, cached)
  - Advanced Options:
    - `cvPresentation`: Evaluate CV professionalism
    - `interviewQuestions`: Suggest interview questions
    - `jobLeveling`: Assess job level
    - `certBenefit`: Analyze certificate benefits

### 📄 JD (Job Description) - Upload 1 file only

- `POST /jd/upload` - Upload JD file (PDF only)
- `GET /jd/files` - List JD files (with pagination: `?limit=100&offset=0`)
- `GET /jd/files/{file_id}` - Get JD file details
- `DELETE /jd/files/{file_id}` - Delete JD file

### 📏 CV - Can upload multiple files

- `POST /cv/upload` - Upload CV files (PDF, DOCX, DOC) - **Có thể upload nhiều file cùng lúc**
- `GET /cv/files` - Danh sách CV files
- `GET /cv/files/{file_id}` - Chi tiết CV file
- `DELETE /cv/files/{file_id}` - Xóa CV file

### 📊POST /jd/upload` - Upload JD file (PDF)
- `GET /jd/files` - Danh sách JD files
- `GET /jd/files/{file_id}` - Chi tiết JD file
- `DELETE /jd/files/{file_id}` - Xóa JD file

### CV - Có thể upload nhiều file

- `POST /cv/upload` - Upload CV files (PDF, DOCX, DOC) - **Can upload multiple files at once**
- `GET /cv/files` - List CV files (with pagination: `?limit=100&offset=0`)
- `GET /cv/files/{file_id}` - Get CV file details
- `GET /cv/files/{file_id}/content` - Get extracted text content from CV
- `DELETE /cv/files/{file_id}` - Delete CV file

### CV-JD Matching (Thinking)

- `POST /thinking` - Đối chiếu CV với JD sử dụng OpenAI
  - Nhận form data: `jd_text`, `response_requirement`, `advanced_options` (JSON string)
  - Trả về danh sách CV đã được đánh giá và sắp xếp theo điểm phù hợp

### Chung

- `GET /` - Thông tin API và danh sách endpoints
- `GET /files` - Lấy tất cả files (có pagination và filter: `?limit=100&offset=0&type=jd` hoặc `?type=cv`)

## 📝 Ví dụ sử dụng

### Upload CV (nhiều file)

```bash
curl -X POST "http://localhost:8000/cv/upload" \
  -F "files=@cv1.pdf" \
  -F "files=@cv2.docx" \
  -F "files=@cv3.pdf"
```

### Upload JD (1 file)

```bash
curl -X POST "http://localhost:8000/jd/upload" \
  -F "file=@job_description.pdf"
```

### Lấy danh sách CV files

```bash
# Lấy 100 CV đầu tiên
curl "http://localhost:8000/cv/files"

# Lấy 50 CV, bỏ qua 10 CV đầu tiên
curl "http://localhost:8000/cv/files?limit=50&offset=10"
```

### Lấy nội dung text của CV

```bash
curl "http://localhost:8000/cv/files/1/content"
```

### Lấy danh sách JD files

```bash
curl "http://localhost:8000/jd/files"
```

### Lấy tất cả files (filter theo type)

```bash
# Lấy tất cả
curl "http://localhost:8000/files"

# Chỉ lấy CV
curl "http://localhost:8000/files?type=cv"

# Chỉ lấy JD
curl "http://localhost:8000/files?type=jd"

# Pagination
curl "http://localhost:8000/files?limit=50&offset=0&type=cv"
```

### Đối chiếu CV với JD

```bash
curl -X POST "http://localhost:8000/thinking" \
  -F "jd_text=Job description text here" \
  -F "response_requirement=Lấy các CV của ứng viên làm PHP" \
  -F "advanced_options={\"cvPresentation\":true,\"interviewQuestions\":true}"
```

**Response format:**

```json
{
  "status": "success",
  "message": "Đã đối chiếu X CV phù hợp với JD",
  "received_data": {...},
  "cv_mappings": [
    {
      "cv_id": "cv_1",
      "file_id": 1,
      "candidate_name": "Tên ứng viên",
      "email": "email@example.com",
      "phone": "+84 xxx xxx xxx",
      "position": "Vị trí",
      "experience_years": 5,
      "skills": ["skill1", "skill2"],
      "education": {
        "degree": "Bằng cấp",
        "university": "Tên trường",
        "graduation_year": 2020
      },
      "scope": {
        "score": 85,
        "matched_requirements": ["Có kinh nghiệm với PHP", ...],
        "missing_requirements": ["Chưa có Laravel", ...]
      },
      "mapping_description": "Mô tả phù hợp",
      "duplicate_warning": null,
      "cv_presentation_comment": "Nhận xét về CV...",
      "interview_questions": ["Câu hỏi 1", "Câu hỏi 2", ...],
      "job_leveling": null,
      "cert_comment": "Nhận xét về chứng chỉ..."
    }
  ],
  "total_cvs_processed": 10,
  "total_cvs_matched": 5
}
```

**Lưu ý:**
- Các field như `duplicate_warning`, `cv_presentation_comment`, `interview_questions`, `job_leveling`, `cert_comment` chỉ xuất hiện khi được bật trong `advanced_options`
- CV được sắp xếp theo điểm số giảm dần (score cao nhất trước)
- Chỉ trả về CV có score > 0

## ⚙️ Cấu hình

### CORS

CORS đã được cấu hình để cho phép requests từ các origin sau:

- `http://localhost:3000`
- `http://localhost:3001`
- `http://localhost:5173` (Vite)
- `http://localhost:8080` (Vue.js)
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

Để thêm origin khác, chỉnh sửa `CORS_ORIGINS` trong file `config.py`.

### Database
**Core Framework:**
- `fastapi` - Modern web framework
- `uvicorn[standard]` - ASGI server
- `python-multipart` - File upload support

**AI & Vector Database:**
- `openai` - OpenAI API client (GPT-4o, GPT-4o-mini)
- `chromadb` - Vector database cho embedding similarity search
- `numpy` - Numerical operations

**Document Processing:**
- `PyPDF2` - PDF text extraction
- `python-docx` - DOCX text extraction

**Environment & Config:**
- `python-dotenv` - Load .env variablesit (đã có trong `.gitignore`)
- Mỗi môi trường sẽ có database riêng
- Database schema tự động migrate khi có thay đổi (thêm cột `file_type`, `content`)

### Thư mục lưu files

- CV files: `cvs/` (tự động tạo)
- Cài lại dependencies
uv pip install -r requirements.txt

# Hoặc dùng pip
pip install -r requirements.txt
```

### Lỗi: OpenAI API key not found

```bash
# Kiểm tra file .env có tồn tại
cat .env

# Đảm bảo có OPENAI_API_KEY
echo "OPENAI_API_KEY=sk-..." > .env
```

### Lỗi: ChromaDB/SQLite permission denied

```bash
# Xóa database cũ và chạy lại
rm -rf db/files.db db/chroma_db/
uv run python main.py
```

### Lỗi: Port đã được sử dụng

```bash
# Thay đổi port
uv run uvicorn main:app --port 8001

# Hoặc kill process đang dùng port 8000
lsof -ti:8000 | xargs kill -9
```

### Cache không hoạt động

```bash
# Clear cache
uv run python -c "from db.vector_db import clear_cache; clear_cache(); print('✅ Cache cleared')"
```

### Performance chậm

- **Lần đầu**: Tạo embeddings + không có cache → ~300s
- **Lần 2+**: Có cache → ~10s
- Kiểm tra logs để xem cache hit/miss rate

## 📦 Dependencies

Xem file `requirements.txt` để biết danh sách đầy đủ dependencies:

- `fastapi>=0.128.0` - Web framework
- `uvicorn[standard]==0.24.0` - ASGI server
- `python-multipart==0.0.6` - Hỗ trợ file upload
- `openai>=1.54.0` - OpenAI API client cho CV matching
- `PyPDF2>=3.0.0` - Đọc và trích xuất text từ file PDF
- `python-docx>=1.1.0` - Đọc và trích xuất text từ file DOCX
- `python-dotenv>=1.0.0` - Đọc biến môi trường từ file `.env`

## 🎯 Tính năng chính

### 1. Upload và quản lý files

- Upload nhiều CV cùng lúc (PDF, DOCX, DOC)
- Upload JD (chỉ PDF, 1 file mỗi lần)
- Tự động trích xuất và lưu nội dung text từ CV vào database
- Tính toán hash SHA256 cho mỗi file
- Quản lý metadata (filename, size, content_type, upload time)

### 2. Đối chiếu CV với JD (AI Matching)

- Sử dụng OpenAI để đánh giá mức độ phù hợp giữa CV và JD
- Trả về điểm số (score 0-100) cho mỗi CV
- Liệt kê các yêu cầu đã đáp ứng và còn thiếu
- Hỗ trợ các tùy chọn nâng cao:
  - `cvPresentation`: Đánh giá độ chuyên nghiệp trong trình bày CV
  - `interviewQuestions`: Đề xuất câu hỏi phỏng vấn
  - `jobLeveling`: Đánh giá cấp bậc
  - `certBenefit`: Phân tích giá trị chứng chỉ

## 🐛 Troubleshooting

### Lỗi: Module not found

```bash
# Đảm bảo đã cài đặt dependencies
pip install -r requirements.txt
```

### Lỗi: Port đã được sử dụng

```bash
# Thay đổi port
uvicorn main:app --port 8001
```

### Lỗi: OPENAI_API_KEY không được tìm thấy

- Đảm bảo đã tạo file `.env` trong thư mục gốc của project
- Kiểm tra file `.env` có chứa `OPENAI_API_KEY=your_key_here`
- Lỗi này chỉ ảnh hưởng đến endpoint `/thinking`, các endpoint khác vẫn hoạt động bình thường

### Database không được tạo

- Database sẽ tự động được tạo khi ứng dụng khởi động
- Kiểm tra quyền ghi trong thư mục project
- Xem logs khi khởi động để biết thông tin chi tiết

### Lỗi khi trích xuất text từ CV

- Đảm bảo file PDF/DOCX không bị mã hóa hoặc bảo vệ
- Một số file PDF scan (ảnh) có thể không trích xuất được text
- File vẫn được lưu thành công, chỉ là không có nội dung text trong database

### Lỗi khi gọi OpenAI API

- Kiểm tra API key có hợp lệ và có đủ credit
- Kiểm tra model name trong `.env` (mặc định: `gpt-4o`)
- Xem logs trong console để biết chi tiết lỗi

## 📄 License

[Thêm license của bạn ở đây]

## 👥 Contributors

[Thêm contributors ở đây]
