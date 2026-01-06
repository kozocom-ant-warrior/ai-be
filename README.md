# AI-BE - File Upload API với CV Matching

API để upload file CV và JD (Job Description), lưu metadata vào SQLite, và đối chiếu CV với JD sử dụng OpenAI.

## 📋 Yêu cầu

- Python 3.8 trở lên
- pip (Python package manager)
- OpenAI API key (để sử dụng tính năng đối chiếu CV với JD)

## 🚀 Hướng dẫn cài đặt và chạy

### 1. Clone repository

```bash
git clone <repository-url>
cd ai-be
```

### 2. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

Hoặc nếu dùng Python 3 cụ thể:

```bash
python3 -m pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường

Tạo file `.env` trong thư mục gốc của project:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
```

**Lưu ý:** 
- File `.env` không được commit lên git (đã có trong `.gitignore`)
- `OPENAI_API_KEY` là bắt buộc nếu muốn sử dụng tính năng đối chiếu CV với JD
- `OPENAI_MODEL` mặc định là `gpt-4o` nếu không được chỉ định

### 4. Chạy ứng dụng

**Cách 1: Chạy trực tiếp**

```bash
python3 main.py
```

**Cách 2: Sử dụng uvicorn (khuyến nghị cho development)**

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- `--reload`: Tự động reload khi có thay đổi code (chỉ dùng cho development)
- `--host 0.0.0.0`: Cho phép truy cập từ bất kỳ địa chỉ IP nào
- `--port 8000`: Port mặc định

### 5. Truy cập API

Sau khi chạy, API sẽ có sẵn tại:

- **API Base URL**: `http://localhost:8000`
- **API Documentation (Swagger UI)**: `http://localhost:8000/docs`
- **API Documentation (ReDoc)**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

## 📁 Cấu trúc project

```
ai-be/
├── main.py              # Entry point chính của ứng dụng FastAPI
├── config.py            # Cấu hình (thư mục, database, CORS, OpenAI)
├── database.py          # Database operations (SQLite)
├── models.py            # Pydantic models cho API responses
├── utils.py             # Utility functions (hash, text extraction)
├── prompts.py           # OpenAI prompt templates cho CV matching
├── requirements.txt     # Python dependencies
├── routers/
│   ├── __init__.py
│   ├── cv.py           # Routes cho CV upload (hỗ trợ multiple files)
│   ├── jd.py           # Routes cho JD upload (chỉ 1 file)
│   └── thinking.py     # Routes cho đối chiếu CV với JD (OpenAI)
├── cvs/                # Thư mục lưu CV files (tự động tạo)
├── jds/                # Thư mục lưu JD files (tự động tạo)
└── files.db            # SQLite database (tự động tạo, không commit lên git)
```

## 🔌 API Endpoints

### JD (Job Description) - Chỉ upload 1 file

- `POST /jd/upload` - Upload JD file (chỉ PDF)
- `GET /jd/files` - Danh sách JD files (có pagination: `?limit=100&offset=0`)
- `GET /jd/files/{file_id}` - Chi tiết JD file
- `DELETE /jd/files/{file_id}` - Xóa JD file

### CV - Có thể upload nhiều file

- `POST /cv/upload` - Upload CV files (PDF, DOCX, DOC) - **Có thể upload nhiều file cùng lúc**
- `GET /cv/files` - Danh sách CV files (có pagination: `?limit=100&offset=0`)
- `GET /cv/files/{file_id}` - Chi tiết CV file
- `GET /cv/files/{file_id}/content` - Lấy nội dung text đã trích xuất từ CV
- `DELETE /cv/files/{file_id}` - Xóa CV file

### Đối chiếu CV với JD (Thinking)

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
  -F "advanced_options={\"detectDuplicate\":true,\"cvPresentation\":true,\"interviewQuestions\":true}"
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
      "suggested_roles": null,
      "cert_comment": "Nhận xét về chứng chỉ..."
    }
  ],
  "total_cvs_processed": 10,
  "total_cvs_matched": 5
}
```

**Lưu ý:**
- Các field như `duplicate_warning`, `cv_presentation_comment`, `interview_questions`, `suggested_roles`, `cert_comment` chỉ xuất hiện khi được bật trong `advanced_options`
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

- Database SQLite tự động được tạo tại `files.db` khi ứng dụng khởi động
- File `files.db` không được commit lên git (đã có trong `.gitignore`)
- Mỗi môi trường sẽ có database riêng
- Database schema tự động migrate khi có thay đổi (thêm cột `file_type`, `content`)

### Thư mục lưu files

- CV files: `cvs/` (tự động tạo)
- JD files: `jds/` (tự động tạo)

### OpenAI Configuration

- Cấu hình OpenAI API key trong file `.env`: `OPENAI_API_KEY`
- Model mặc định: `gpt-4o` (có thể thay đổi bằng biến `OPENAI_MODEL` trong `.env`)
- Sử dụng cho tính năng đối chiếu CV với JD tại endpoint `/thinking`

## 🔧 Development

### Chạy với auto-reload

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Kiểm tra code

```bash
# Kiểm tra import
python3 -c "from main import app; print('✓ Import thành công!')"
```

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
  - `detectDuplicate`: Phát hiện CV trùng lặp/giả mạo
  - `cvPresentation`: Đánh giá độ chuyên nghiệp trong trình bày CV
  - `interviewQuestions`: Đề xuất câu hỏi phỏng vấn
  - `suggestOtherRoles`: Gợi ý vị trí khác phù hợp
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
