from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime


class AuditIssue(BaseModel):
    type: str
    word: str
    suggestion: str


class AuditRequest(BaseModel):
    content: str
    content_type: str  # copy, prompt


class AuditResponse(BaseModel):
    passed: bool
    risk_level: str  # low, medium, high
    issues: List[Dict]
    suggestions: List[Dict]


class AuditResultResponse(BaseModel):
    id: int
    task_id: int
    content_type: str
    passed: bool
    risk_level: Optional[str] = None
    issues: Optional[List[Dict]] = None
    suggestions: Optional[List[Dict]] = None
    created_at: datetime

    class Config:
        from_attributes = True
