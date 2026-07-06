"""Pydantic models for Document."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class LabelRef(BaseModel):
    """Resolved org label (uuid id + display string)."""
    id: str
    label: str


class DocumentMetadata(BaseModel):
    """Document metadata returned by API (resolved labels)."""
    sender: LabelRef
    event_type: LabelRef
    recipient: Optional[LabelRef] = None
    doc_date: str
    caption: Optional[str] = None


class DocumentPageResponse(BaseModel):
    """Single page of a multi-image document (API response)."""
    page_number: int
    s3_original_url: str
    s3_thumbnail_url: str


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
    pages: Optional[List[DocumentPageResponse]] = None

    class Config:
        from_attributes = True


class DocumentMetadataPatch(BaseModel):
    """PATCH body: provide id OR label for sender/event; recipient optional."""
    sender_id: Optional[str] = None
    sender_label: Optional[str] = None
    event_type_id: Optional[str] = None
    event_type_label: Optional[str] = None
    recipient_id: Optional[str] = None
    recipient_label: Optional[str] = None
    doc_date: str
    caption: str
