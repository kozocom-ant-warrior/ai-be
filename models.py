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

