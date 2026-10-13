from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.ad_task import AdTask
from app.models.product import Product
from app.schemas.ad_task import AdTaskCreate
from app.core.exceptions import NotFoundException, ForbiddenException
from app.workers.tasks import generate_ad_materials
from app.core.logging import logger


class AdTaskService:
    @staticmethod
    def create_task(db: Session, task_data: AdTaskCreate, user_id: int) -> AdTask:
        """创建广告任务"""
        # 验证商品是否存在且属于用户
        product = db.query(Product).filter(
            Product.id == task_data.product_id,
            Product.shop_id == task_data.shop_id
        ).first()

        if not product:
            raise NotFoundException(detail="Product not found")

        # 创建任务
        db_task = AdTask(
            user_id=user_id,
            shop_id=task_data.shop_id,
            product_id=task_data.product_id,
            platform=task_data.platform,
            ad_type=task_data.ad_type,
            style=task_data.style,
            image_ratio=task_data.image_ratio,
            copywriting_tone=task_data.copywriting_tone,
            status="pending",
            retry_count=0,
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)

        # 异步触发任务
        try:
            generate_ad_materials.delay(db_task.id)
            logger.info(f"Ad task {db_task.id} created and queued")
        except Exception as e:
            logger.error(f"Failed to queue ad task {db_task.id}: {str(e)}")
            db_task.status = "failed"
            db_task.error_message = f"Failed to queue task: {str(e)}"
            db.commit()

        return db_task

    @staticmethod
    def get_tasks(
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[AdTask]:
        """获取用户的广告任务列表"""
        query = db.query(AdTask).filter(AdTask.user_id == user_id)

        if status:
            query = query.filter(AdTask.status == status)

        return query.order_by(AdTask.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_task(db: Session, task_id: int, user_id: int) -> Optional[AdTask]:
        """获取广告任务详情"""
        task = db.query(AdTask).filter(
            AdTask.id == task_id,
            AdTask.user_id == user_id
        ).first()

        if not task:
            raise NotFoundException(detail="Task not found")

        return task

    @staticmethod
    def retry_task(db: Session, task_id: int, user_id: int) -> AdTask:
        """重试失败的广告任务"""
        task = db.query(AdTask).filter(
            AdTask.id == task_id,
            AdTask.user_id == user_id
        ).first()

        if not task:
            raise NotFoundException(detail="Task not found")

        if task.status != "failed":
            raise ForbiddenException(detail="Only failed tasks can be retried")

        # 重置任务状态
        task.status = "pending"
        task.error_message = None
        db.commit()

        # 重新触发任务
        try:
            generate_ad_materials.delay(task.id)
            logger.info(f"Ad task {task.id} retried")
        except Exception as e:
            logger.error(f"Failed to retry ad task {task.id}: {str(e)}")
            task.status = "failed"
            task.error_message = f"Failed to queue task: {str(e)}"
            db.commit()

        return task

    @staticmethod
    def delete_task(db: Session, task_id: int, user_id: int):
        """删除广告任务"""
        task = db.query(AdTask).filter(
            AdTask.id == task_id,
            AdTask.user_id == user_id
        ).first()

        if not task:
            raise NotFoundException(detail="Task not found")

        db.delete(task)
        db.commit()
