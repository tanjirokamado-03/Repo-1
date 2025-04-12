# models.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class TagWithConfidence(BaseModel):
    """Tag with confidence score and optional color"""
    name: str
    confidence: float = 1.0
    color: Optional[str] = None

class Email(BaseModel):
    """Basic email model"""
    sender: str
    subject: str
    body: str
    date: str
    summary: str = ""  # Will be added later
    
class EmailModel(BaseModel):
    """Enhanced email model for API responses"""
    id: str
    from_: str = Field(..., alias="from")
    subject: str
    summary: str
    date: str
    tags: List[TagWithConfidence] = []
    unread: bool = True

class SmartReply(BaseModel):
    """Model for smart reply suggestions"""
    text: str
    context: Optional[str] = None

class FilterOptions(BaseModel):
    """Options for filtering emails"""
    tag: Optional[str] = None
    unread_only: bool = False
    sort_by: str = "date"  # One of: "date", "sender", "subject"
    sort_order: str = "desc"  # One of: "asc", "desc"
