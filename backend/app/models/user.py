"""Pydantic models for User."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserResponse(BaseModel):
    """User response model."""
    id: str
    email: str
    name: str
    family_id: Optional[str] = None
    role: str
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

