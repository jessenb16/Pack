"""Pydantic models for Family."""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class FamilyBase(BaseModel):
    """Base family model."""
    name: str


class FamilyCreate(FamilyBase):
    """Family creation model."""
    pass


class FamilyResponse(FamilyBase):
    """Family response model."""
    id: str
    members: List[str]
    event_types: List[str]
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

