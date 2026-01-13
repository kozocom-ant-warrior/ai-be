"""Routes for CV upload"""
from pathlib import Path
from typing import List
import hashlib
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from fastapi.responses import Response
from config import CV_DIRECTORY
from db.database import save_file_to_database, get_file_by_id, get_all_files, delete_file_from_database
from models import FileResponse, FileListResponse
from utils import calculate_file_hash, generate_safe_filename, extract_text_from_file
from db import vector_db

router = APIRouter(prefix="/cv", tags=["CV"])


@router.post("/upload", response_model=FileListResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(files: List[UploadFile] = File(...)):
    """
    Upload multiple CV files (PDF or DOCX) to the cvs folder and save metadata to SQLite
    
    Args:
        files: List of files to upload (accepts PDF, DOCX or DOC)
              Can upload multiple files at once
    
    Returns:
        FileListResponse: List of information about uploaded files
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please select at least one file to upload"
        )
    
    uploaded_files = []
    failed_files = []
    
    for file in files:
        # Check file type
        if not file.filename:
            failed_files.append({"filename": "unknown", "error": "Filename cannot be empty"})
            continue
        
        # Check extension (accept PDF and DOCX)
        file_extension = Path(file.filename).suffix.lower()
        allowed_extensions = [".pdf", ".docx", ".doc"]
        if file_extension not in allowed_extensions:
            failed_files.append({
                "filename": file.filename,
                "error": f"Only PDF, DOCX or DOC files are accepted. File has extension: {file_extension}"
            })
            continue
        
        # Check content type
        if file.content_type:
            valid_content_types = ["pdf", "document", "msword", "wordprocessingml"]
            if not any(ct in file.content_type.lower() for ct in valid_content_types):
                failed_files.append({
                    "filename": file.filename,
                    "error": f"Invalid content type: {file.content_type}"
                })
                continue
        
        # Create safe filename
        original_filename = file.filename
        file_path = generate_safe_filename(original_filename, CV_DIRECTORY)
        
        try:
            # Save file to cvs folder
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Calculate file size and hash
            file_size = file_path.stat().st_size
            file_hash = calculate_file_hash(file_path)
            
            # Extract text content from CV (save RAW - no cleaning)
            content = None
            try:
                content = extract_text_from_file(file_path)
                # Print CV content for verification
                if content:
                    print(f"\n{'='*80}")
                    print(f"CV Content (RAW): {original_filename}")
                    print(f"{'='*80}")
                    print(content[:500])  # Print first 500 chars
                    print(f"... (total {len(content)} chars)")
                    print(f"{'='*80}\n")
                    
                    # ============================================
                    # DUPLICATE DETECTION: Check if CV already exists
                    # ============================================
                    content_hash = hashlib.md5(content.encode()).hexdigest()
                    doc_id = content_hash  # Same as vector_db doc_id format
                    
                    # Check ChromaDB embedding cache
                    try:
                        collection = vector_db._get_or_create_collection(vector_db.CV_COLLECTION_NAME)
                        existing_cv = collection.get(
                            ids=[doc_id],
                            include=["metadatas"]
                        )
                        
                        if existing_cv['ids'] and len(existing_cv['ids']) > 0:
                            # Found duplicate!
                            existing_metadata = existing_cv['metadatas'][0]
                            existing_filename = existing_metadata.get('filename', 'Unknown')
                            existing_file_id = existing_metadata.get('file_id', 'Unknown')
                            
                            # Delete the newly uploaded file
                            if file_path.exists():
                                file_path.unlink()
                            
                            # Return error with duplicate info
                            failed_files.append({
                                "filename": original_filename,
                                "error": f"⚠️ Duplicate CV! This file is 100% identical to '{existing_filename}' (file_id: {existing_file_id}) already in the system. Please check again."
                            })
                            print(f"🔍 Duplicate detected: {original_filename} === {existing_filename}")
                            continue  # Skip to next file
                    except Exception as e:
                        # If duplicate check fails, continue with upload (fail-safe)
                        print(f"Warning: Duplicate check failed for {original_filename}: {e}")
                    
                else:
                    print(f"Warning: Unable to extract content from file {original_filename}")
            except Exception as e:
                # If content extraction fails, continue saving file without content
                print(f"Warning: Unable to extract content from file {original_filename}: {str(e)}")
            
            # Save to database
            file_id = save_file_to_database(
                filename=file_path.name,
                original_filename=original_filename,
                file_path=str(file_path),
                file_size=file_size,
                file_hash=file_hash,
                content_type=file.content_type,
                file_type="cv",
                content=content
            )
            
            # Get saved file information
            file_info = get_file_by_id(file_id)
            if file_info:
                uploaded_files.append(FileResponse(**file_info))
        
        except Exception as e:
            # Delete file if error occurs when saving to database
            if file_path.exists():
                file_path.unlink()
            
            failed_files.append({
                "filename": original_filename,
                "error": f"Error uploading file: {str(e)}"
            })
    
    # If no files were uploaded successfully
    if not uploaded_files:
        error_details = "; ".join([f"{f['filename']}: {f['error']}" for f in failed_files])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No files were uploaded successfully. Errors: {error_details}"
        )
    
    # Return list of successfully uploaded files
    # If there are failed files, add information to response (can extend model later)
    return FileListResponse(
        total=len(uploaded_files),
        files=uploaded_files
    )


@router.get("/files", response_model=FileListResponse)
async def list_cv_files(limit: int = 100, offset: int = 0):
    """
    Get list of all uploaded CV files
    
    Args:
        limit: Maximum number of files to return (default: 100)
        offset: Number of files to skip (default: 0)
    
    Returns:
        FileListResponse: List of files and total count
    """
    files, total = get_all_files(limit=limit, offset=offset, file_type="cv")
    
    return FileListResponse(
        total=total,
        files=[FileResponse(**file) for file in files]
    )


@router.get("/view/{file_id}")
async def view_cv_file(file_id: int):
    """
    View CV file directly in browser by ID
    
    Args:
        file_id: CV file ID
    
    Returns:
        Response: File binary with headers to display directly in browser (inline)
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info or file_info.get("file_type") != "cv":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV file not found with ID: {file_id}"
        )
    
    file_path = Path(file_info["file_path"])
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File does not exist on system: {file_path}"
        )
    
    # Determine content type based on extension
    content_type = file_info.get("content_type")
    if not content_type:
        file_extension = file_path.suffix.lower()
        content_type_map = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword"
        }
        content_type = content_type_map.get(file_extension, "application/octet-stream")
    
    # Read file content
    with open(file_path, "rb") as f:
        file_content = f.read()
    
    # Set headers to display inline (not download)
    # Important: only set Content-Disposition: inline, not attachment
    headers = {
        "Content-Type": content_type,
        "Content-Disposition": "inline"
    }
    
    return Response(
        content=file_content,
        media_type=content_type,
        headers=headers
    )


@router.get("/files/{file_id}/content")
async def get_cv_content(file_id: int):
    """
    Get text content of CV file by ID
    
    Args:
        file_id: File ID
    
    Returns:
        dict: Text content of CV
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info or file_info.get("file_type") != "cv":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV file not found with ID: {file_id}"
        )
    
    content = file_info.get("content")
    
    return {
        "file_id": file_id,
        "filename": file_info.get("original_filename"),
        "content": content if content else "Content not available"
    }


@router.get("/files/{file_id}", response_model=FileResponse)
async def get_cv_file(file_id: int):
    """
    Get detailed information of a CV file by ID
    
    Args:
        file_id: File ID
    
    Returns:
        FileResponse: File information
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info or file_info.get("file_type") != "cv":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV file not found with ID: {file_id}"
        )
    
    return FileResponse(**file_info)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv_file(file_id: int):
    """
    Delete CV file and metadata from database
    
    Args:
        file_id: ID of file to delete
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info or file_info.get("file_type") != "cv":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV file not found with ID: {file_id}"
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

