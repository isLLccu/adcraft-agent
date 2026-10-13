from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class ImagePrompt(Base):
    __tablename__ = "image_prompts"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("ad_tasks.id", ondelete="CASCADE"), nullable=False)
    prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text)
    style = Column(String(50))
    ratio = Column(String(10))
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    task = relationship("AdTask", back_populates="image_prompts")
    materials = relationship("Material", back_populates="prompt")
