from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(50))
    price = Column(Numeric(10, 2))
    description = Column(Text)
    selling_points = Column(JSON)  # List of selling points
    target_audience = Column(String(200))
    usage_scenario = Column(String(200))
    image_url = Column(String(500))
    tags = Column(JSON)  # List of tags
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    shop = relationship("Shop", back_populates="products")
    ad_tasks = relationship("AdTask", back_populates="product", cascade="all, delete-orphan")
    materials = relationship("Material", back_populates="product", cascade="all, delete-orphan")
