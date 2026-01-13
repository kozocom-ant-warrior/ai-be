"""Routes for JD (Job Description) upload"""
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from config import JD_DIRECTORY
from db.database import save_file_to_database, get_file_by_id, get_all_files, delete_file_from_database
from models import FileResponse, FileListResponse, JDTextRequest
from utils import calculate_file_hash, generate_safe_filename, extract_text_from_file

router = APIRouter(prefix="/jd", tags=["JD"])


@router.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_jd(file: UploadFile = File(...)):
    """
    Upload JD (Job Description) file to jds folder and save metadata to SQLite
    
    Note: Only accepts 1 file upload at a time
    
    Args:
        file: File to upload (only accepts PDF, only 1 file)
    
    Returns:
        FileResponse: Uploaded file information
    """
    # Check file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty"
        )
    
    # Check extension
    file_extension = Path(file.filename).suffix.lower()
    if file_extension != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PDF files are accepted. Your uploaded file has extension: {file_extension}"
        )
    
    # Check content type
    if file.content_type and "pdf" not in file.content_type.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type: {file.content_type}. Only PDF is accepted"
        )
    
    # Create safe filename
    original_filename = file.filename
    file_path = generate_safe_filename(original_filename, JD_DIRECTORY)
    
    try:
        # Save file to jds folder
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Calculate file size and hash
        file_size = file_path.stat().st_size
        file_hash = calculate_file_hash(file_path)
        
        # Extract text content from JD (CRITICAL: needed for embedding cache)
        # Save RAW content - only clean when creating embedding
        content = None
        try:
            content = extract_text_from_file(file_path)
            if content:
                print(f"\n{'='*80}")
                print(f"JD Content (RAW): {original_filename}")
                print(f"{'='*80}")
                print(content[:500])  # Print first 500 chars
                print(f"... (total {len(content)} chars)")
                print(f"{'='*80}\n")
            else:
                print(f"Warning: Unable to extract content from JD {original_filename}")
        except Exception as e:
            print(f"Warning: Unable to extract content from JD {original_filename}: {str(e)}")
        
        # Save to database
        file_id = save_file_to_database(
            filename=file_path.name,
            original_filename=original_filename,
            file_path=str(file_path),
            file_size=file_size,
            file_hash=file_hash,
            content_type=file.content_type,
            file_type="jd",
            content=content
        )
        
        # Get saved file information
        file_info = get_file_by_id(file_id)
        
        return FileResponse(**file_info)
    
    except Exception as e:
        # Delete file if error occurs when saving to database
        if file_path.exists():
            file_path.unlink()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}"
        )


@router.post("/text", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_jd_text(request: JDTextRequest):
    """
    Upload JD as text (no PDF file needed)
    
    Args:
        request: JDTextRequest containing jd_text and job_title (optional)
    
    Returns:
        FileResponse: Saved JD information
    """
    if not request.jd_text or not request.jd_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JD text cannot be empty"
        )
    
    try:
        # Save RAW text - only clean when creating embedding
        raw_content = request.jd_text.strip()
        
        # Create filename from job_title or timestamp
        if request.job_title:
            base_filename = request.job_title.replace(" ", "_").replace("/", "-")
        else:
            base_filename = "JD_Text"
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{base_filename}_{timestamp}.txt"
        file_path = JD_DIRECTORY / filename
        
        # Save text to .txt file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(raw_content)
        
        # Calculate file size and hash
        file_size = file_path.stat().st_size
        file_hash = calculate_file_hash(file_path)
        
        # Save to database with RAW content
        file_id = save_file_to_database(
            filename=filename,
            original_filename=filename,
            file_path=str(file_path),
            file_size=file_size,
            file_hash=file_hash,
            content_type="text/plain",
            file_type="jd",
            content=raw_content
        )
        
        # Get saved file information
        file_info = get_file_by_id(file_id)
        
        return FileResponse(**file_info)
    
    except Exception as e:
        # Delete file if error occurs
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving JD text: {str(e)}"
        )


@router.get("/files", response_model=FileListResponse)
async def list_jd_files(limit: int = 100, offset: int = 0):
    """
    Get list of all uploaded JD files
    
    Args:
        limit: Maximum number of files to return (default: 100)
        offset: Number of files to skip (default: 0)
    
    Returns:
        FileListResponse: List of files and total count
    """
    files, total = get_all_files(limit=limit, offset=offset, file_type="jd")
    
    return FileListResponse(
        total=total,
        files=[FileResponse(**file) for file in files]
    )


@router.get("/files/{file_id}", response_model=FileResponse)
async def get_jd_file(file_id: int):
    """
    Get detailed information of a JD file by ID
    
    Args:
        file_id: File ID
    
    Returns:
        FileResponse: File information
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info or file_info.get("file_type") != "jd":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"JD file not found with ID: {file_id}"
        )
    
    return FileResponse(**file_info)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_jd_file(file_id: int):
    """
    Delete JD file and metadata from database
    
    Args:
        file_id: ID of file to delete
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info or file_info.get("file_type") != "jd":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"JD file not found with ID: {file_id}"
        )
    
    # Delete file from filesystem
    file_path = Path(file_info["file_path"])
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error deleting file: {str(e)}"
            )
    
    # Delete from database
    deleted = delete_file_from_database(file_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting file from database"
        )
    
    return None

