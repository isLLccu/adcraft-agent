from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: Optional[str] = Field(None, max_length=50)
    price: Optional[Decimal] = None
    description: Optional[str] = None
    selling_points: Optional[List[str]] = None
    target_audience: Optional[str] = Field(None, max_length=200)
    usage_scenario: Optional[str] = Field(None, max_length=200)
    tags: Optional[List[str]] = None


class ProductCreate(ProductBase):
    shop_id: int


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = Field(None, max_length=50)
    price: Optional[Decimal] = None
    description: Optional[str] = None
    selling_points: Optional[List[str]] = None
    target_audience: Optional[str] = Field(None, max_length=200)
    usage_scenario: Optional[str] = Field(None, max_length=200)
    tags: Optional[List[str]] = None


class ProductResponse(ProductBase):
    id: int
    shop_id: int
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
