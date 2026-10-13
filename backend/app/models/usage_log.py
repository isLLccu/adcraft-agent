from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("ad_tasks.id", ondelete="CASCADE"))
    model_name = Column(String(50), nullable=False)
    token_usage = Column(Integer)
    image_count = Column(Integer)
    estimated_cost = Column(Numeric(10, 4))
    latency_ms = Column(Integer)
    success = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="usage_logs")
    task = relationship("AdTask", back_populates="usage_logs")
