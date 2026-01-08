# AI-BE - CV-JD Matching API

API để upload file CV và JD (Job Description), phân tích matching score bằng AI (OpenAI GPT), và vector similarity (ChromaDB).

## 📋 Yêu cầu

- **Python 3.8+** (khuyến nghị 3.11+)
- **pip** hoặc **uv** (Python package manager)
- **OS**: Linux, Windows, macOS

## 🚀 Hướng dẫn cài đặt và chạy

### 1. Clone repository

```bash
git clone <repository-url>
cd ai-be
```

### 2. Cài đặt dependencies

**Linux / Windows:**

```bash
# Sử dụng pip
pip install -r requirements.txt

# Hoặc nếu dùng Python 3 cụ thể
python3 -m pip install -r requirements.txt
```

**macOS (khuyến nghị sử dụng uv):**

```bash
# Bước 1: Cài đặt uv (package manager hiện đại, nhanh hơn pip)
brew install uv
# hoặc: curl -LsSf https://astral.sh/uv/install.sh | sh

# Bước 2: Cài dependencies
uv pip install -r requirements.txt
```

> **Lưu ý macOS**: `uv` giúp quản lý Python version tự động và cài packages nhanh hơn pip rất nhiều. Tuy nhiên, bạn vẫn có thể dùng `pip` như Linux/Windows.

### 3. Cấu hình biến môi trường

Tạo file `.env` trong thư mục gốc project:

```bash
# Linux/macOS
touch .env

# Windows
type nul > .env
```

Sau đó chỉnh sửa file `.env` và thêm OpenAI API key:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
OPENAI_MINI_MODEL=gpt-4o-mini
```

**Lưu ý:** 
- File `.env` không được commit lên git (đã có trong `.gitignore`)
- Sử dụng `gpt-4o` cho độ chính xác cao, `gpt-4o-mini` cho tiết kiệm chi phí

### 4. Chạy ứng dụng

**Linux / Windows:**

```bash
# Chạy trực tiếp
python3 main.py

# Hoặc dùng uvicorn với auto-reload (development)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**macOS (với uv):**

```bash
# Chạy với uv (tự động quản lý Python version)
uv run python main.py

# Hoặc dùng uvicorn với auto-reload (development)
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Tham số uvicorn:**
- `--reload`: Tự động reload khi có thay đổi code (chỉ dùng cho development)
- `--host 0.0.0.0`: Cho phép truy cập từ bất kỳ địa chỉ IP nào
- `--port 8000`: Port mặc định

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

- `POST /thinking/` - **Matching CVs với JD bằng AI (THREE-STAGE HYBRID)**
  - Input: JD text, response requirements, advanced options
  - Output: Ranked CVs với scores, matched/missing requirements, advanced features
  - Features:
    - **Stage 1A**: Extract JD requirements (gpt-4o)
    - **Stage 1B**: Extract CV data (gpt-4o-mini, batch processing)
    - **Stage 2**: Deterministic scoring (no API cost)
    - **Stage 3**: Advanced features (conditional, cached)
  - Advanced Options:
    - `detectDuplicate`: Phát hiện CV trùng lặp/giả mạo
    - `cvPresentation`: Đánh giá độ chuyên nghiệp CV
    - `interviewQuestions`: Gợi ý câu hỏi phỏng vấn
    - `suggestOtherRoles`: Đề xuất vị trí phù hợp hơn
    - `certBenefit`: Phân tích certificate ↔ benefits

### 📄 JD (Job Description) - Chỉ upload 1 file

- `POST /jd/upload` - Upload JD file (PDF)
- `GET /jd/files` - Danh sách JD files
- `GET /jd/files/{file_id}` - Chi tiết JD file
- `DELETE /jd/files/{file_id}` - Xóa JD file

### 📝 CV - Có thể upload nhiều file

- `POST /cv/upload` - Upload CV files (PDF, DOCX, DOC) - **Có thể upload nhiều file cùng lúc**
- `GET /cv/files` - Danh sách CV files
- `GET /cv/files/{file_id}` - Chi tiết CV file
- `DELETE /cv/files/{file_id}` - Xóa CV file

### 📊POST /jd/upload` - Upload JD file (PDF)
- `GET /jd/files` - Danh sách JD files
- `GET /jd/files/{file_id}` - Chi tiết JD file
- `DELETE /jd/files/{file_id}` - Xóa JD file

### CV - Có thể upload nhiều file

- `POST /cv/upload` - Upload CV files (PDF, DOCX, DOC) - **Có thể upload nhiều file cùng lúc**
- `GET /cv/files` - Danh sách CV files
- `GET /cv/files/{file_id}` - Chi tiết CV file
- `DELETE /cv/files/{file_id}` - Xóa CV file

### Chung

- `GET /` - Thông tin API và danh sách endpoints
- `GET /files` - Lấy tất cả files (có thể filter `?type=jd` hoặc `?type=cv`)

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
curl "http://localhost:8000/cv/files"
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
```

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

- `fastapi` - Web framework
- `uvicorn[standard]` - ASGI server
- `python-multipart` - Hỗ trợ file upload

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

### Database không được tạo

- Database sẽ tự động được tạo khi ứng dụng khởi động
- Kiểm tra quyền ghi trong thư mục project
- Xem logs khi khởi động để biết thông tin chi tiết

## 📄 License

[Thêm license của bạn ở đây]

## 👥 Contributors

[Thêm contributors ở đây]
