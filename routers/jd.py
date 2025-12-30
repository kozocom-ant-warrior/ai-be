"""Routes cho JD (Job Description) upload"""
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from config import JD_DIRECTORY
from database import save_file_to_database, get_file_by_id, get_all_files, delete_file_from_database
from models import FileResponse, FileListResponse
from utils import calculate_file_hash, generate_safe_filename

router = APIRouter(prefix="/jd", tags=["JD"])


@router.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_jd(file: UploadFile = File(...)):
    """
    Upload file JD (Job Description) vào thư mục jds và lưu metadata vào SQLite
    
    Lưu ý: Chỉ chấp nhận upload 1 file tại một thời điểm
    
    Args:
        file: File cần upload (chỉ chấp nhận PDF, chỉ 1 file)
    
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
    
    # Tạo tên file an toàn
    original_filename = file.filename
    file_path = generate_safe_filename(original_filename, JD_DIRECTORY)
    
    try:
        # Lưu file vào thư mục jds
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
            content_type=file.content_type,
            file_type="jd"
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


@router.get("/files", response_model=FileListResponse)
async def list_jd_files(limit: int = 100, offset: int = 0):
    """
    Lấy danh sách tất cả JD files đã upload
    
    Args:
        limit: Số lượng files tối đa trả về (mặc định: 100)
        offset: Số lượng files bỏ qua (mặc định: 0)
    
    Returns:
        FileListResponse: Danh sách files và tổng số
    """
    files, total = get_all_files(limit=limit, offset=offset, file_type="jd")
    
    return FileListResponse(
        total=total,
        files=[FileResponse(**file) for file in files]
    )


@router.get("/files/{file_id}", response_model=FileResponse)
async def get_jd_file(file_id: int):
    """
    Lấy thông tin chi tiết của một JD file theo ID
    
    Args:
        file_id: ID của file
    
    Returns:
        FileResponse: Thông tin file
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info or file_info.get("file_type") != "jd":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy JD file với ID: {file_id}"
        )
    
    return FileResponse(**file_info)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_jd_file(file_id: int):
    """
    Xóa JD file và metadata từ database
    
    Args:
        file_id: ID của file cần xóa
    """
    file_info = get_file_by_id(file_id)
    
    if not file_info or file_info.get("file_type") != "jd":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy JD file với ID: {file_id}"
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

