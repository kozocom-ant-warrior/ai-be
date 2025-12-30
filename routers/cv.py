"""Routes cho CV upload"""
from pathlib import Path
from typing import List
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from config import CV_DIRECTORY
from database import save_file_to_database, get_file_by_id, get_all_files, delete_file_from_database
from models import FileResponse, FileListResponse
from utils import calculate_file_hash, generate_safe_filename, extract_text_from_file

router = APIRouter(prefix="/cv", tags=["CV"])


@router.post("/upload", response_model=FileListResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(files: List[UploadFile] = File(...)):
    """
    Upload nhiều file CV (PDF hoặc DOCX) vào thư mục cvs và lưu metadata vào SQLite
    
    Args:
        files: Danh sách files cần upload (chấp nhận PDF, DOCX hoặc DOC)
              Có thể upload nhiều file cùng lúc
    
    Returns:
        FileListResponse: Danh sách thông tin các file đã upload
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn ít nhất một file để upload"
        )
    
    uploaded_files = []
    failed_files = []
    
    for file in files:
        # Kiểm tra loại file
        if not file.filename:
            failed_files.append({"filename": "unknown", "error": "Tên file không được để trống"})
            continue
        
        # Kiểm tra extension (chấp nhận PDF và DOCX)
        file_extension = Path(file.filename).suffix.lower()
        allowed_extensions = [".pdf", ".docx", ".doc"]
        if file_extension not in allowed_extensions:
            failed_files.append({
                "filename": file.filename,
                "error": f"Chỉ chấp nhận file PDF, DOCX hoặc DOC. File có extension: {file_extension}"
            })
            continue
        
        # Kiểm tra content type
        if file.content_type:
            valid_content_types = ["pdf", "document", "msword", "wordprocessingml"]
            if not any(ct in file.content_type.lower() for ct in valid_content_types):
                failed_files.append({
                    "filename": file.filename,
                    "error": f"Content type không hợp lệ: {file.content_type}"
                })
                continue
        
        # Tạo tên file an toàn
        original_filename = file.filename
        file_path = generate_safe_filename(original_filename, CV_DIRECTORY)
        
        try:
            # Lưu file vào thư mục cvs
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Tính toán file size và hash
            file_size = file_path.stat().st_size
            file_hash = calculate_file_hash(file_path)
            
            # Trích xuất nội dung text từ CV
            content = None
            try:
                content = extract_text_from_file(file_path)
                # In ra nội dung content CV để kiểm tra
                if content:
                    print(f"\n{'='*80}")
                    print(f"Nội dung CV: {original_filename}")
                    print(f"{'='*80}")
                    print(content)
                    print(f"{'='*80}\n")
                else:
                    print(f"Warning: Không thể trích xuất nội dung từ file {original_filename}")
            except Exception as e:
                # Nếu không extract được content, vẫn tiếp tục lưu file nhưng không có content
                print(f"Warning: Không thể trích xuất nội dung từ file {original_filename}: {str(e)}")
            
            # Lưu vào database
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
            
            # Lấy thông tin file vừa lưu
            file_info = get_file_by_id(file_id)
            if file_info:
                uploaded_files.append(FileResponse(**file_info))
        
        except Exception as e:
            # Xóa file nếu có lỗi khi lưu vào database
            if file_path.exists():
                file_path.unlink()
            
            failed_files.append({
                "filename": original_filename,
                "error": f"Lỗi khi upload file: {str(e)}"
            })
    
    # Nếu không có file nào upload thành công
    if not uploaded_files:
        error_details = "; ".join([f"{f['filename']}: {f['error']}" for f in failed_files])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không có file nào được upload thành công. Lỗi: {error_details}"
        )
    
    # Trả về danh sách files đã upload thành công
    # Nếu có file lỗi, thêm thông tin vào response (có thể mở rộng model sau)
    return FileListResponse(
        total=len(uploaded_files),
        files=uploaded_files
    )


@router.get("/files", response_model=FileListResponse)
async def list_cv_files(limit: int = 100, offset: int = 0):
    """
    Lấy danh sách tất cả CV files đã upload
    
    Args:
        limit: Số lượng files tối đa trả về (mặc định: 100)
        offset: Số lượng files bỏ qua (mặc định: 0)
    
    Returns:
        FileListResponse: Danh sách files và tổng số
    """
    files, total = get_all_files(limit=limit, offset=offset, file_type="cv")
    
    return FileListResponse(
        total=total,
        files=[FileResponse(**file) for file in files]
    )


@router.get("/files/{file_id}", response_model=FileResponse)
async def get_cv_file(file_id: int):
    """
    Lấy thông tin chi tiết của một CV file theo ID
    
    Args:
        file_id: ID của file
    
    Returns:
        FileResponse: Thông tin file
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info or file_info.get("file_type") != "cv":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy CV file với ID: {file_id}"
        )
    
    return FileResponse(**file_info)


@router.get("/files/{file_id}/content")
async def get_cv_content(file_id: int):
    """
    Lấy nội dung text của CV file theo ID
    
    Args:
        file_id: ID của file
    
    Returns:
        dict: Nội dung text của CV
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info or file_info.get("file_type") != "cv":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy CV file với ID: {file_id}"
        )
    
    content = file_info.get("content")
    
    return {
        "file_id": file_id,
        "filename": file_info.get("original_filename"),
        "content": content if content else "Nội dung không có sẵn"
    }


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv_file(file_id: int):
    """
    Xóa CV file và metadata từ database
    
    Args:
        file_id: ID của file cần xóa
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info or file_info.get("file_type") != "cv":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy CV file với ID: {file_id}"
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

