from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class AuditResult(Base):
    __tablename__ = "audit_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("ad_tasks.id", ondelete="CASCADE"), nullable=False)
    content_type = Column(String(20), nullable=False)  # copy, prompt
    passed = Column(Boolean, nullable=False)
    risk_level = Column(String(20))  # low, medium, high
    issues = Column(JSON)  # List of issues
    suggestions = Column(JSON)  # List of suggestions
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    task = relationship("AdTask", back_populates="audit_results")
