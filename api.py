"""
API Upload File - FastAPI
Upload file PDF vào thư mục pdfs và lưu metadata vào SQLite
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import hashlib
from routers import thinking, cv, jd

app = FastAPI(
    title="PDF Upload API",
    description="API để upload file PDF vào thư mục pdfs và lưu metadata vào SQLite",
    version="1.0.0"
)

# Cấu hình CORS để cho phép requests từ ReactJS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # ReactJS development server mặc định
        "http://localhost:3001",
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8080",  # Vue.js dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        # Thêm domain production của bạn ở đây nếu cần
        # "https://yourdomain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Cho phép tất cả methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Cho phép tất cả headers
)

# Đăng ký routers
app.include_router(thinking.router)
app.include_router(cv.router)
app.include_router(jd.router)

# Cấu hình
PDF_DIRECTORY = Path("pdfs")
DATABASE_PATH = "files.db"

# Tạo thư mục pdfs nếu chưa tồn tại
PDF_DIRECTORY.mkdir(exist_ok=True)


# Database setup
def init_database():
    """Khởi tạo database SQLite và tạo bảng nếu chưa tồn tại"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL UNIQUE,
            file_size INTEGER NOT NULL,
            file_hash TEXT,
            content_type TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tạo index để tìm kiếm nhanh hơn
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_filename ON files(filename)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_uploaded_at ON files(uploaded_at)
    """)
    
    conn.commit()
    conn.close()
    print(f"✓ Database đã được khởi tạo: {DATABASE_PATH}")


# Models
class FileResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    file_hash: Optional[str]
    content_type: Optional[str]
    uploaded_at: str
    updated_at: str


class FileListResponse(BaseModel):
    total: int
    files: List[FileResponse]


def calculate_file_hash(file_path: Path) -> str:
    """Tính toán hash SHA256 của file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def save_file_to_database(
    filename: str,
    original_filename: str,
    file_path: str,
    file_size: int,
    file_hash: Optional[str] = None,
    content_type: Optional[str] = None
) -> int:
    """Lưu thông tin file vào database và trả về ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO files (
                filename, original_filename, file_path, file_size, 
                file_hash, content_type, uploaded_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            filename,
            original_filename,
            file_path,
            file_size,
            file_hash,
            content_type,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        file_id = cursor.lastrowid
        conn.commit()
        return file_id
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"File với đường dẫn '{file_path}' đã tồn tại trong database"
        )
    finally:
        conn.close()


def get_file_by_id(file_id: int) -> Optional[dict]:
    """Lấy thông tin file từ database theo ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_all_files(limit: int = 100, offset: int = 0) -> tuple[List[dict], int]:
    """Lấy danh sách tất cả files từ database"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Đếm tổng số files
    cursor.execute("SELECT COUNT(*) FROM files")
    total = cursor.fetchone()[0]
    
    # Lấy danh sách files
    cursor.execute("""
        SELECT * FROM files 
        ORDER BY uploaded_at DESC 
        LIMIT ? OFFSET ?
    """, (limit, offset))
    
    rows = cursor.fetchall()
    conn.close()
    
    files = [dict(row) for row in rows]
    return files, total


def delete_file_from_database(file_id: int) -> bool:
    """Xóa file từ database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted


# API Endpoints
@app.on_event("startup")
async def startup_event():
    """Khởi tạo database khi ứng dụng khởi động"""
    init_database()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "PDF Upload API",
        "version": "1.0.0",
        "endpoints": {
            "upload": "POST /upload",
            "list": "GET /files",
            "get": "GET /files/{file_id}",
            "delete": "DELETE /files/{file_id}"
        }
    }


@app.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload file PDF vào thư mục pdfs và lưu metadata vào SQLite
    
    Args:
        file: File cần upload (chỉ chấp nhận PDF)
    
    Returns:
        FileResponse: Thông tin file đã upload
    """
    # Kiểm tra loại file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên file không được để trống"
        )
    
    # Kiểm tra extension
    file_extension = Path(file.filename).suffix.lower()
    if file_extension != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ chấp nhận file PDF. File bạn upload có extension: {file_extension}"
        )
    
    # Kiểm tra content type
    if file.content_type and "pdf" not in file.content_type.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content type không hợp lệ: {file.content_type}. Chỉ chấp nhận PDF"
        )
    
    # Tạo tên file an toàn (tránh trùng lặp)
    original_filename = file.filename
    safe_filename = original_filename.replace(" ", "_")
    file_path = PDF_DIRECTORY / safe_filename
    
    # Nếu file đã tồn tại, thêm số vào tên
    counter = 1
    while file_path.exists():
        stem = Path(safe_filename).stem
        suffix = Path(safe_filename).suffix
        file_path = PDF_DIRECTORY / f"{stem}_{counter}{suffix}"
        counter += 1
    
    try:
        # Lưu file vào thư mục pdfs
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Tính toán file size và hash
        file_size = file_path.stat().st_size
        file_hash = calculate_file_hash(file_path)
        
        # Lưu vào database
        file_id = save_file_to_database(
            filename=file_path.name,
            original_filename=original_filename,
            file_path=str(file_path),
            file_size=file_size,
            file_hash=file_hash,
            content_type=file.content_type
        )
        
        # Lấy thông tin file vừa lưu
        file_info = get_file_by_id(file_id)
        
        return FileResponse(**file_info)
    
    except Exception as e:
        # Xóa file nếu có lỗi khi lưu vào database
        if file_path.exists():
            file_path.unlink()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi upload file: {str(e)}"
        )


@app.get("/files", response_model=FileListResponse)
async def list_files(limit: int = 100, offset: int = 0):
    """
    Lấy danh sách tất cả files đã upload
    
    Args:
        limit: Số lượng files tối đa trả về (mặc định: 100)
        offset: Số lượng files bỏ qua (mặc định: 0)
    
    Returns:
        FileListResponse: Danh sách files và tổng số
    """
    files, total = get_all_files(limit=limit, offset=offset)
    
    return FileListResponse(
        total=total,
        files=[FileResponse(**file) for file in files]
    )


@app.get("/files/{file_id}", response_model=FileResponse)
async def get_file(file_id: int):
    """
    Lấy thông tin chi tiết của một file theo ID
    
    Args:
        file_id: ID của file
    
    Returns:
        FileResponse: Thông tin file
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy file với ID: {file_id}"
        )
    
    return FileResponse(**file_info)


@app.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(file_id: int):
    """
    Xóa file và metadata từ database
    
    Args:
        file_id: ID của file cần xóa
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy file với ID: {file_id}"
        )
    
    # Xóa file từ filesystem
    file_path = Path(file_info["file_path"])
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi xóa file: {str(e)}"
            )
    
    # Xóa từ database
    deleted = delete_file_from_database(file_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi khi xóa file từ database"
        )
    
    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

