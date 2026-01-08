"""Cấu hình ứng dụng"""
from pathlib import Path
from dotenv import load_dotenv
import os

# Load biến môi trường từ file .env
load_dotenv()

# Thư mục lưu trữ files
JD_DIRECTORY = Path("jds")
CV_DIRECTORY = Path("cvs")

# Database
DATABASE_PATH = "db/files.db"

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validate API Key exists
if not OPENAI_API_KEY:
    raise ValueError("⚠️ OPENAI_API_KEY không được tìm thấy trong file .env!")
if OPENAI_API_KEY == "your_openai_api_key_here":
    raise ValueError("⚠️ Vui lòng thay thế OPENAI_API_KEY bằng key thật trong file .env!")

# OpenAI Models Configuration
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # Main model cho JD extraction
OPENAI_MINI_MODEL = os.getenv("OPENAI_MINI_MODEL", "gpt-4o-mini")  # Rẻ hơn cho CV extraction
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")  # Embedding model

# Tạo thư mục nếu chưa tồn tại
JD_DIRECTORY.mkdir(exist_ok=True)
CV_DIRECTORY.mkdir(exist_ok=True)

# CORS origins
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

