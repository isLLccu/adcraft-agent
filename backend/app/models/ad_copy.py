from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class AdCopy(Base):
    __tablename__ = "ad_copies"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("ad_tasks.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200))
    body = Column(Text, nullable=False)
    slogan = Column(String(200))
    platform = Column(String(50), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    task = relationship("AdTask", back_populates="ad_copies")
    materials = relationship("Material", back_populates="copy")
