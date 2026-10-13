from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("ad_tasks.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    image_url = Column(String(500), nullable=False)
    copy_id = Column(Integer, ForeignKey("ad_copies.id", ondelete="SET NULL"))
    prompt_id = Column(Integer, ForeignKey("image_prompts.id", ondelete="SET NULL"))
    status = Column(String(20), default="active", nullable=False)  # active, archived
    is_favorite = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    task = relationship("AdTask", back_populates="materials")
    product = relationship("Product", back_populates="materials")
    copy = relationship("AdCopy", back_populates="materials")
    prompt = relationship("ImagePrompt", back_populates="materials")
