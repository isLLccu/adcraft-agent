from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ShopBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    industry: Optional[str] = Field(None, max_length=50)
    brand_style: Optional[str] = Field(None, max_length=100)
    target_audience: Optional[str] = Field(None, max_length=200)
    main_platform: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class ShopCreate(ShopBase):
    pass


class ShopUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    industry: Optional[str] = Field(None, max_length=50)
    brand_style: Optional[str] = Field(None, max_length=100)
    target_audience: Optional[str] = Field(None, max_length=200)
    main_platform: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class ShopResponse(ShopBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
