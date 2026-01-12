"""
Main FastAPI Application
Entry point cho ứng dụng upload files
"""
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS
from db.database import init_database, get_all_files
from models import FileListResponse, FileResponse
from routers import jd, cv, thinking

app = FastAPI(
    title="File Upload API",
    description="API để upload file CV và JD (Job Description), lưu metadata vào SQLite",
    version="1.0.0"
)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký routers
app.include_router(jd.router)
app.include_router(cv.router)
app.include_router(thinking.router)


@app.on_event("startup")
async def startup_event():
    """Khởi tạo database khi ứng dụng khởi động"""
    init_database()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "File Upload API",
        "version": "1.0.0",
        "endpoints": {
            "all_files": {
                "list": "GET /files?type=cv|jd (optional)"
            },
            "jd": {
                "upload": "POST /jd/upload (chỉ upload 1 file)",
                "list": "GET /jd/files",
                "get": "GET /jd/files/{file_id}",
                "delete": "DELETE /jd/files/{file_id}"
            },
            "cv": {
                "upload": "POST /cv/upload (có thể upload nhiều file cùng lúc)",
                "list": "GET /cv/files",
                "get": "GET /cv/files/{file_id}",
                "view": "GET /cv/view/{file_id} (xem/tải file CV)",
                "content": "GET /cv/files/{file_id}/content (lấy nội dung text)",
                "delete": "DELETE /cv/files/{file_id}"
            },
            "thinking": {
                "dump": "POST /thinking (dump các giá trị từ client)"
            }
        }
    }


@app.get("/files", response_model=FileListResponse)
async def list_all_files(
    limit: int = Query(100, ge=1, le=1000, description="Số lượng files tối đa trả về"),
    offset: int = Query(0, ge=0, description="Số lượng files bỏ qua"),
    file_type: Optional[str] = Query(None, alias="type", description="Lọc theo loại file: 'jd' hoặc 'cv'. Để trống để lấy tất cả")
):
    """
    Lấy danh sách tất cả files đã upload
    
    Args:
        limit: Số lượng files tối đa trả về (mặc định: 100, tối đa: 1000)
        offset: Số lượng files bỏ qua (mặc định: 0)
        type: Lọc theo loại file - 'jd' hoặc 'cv'. Để trống để lấy tất cả files
    
    Returns:
        FileListResponse: Danh sách files và tổng số
    
    Note:
        - Endpoint này lấy tất cả files nếu không truyền tham số 'type'
        - Có thể filter theo type bằng cách truyền ?type=jd hoặc ?type=cv
        - Các endpoint /jd/files và /cv/files tự động filter theo type tương ứng
    """
    # Validate file_type nếu có
    if file_type and file_type not in ["jd", "cv"]:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Type phải là 'jd' hoặc 'cv'"
        )
    
    files, total = get_all_files(limit=limit, offset=offset, file_type=file_type)
    
    return FileListResponse(
        total=total,
        files=[FileResponse(**file) for file in files]
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

