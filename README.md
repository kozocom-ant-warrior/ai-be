# AI-BE - File Upload API

API để upload file CV và JD (Job Description), lưu metadata vào SQLite.

## 📋 Yêu cầu

- Python 3.8 trở lên
- pip (Python package manager)

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

Tạo file `.env` từ template:

```bash
cp .env.example .env
```

Sau đó chỉnh sửa file `.env` và thêm OpenAI API key của bạn:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-3.5-turbo
```

**Lưu ý:** File `.env` không được commit lên git (đã có trong `.gitignore`)

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
├── main.py              # Entry point chính của ứng dụng
├── config.py            # Cấu hình (thư mục, database, CORS)
├── database.py          # Database operations (SQLite)
├── models.py            # Pydantic models cho API responses
├── utils.py             # Utility functions
├── requirements.txt     # Python dependencies
├── routers/
│   ├── __init__.py
│   ├── cv.py           # Routes cho CV upload (hỗ trợ multiple files)
│   └── jd.py           # Routes cho JD upload (chỉ 1 file)
├── cvs/                # Thư mục lưu CV files (tự động tạo)
├── jds/                # Thư mục lưu JD files (tự động tạo)
└── files.db            # SQLite database (tự động tạo, không commit lên git)
```

## 🔌 API Endpoints

### JD (Job Description) - Chỉ upload 1 file

- `POST /jd/upload` - Upload JD file (PDF)
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

- Database SQLite tự động được tạo tại `files.db` khi ứng dụng khởi động
- File `files.db` không được commit lên git (đã có trong `.gitignore`)
- Mỗi môi trường sẽ có database riêng

### Thư mục lưu files

- CV files: `cvs/` (tự động tạo)
- JD files: `jds/` (tự động tạo)

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
