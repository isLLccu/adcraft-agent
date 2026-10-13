from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.shop import Shop
from app.schemas.shop import ShopCreate, ShopUpdate
from app.core.exceptions import NotFoundException, ForbiddenException


class ShopService:
    @staticmethod
    def create_shop(db: Session, shop_data: ShopCreate, user_id: int) -> Shop:
        """创建店铺"""
        db_shop = Shop(
            user_id=user_id,
            name=shop_data.name,
            industry=shop_data.industry,
            brand_style=shop_data.brand_style,
            target_audience=shop_data.target_audience,
            main_platform=shop_data.main_platform,
            description=shop_data.description
        )
        db.add(db_shop)
        db.commit()
        db.refresh(db_shop)
        return db_shop

    @staticmethod
    def get_shop(db: Session, shop_id: int, user_id: int) -> Shop:
        """获取店铺详情"""
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            raise NotFoundException(detail="Shop not found")

        if shop.user_id != user_id:
            raise ForbiddenException(detail="Not authorized to access this shop")

        return shop

    @staticmethod
    def get_user_shops(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Shop]:
        """获取用户的所有店铺"""
        return db.query(Shop).filter(Shop.user_id == user_id).offset(skip).limit(limit).all()

    @staticmethod
    def update_shop(db: Session, shop_id: int, shop_data: ShopUpdate, user_id: int) -> Shop:
        """更新店铺信息"""
        shop = ShopService.get_shop(db, shop_id, user_id)

        update_data = shop_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(shop, field, value)

        db.commit()
        db.refresh(shop)
        return shop

    @staticmethod
    def delete_shop(db: Session, shop_id: int, user_id: int) -> None:
        """删除店铺"""
        shop = ShopService.get_shop(db, shop_id, user_id)
        db.delete(shop)
        db.commit()
