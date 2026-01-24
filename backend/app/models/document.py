"""Pydantic models for Document."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DocumentMetadata(BaseModel):
    """Document metadata."""
    sender_name: str
    event_type: str
    doc_date: str
    recipient_name: Optional[str] = None


class DocumentCreate(BaseModel):
    """Document creation model."""
    sender_name: str
    event_type: str
    doc_date: str


class DocumentResponse(BaseModel):
    """Document response model."""
    id: str
    family_id: str
    uploader_id: str
    metadata: DocumentMetadata
    file_type: str
    s3_original_url: str
    s3_thumbnail_url: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class DocumentFilter(BaseModel):
    """Document filter model."""
    sender: Optional[str] = None
    event_type: Optional[str] = None
    year: Optional[int] = None

