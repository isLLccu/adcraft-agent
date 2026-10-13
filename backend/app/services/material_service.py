from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.models.material import Material
from app.models.ad_task import AdTask
from app.models.product import Product
from app.models.ad_copy import AdCopy
from app.models.image_prompt import ImagePrompt
from app.schemas.material import MaterialUpdate, MaterialStats, MaterialBatchUpdate
from app.core.exceptions import NotFoundException, ForbiddenException
from app.core.logging import logger


class MaterialService:
    @staticmethod
    def get_materials(
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        product_id: Optional[int] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        is_favorite: Optional[bool] = None
    ) -> List[Material]:
        """获取用户的素材列表（带过滤）"""
        # 通过 task 关联查询用户的素材
        query = db.query(Material).join(AdTask).filter(AdTask.user_id == user_id)

        # 应用过滤条件
        if product_id:
            query = query.filter(Material.product_id == product_id)

        if platform:
            query = query.filter(AdTask.platform == platform)

        if status:
            query = query.filter(Material.status == status)

        if is_favorite is not None:
            query = query.filter(Material.is_favorite == is_favorite)

        return query.order_by(Material.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_material(db: Session, material_id: int, user_id: int) -> Optional[Material]:
        """获取素材详情（包含关联数据）"""
        material = (
            db.query(Material)
            .join(AdTask)
            .filter(Material.id == material_id, AdTask.user_id == user_id)
            .options(
                joinedload(Material.copy),
                joinedload(Material.prompt),
                joinedload(Material.product),
                joinedload(Material.task)
            )
            .first()
        )

        if not material:
            raise NotFoundException(detail="Material not found")

        return material

    @staticmethod
    def update_material(
        db: Session,
        material_id: int,
        user_id: int,
        update_data: MaterialUpdate
    ) -> Material:
        """更新素材（收藏、归档等）"""
        material = (
            db.query(Material)
            .join(AdTask)
            .filter(Material.id == material_id, AdTask.user_id == user_id)
            .first()
        )

        if not material:
            raise NotFoundException(detail="Material not found")

        # 更新字段
        if update_data.is_favorite is not None:
            material.is_favorite = update_data.is_favorite

        if update_data.status is not None:
            if update_data.status not in ["active", "archived"]:
                raise ForbiddenException(detail="Invalid status value")
            material.status = update_data.status

        db.commit()
        db.refresh(material)
        logger.info(f"Material {material_id} updated by user {user_id}")
        return material

    @staticmethod
    def batch_update_materials(
        db: Session,
        user_id: int,
        batch_data: MaterialBatchUpdate
    ) -> int:
        """批量更新素材"""
        # 验证所有素材都属于该用户
        materials = (
            db.query(Material)
            .join(AdTask)
            .filter(
                Material.id.in_(batch_data.material_ids),
                AdTask.user_id == user_id
            )
            .all()
        )

        if len(materials) != len(batch_data.material_ids):
            raise NotFoundException(detail="Some materials not found or not accessible")

        # 批量更新
        update_dict = {}
        if batch_data.is_favorite is not None:
            update_dict["is_favorite"] = batch_data.is_favorite

        if batch_data.status is not None:
            if batch_data.status not in ["active", "archived"]:
                raise ForbiddenException(detail="Invalid status value")
            update_dict["status"] = batch_data.status

        if update_dict:
            db.query(Material).filter(
                Material.id.in_(batch_data.material_ids)
            ).update(update_dict, synchronize_session=False)
            db.commit()
            logger.info(f"Batch updated {len(materials)} materials by user {user_id}")

        return len(materials)

    @staticmethod
    def delete_material(db: Session, material_id: int, user_id: int):
        """删除素材"""
        material = (
            db.query(Material)
            .join(AdTask)
            .filter(Material.id == material_id, AdTask.user_id == user_id)
            .first()
        )

        if not material:
            raise NotFoundException(detail="Material not found")

        db.delete(material)
        db.commit()
        logger.info(f"Material {material_id} deleted by user {user_id}")

    @staticmethod
    def get_material_stats(db: Session, user_id: int) -> MaterialStats:
        """获取用户的素材统计信息"""
        # 查询用户的所有素材
        materials = db.query(Material).join(AdTask).filter(AdTask.user_id == user_id).all()

        total = len(materials)
        active = sum(1 for m in materials if m.status == "active")
        archived = sum(1 for m in materials if m.status == "archived")
        favorites = sum(1 for m in materials if m.is_favorite)

        return MaterialStats(
            total=total,
            active=active,
            archived=archived,
            favorites=favorites
        )
