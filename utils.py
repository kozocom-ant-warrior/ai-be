"""Utility functions"""
import hashlib
import re
from pathlib import Path
from typing import Optional
import PyPDF2
from docx import Document


def calculate_file_hash(file_path: Path) -> str:
    """Tính toán hash SHA256 của file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def generate_safe_filename(original_filename: str, directory: Path) -> Path:
    """Tạo tên file an toàn, tránh trùng lặp"""
    safe_filename = original_filename.replace(" ", "_")
    file_path = directory / safe_filename
    
    # Nếu file đã tồn tại, thêm số vào tên
    counter = 1
    while file_path.exists():
        stem = Path(safe_filename).stem
        suffix = Path(safe_filename).suffix
        file_path = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    
    return file_path


def extract_text_from_pdf(file_path: Path) -> str:
    """Trích xuất text từ file PDF"""
    try:
        text_content = []
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text_content.append(page.extract_text())
        return "\n".join(text_content)
    except Exception as e:
        raise Exception(f"Lỗi khi đọc PDF: {str(e)}")


def extract_text_from_docx(file_path: Path) -> str:
    """Trích xuất text từ file DOCX"""
    try:
        doc = Document(file_path)
        text_content = []
        for paragraph in doc.paragraphs:
            text_content.append(paragraph.text)
        return "\n".join(text_content)
    except Exception as e:
        raise Exception(f"Lỗi khi đọc DOCX: {str(e)}")


def extract_text_from_file(file_path: Path) -> Optional[str]:
    """Trích xuất text từ file PDF hoặc DOCX dựa vào extension"""
    file_extension = file_path.suffix.lower()
    
    if file_extension == ".pdf":
        return extract_text_from_pdf(file_path)
    elif file_extension in [".docx", ".doc"]:
        return extract_text_from_docx(file_path)
    else:
        return None


def clean_text_for_embedding(text: str) -> str:
    """
    Làm sạch text trước khi tạo embedding:
    - Loại bỏ emoji
    - Loại bỏ ký tự đặc biệt không phải chữ cái, số, khoảng trắng
    - Chuẩn hóa khoảng trắng
    
    Args:
        text: Text cần làm sạch
        
    Returns:
        str: Text đã được làm sạch
    """
    if not text:
        return ""
    
    # Remove emoji và ký tự Unicode đặc biệt
    # Regex pattern để loại bỏ emoji
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", 
        flags=re.UNICODE
    )
    text = emoji_pattern.sub(r'', text)
    
    # Loại bỏ các ký tự control characters
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
    
    # Chuẩn hóa khoảng trắng: nhiều space/tab/newline → single space
    text = re.sub(r'\s+', ' ', text)
    
    # Trim leading/trailing whitespace
    text = text.strip()
    
    return text

