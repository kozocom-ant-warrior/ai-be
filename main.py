"""
Main FastAPI Application
Entry point for file upload application
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
    description="API for uploading CV and JD (Job Description) files, storing metadata in SQLite",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(jd.router)
app.include_router(cv.router)
app.include_router(thinking.router)


@app.on_event("startup")
async def startup_event():
    """Initialize database when application starts"""
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
                "upload": "POST /jd/upload (upload 1 file only)",
                "list": "GET /jd/files",
                "get": "GET /jd/files/{file_id}",
                "delete": "DELETE /jd/files/{file_id}"
            },
            "cv": {
                "upload": "POST /cv/upload (can upload multiple files at once)",
                "list": "GET /cv/files",
                "get": "GET /cv/files/{file_id}",
                "view": "GET /cv/view/{file_id} (view/download CV file)",
                "content": "GET /cv/files/{file_id}/content (get text content)",
                "delete": "DELETE /cv/files/{file_id}"
            },
            "thinking": {
                "dump": "POST /thinking (dump values from client)"
            }
        }
    }


@app.get("/files", response_model=FileListResponse)
async def list_all_files(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of files to return"),
    offset: int = Query(0, ge=0, description="Number of files to skip"),
    file_type: Optional[str] = Query(None, alias="type", description="Filter by file type: 'jd' or 'cv'. Leave empty to get all")
):
    """
    Get list of all uploaded files
    
    Args:
        limit: Maximum number of files to return (default: 100, max: 1000)
        offset: Number of files to skip (default: 0)
        type: Filter by file type - 'jd' or 'cv'. Leave empty to get all files
    
    Returns:
        FileListResponse: List of files and total count
    
    Note:
        - This endpoint gets all files if 'type' parameter is not provided
        - Can filter by type using ?type=jd or ?type=cv
        - The /jd/files and /cv/files endpoints automatically filter by respective type
    """
    # Validate file_type if provided
    if file_type and file_type not in ["jd", "cv"]:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Type must be 'jd' or 'cv'"
        )
    
    files, total = get_all_files(limit=limit, offset=offset, file_type=file_type)
    
    return FileListResponse(
        total=total,
        files=[FileResponse(**file) for file in files]
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

