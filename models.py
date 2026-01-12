"""Pydantic models cho API responses"""
from typing import Optional, List
from pydantic import BaseModel


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
    file_type: Optional[str] = None  # 'jd' hoặc 'cv'
    content: Optional[str] = None  # Nội dung text của file


class FileListResponse(BaseModel):
    total: int
    files: List[FileResponse]


class JDTextRequest(BaseModel):
    """Model cho JD dạng text input"""
    jd_text: str
    job_title: Optional[str] = None  # Tên vị trí tuyển dụng (optional)
    
    class Config:
        json_schema_extra = {
            "example": {
                "jd_text": "We are looking for a Senior Frontend Developer with 5+ years experience in React...",
                "job_title": "Senior Frontend Developer"
            }
        }

