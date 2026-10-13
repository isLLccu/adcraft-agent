from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MaterialResponse(BaseModel):
    id: int
    task_id: int
    product_id: int
    image_url: str
    copy_id: Optional[int] = None
    prompt_id: Optional[int] = None
    status: str
    is_favorite: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MaterialDetailResponse(MaterialResponse):
    """素材详情，包含关联的文案、Prompt、商品和任务信息"""
    copy: Optional[dict] = None
    prompt: Optional[dict] = None
    product: Optional[dict] = None
    task: Optional[dict] = None

    class Config:
        from_attributes = True


class MaterialFilter(BaseModel):
    product_id: Optional[int] = None
    platform: Optional[str] = None
    status: Optional[str] = None
    is_favorite: Optional[bool] = None


class MaterialUpdate(BaseModel):
    is_favorite: Optional[bool] = None
    status: Optional[str] = None


class MaterialStats(BaseModel):
    total: int
    active: int
    archived: int
    favorites: int


class MaterialBatchUpdate(BaseModel):
    material_ids: List[int]
    is_favorite: Optional[bool] = None
    status: Optional[str] = None
