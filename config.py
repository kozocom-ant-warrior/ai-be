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
DATABASE_PATH = "files.db"

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

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

