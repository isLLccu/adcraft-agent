from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.schemas.shop import ShopCreate, ShopUpdate, ShopResponse
from app.services.shop_service import ShopService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("", response_model=ShopResponse, status_code=status.HTTP_201_CREATED)
def create_shop(
    shop_data: ShopCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建店铺"""
    return ShopService.create_shop(db, shop_data, current_user.id)


@router.get("", response_model=List[ShopResponse])
def get_shops(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户的所有店铺"""
    return ShopService.get_user_shops(db, current_user.id, skip, limit)


@router.get("/{shop_id}", response_model=ShopResponse)
def get_shop(
    shop_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取店铺详情"""
    return ShopService.get_shop(db, shop_id, current_user.id)


@router.put("/{shop_id}", response_model=ShopResponse)
def update_shop(
    shop_id: int,
    shop_data: ShopUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新店铺信息"""
    return ShopService.update_shop(db, shop_id, shop_data, current_user.id)


@router.delete("/{shop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shop(
    shop_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除店铺"""
    ShopService.delete_shop(db, shop_id, current_user.id)
