from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.schemas.ad_task import AdTaskCreate, AdTaskResponse
from app.services.ad_task_service import AdTaskService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("", response_model=AdTaskResponse, status_code=status.HTTP_201_CREATED)
def create_ad_task(
    task_data: AdTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建广告任务"""
    return AdTaskService.create_task(db, task_data, current_user.id)


@router.get("", response_model=List[AdTaskResponse])
def get_ad_tasks(
    skip: int = 0,
    limit: int = 100,
    status: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取广告任务列表"""
    return AdTaskService.get_tasks(db, current_user.id, skip, limit, status)


@router.get("/{task_id}", response_model=AdTaskResponse)
def get_ad_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取广告任务详情"""
    task = AdTaskService.get_task(db, task_id, current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/retry", response_model=AdTaskResponse)
def retry_ad_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """重试失败的广告任务"""
    return AdTaskService.retry_task(db, task_id, current_user.id)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ad_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除广告任务"""
    AdTaskService.delete_task(db, task_id, current_user.id)
