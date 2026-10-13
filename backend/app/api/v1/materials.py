from fastapi import APIRouter, Depends, status, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.schemas.material import (
    MaterialResponse,
    MaterialDetailResponse,
    MaterialUpdate,
    MaterialStats,
    MaterialBatchUpdate
)
from app.services.material_service import MaterialService
from app.services.storage_service import StorageService
from app.api.deps import get_current_user
from app.models.user import User
from app.core.logging import logger
import io

router = APIRouter()


@router.get("", response_model=List[MaterialResponse])
def get_materials(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    product_id: Optional[int] = Query(None),
    platform: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    is_favorite: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取素材列表（支持过滤）"""
    return MaterialService.get_materials(
        db,
        current_user.id,
        skip,
        limit,
        product_id,
        platform,
        status,
        is_favorite
    )


@router.get("/stats", response_model=MaterialStats)
def get_material_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取素材统计信息"""
    return MaterialService.get_material_stats(db, current_user.id)


@router.get("/{material_id}", response_model=MaterialDetailResponse)
def get_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取素材详情（包含关联的文案、Prompt、商品信息）"""
    material = MaterialService.get_material(db, material_id, current_user.id)

    # 构建详情响应
    response_data = {
        "id": material.id,
        "task_id": material.task_id,
        "product_id": material.product_id,
        "image_url": material.image_url,
        "copy_id": material.copy_id,
        "prompt_id": material.prompt_id,
        "status": material.status,
        "is_favorite": material.is_favorite,
        "created_at": material.created_at,
    }

    # 添加关联数据
    if material.copy:
        response_data["copy"] = {
            "id": material.copy.id,
            "title": material.copy.title,
            "body": material.copy.body,
            "slogan": material.copy.slogan,
            "platform": material.copy.platform,
        }

    if material.prompt:
        response_data["prompt"] = {
            "id": material.prompt.id,
            "prompt": material.prompt.prompt,
            "negative_prompt": material.prompt.negative_prompt,
            "style": material.prompt.style,
            "ratio": material.prompt.ratio,
        }

    if material.product:
        response_data["product"] = {
            "id": material.product.id,
            "name": material.product.name,
            "category": material.product.category,
            "price": material.product.price,
            "image_url": material.product.image_url,
        }

    if material.task:
        response_data["task"] = {
            "id": material.task.id,
            "platform": material.task.platform,
            "ad_type": material.task.ad_type,
            "status": material.task.status,
            "created_at": material.task.created_at,
        }

    return response_data


@router.get("/{material_id}/download")
async def download_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """下载素材图片"""
    material = MaterialService.get_material(db, material_id, current_user.id)

    try:
        # 从 MinIO 下载文件
        storage_service = StorageService()
        # 从 URL 中提取文件名（假设格式为 http://minio:9000/bucket/filename）
        file_name = material.image_url.split('/')[-1]
        file_data = storage_service.download_file(file_name)

        # 返回文件流
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename={file_name}"
            }
        )
    except Exception as e:
        logger.error(f"Failed to download material {material_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download material: {str(e)}"
        )


@router.put("/{material_id}", response_model=MaterialResponse)
def update_material(
    material_id: int,
    update_data: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新素材（收藏/取消收藏、归档等）"""
    return MaterialService.update_material(db, material_id, current_user.id, update_data)


@router.post("/batch-update")
def batch_update_materials(
    batch_data: MaterialBatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量更新素材"""
    count = MaterialService.batch_update_materials(db, current_user.id, batch_data)
    return {"message": f"Successfully updated {count} materials"}


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除素材"""
    MaterialService.delete_material(db, material_id, current_user.id)
