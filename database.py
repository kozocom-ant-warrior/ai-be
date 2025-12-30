"""Database operations"""
import sqlite3
from datetime import datetime
from typing import Optional, List
from fastapi import HTTPException, status
from config import DATABASE_PATH


def _column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    """Kiểm tra xem cột có tồn tại trong bảng không"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def init_database():
    """Khởi tạo database SQLite và tạo bảng nếu chưa tồn tại"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Bảng files cho cả JD và CV
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL UNIQUE,
            file_size INTEGER NOT NULL,
            file_hash TEXT,
            content_type TEXT,
            file_type TEXT,
            content TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Migration: Thêm cột file_type nếu chưa có (cho database cũ)
    if not _column_exists(cursor, "files", "file_type"):
        try:
            cursor.execute("ALTER TABLE files ADD COLUMN file_type TEXT")
            print("✓ Đã thêm cột file_type vào bảng files")
        except sqlite3.OperationalError as e:
            print(f"Warning: Không thể thêm cột file_type: {e}")
    
    # Migration: Thêm cột content nếu chưa có (cho database cũ)
    if not _column_exists(cursor, "files", "content"):
        try:
            cursor.execute("ALTER TABLE files ADD COLUMN content TEXT")
            print("✓ Đã thêm cột content vào bảng files")
        except sqlite3.OperationalError as e:
            print(f"Warning: Không thể thêm cột content: {e}")
    
    # Tạo index để tìm kiếm nhanh hơn
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_filename ON files(filename)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_uploaded_at ON files(uploaded_at)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_type ON files(file_type)
    """)
    
    conn.commit()
    conn.close()
    print(f"✓ Database đã được khởi tạo: {DATABASE_PATH}")


def save_file_to_database(
    filename: str,
    original_filename: str,
    file_path: str,
    file_size: int,
    file_hash: Optional[str] = None,
    content_type: Optional[str] = None,
    file_type: Optional[str] = None,
    content: Optional[str] = None
) -> int:
    """Lưu thông tin file vào database và trả về ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO files (
                filename, original_filename, file_path, file_size, 
                file_hash, content_type, file_type, content, uploaded_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            filename,
            original_filename,
            file_path,
            file_size,
            file_hash,
            content_type,
            file_type,
            content,
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


def get_all_files(
    limit: int = 100, 
    offset: int = 0, 
    file_type: Optional[str] = None
) -> tuple[List[dict], int]:
    """Lấy danh sách tất cả files từ database"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Đếm tổng số files
    if file_type:
        cursor.execute("SELECT COUNT(*) FROM files WHERE file_type = ?", (file_type,))
    else:
        cursor.execute("SELECT COUNT(*) FROM files")
    total = cursor.fetchone()[0]
    
    # Lấy danh sách files
    if file_type:
        cursor.execute("""
            SELECT * FROM files 
            WHERE file_type = ?
            ORDER BY uploaded_at DESC 
            LIMIT ? OFFSET ?
        """, (file_type, limit, offset))
    else:
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

