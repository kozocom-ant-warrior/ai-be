"""Application configuration"""
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# File storage directories
JD_DIRECTORY = Path("jds")
CV_DIRECTORY = Path("cvs")

# Database
DATABASE_PATH = "db/files.db"

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validate API Key exists
if not OPENAI_API_KEY:
    raise ValueError("⚠️ OPENAI_API_KEY not found in .env file!")
if OPENAI_API_KEY == "your_openai_api_key_here":
    raise ValueError("⚠️ Please replace OPENAI_API_KEY with a real key in .env file!")

# OpenAI Models Configuration
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # Main model for JD extraction
OPENAI_MINI_MODEL = os.getenv("OPENAI_MINI_MODEL", "gpt-4o-mini")  # Cheaper for CV extraction
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")  # Embedding model

# Prompt Language Configuration
PROMPT_LANGUAGE = os.getenv("PROMPT_LANGUAGE", "en")  # vi, en, ja

# Create directories if they don't exist
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

