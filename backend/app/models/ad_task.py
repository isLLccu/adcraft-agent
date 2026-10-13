from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class AdTask(Base):
    __tablename__ = "ad_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(50), nullable=False)  # xiaohongshu, taobao, douyin, wechat
    ad_type = Column(String(50), nullable=False)  # new_product, promotion, festival, etc.
    style = Column(String(50))
    image_ratio = Column(String(10))  # 1:1, 3:4, 4:5, 9:16, 16:9
    copywriting_tone = Column(String(50))
    status = Column(String(20), default="pending", nullable=False)  # pending, processing, success, failed, cancelled
    error_message = Column(Text)
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="ad_tasks")
    shop = relationship("Shop", back_populates="ad_tasks")
    product = relationship("Product", back_populates="ad_tasks")
    ad_copies = relationship("AdCopy", back_populates="task", cascade="all, delete-orphan")
    image_prompts = relationship("ImagePrompt", back_populates="task", cascade="all, delete-orphan")
    materials = relationship("Material", back_populates="task", cascade="all, delete-orphan")
    audit_results = relationship("AuditResult", back_populates="task", cascade="all, delete-orphan")
    usage_logs = relationship("UsageLog", back_populates="task", cascade="all, delete-orphan")
