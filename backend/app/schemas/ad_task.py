from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Platform(str, Enum):
    XIAOHONGSHU = "xiaohongshu"
    TAOBAO = "taobao"
    DOUYIN = "douyin"
    WECHAT = "wechat"


class AdType(str, Enum):
    NEW_PRODUCT = "new_product"
    PROMOTION = "promotion"
    FESTIVAL = "festival"
    SEED_NOTE = "seed_note"
    MAIN_IMAGE = "main_image"
    ACTIVITY_POSTER = "activity_poster"


class ImageRatio(str, Enum):
    SQUARE = "1:1"
    PORTRAIT_3_4 = "3:4"
    PORTRAIT_4_5 = "4:5"
    VERTICAL = "9:16"
    HORIZONTAL = "16:9"


class AdTaskBase(BaseModel):
    product_id: int
    platform: Platform
    ad_type: AdType
    style: Optional[str] = Field(None, max_length=50)
    image_ratio: ImageRatio = ImageRatio.SQUARE
    copywriting_tone: Optional[str] = Field(None, max_length=50)


class AdTaskCreate(AdTaskBase):
    shop_id: int


class AdTaskResponse(AdTaskBase):
    id: int
    user_id: int
    shop_id: int
    status: TaskStatus
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdCopyResponse(BaseModel):
    id: int
    task_id: int
    title: Optional[str] = None
    body: str
    slogan: Optional[str] = None
    platform: str
    version: int
    created_at: datetime

    class Config:
        from_attributes = True


class ImagePromptResponse(BaseModel):
    id: int
    task_id: int
    prompt: str
    negative_prompt: Optional[str] = None
    style: Optional[str] = None
    ratio: Optional[str] = None
    version: int
    created_at: datetime

    class Config:
        from_attributes = True
