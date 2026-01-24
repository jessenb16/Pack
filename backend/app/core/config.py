"""Configuration for FastAPI backend."""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    APP_NAME: str = "Pack API"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # MongoDB
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "pack")
    
    # AWS S3
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_S3_BUCKET_NAME: str = os.getenv("AWS_S3_BUCKET_NAME", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Clerk Authentication
    CLERK_SECRET_KEY: str = os.getenv("CLERK_SECRET_KEY", "")
    CLERK_PUBLISHABLE_KEY: str = os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "")
    CLERK_FRONTEND_API: Optional[str] = os.getenv("NEXT_PUBLIC_CLERK_FRONTEND_API", "")
    
    # File Upload
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # 16MB
    ALLOWED_EXTENSIONS: set = {"png", "jpg", "jpeg", "gif", "pdf", "jfif", "webp"}
    
    # Frontend
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        # Allow extra fields from environment (needed for NEXT_PUBLIC_ prefixed vars)
        extra = "ignore"


settings = Settings()

