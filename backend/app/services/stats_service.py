from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict
from app.models.ad_task import AdTask
from app.models.material import Material
from app.models.usage_log import UsageLog
from app.schemas.stats import StatsOverview, TaskStats, CostStats


class StatsService:
    @staticmethod
    def get_overview(db: Session, user_id: int) -> StatsOverview:
        """获取统计概览"""
        # 总任务数
        total_tasks = db.query(AdTask).filter(AdTask.user_id == user_id).count()

        # 成功和失败任务数
        success_tasks = db.query(AdTask).filter(
            AdTask.user_id == user_id,
            AdTask.status == "completed"
        ).count()

        failed_tasks = db.query(AdTask).filter(
            AdTask.user_id == user_id,
            AdTask.status == "failed"
        ).count()

        # 成功率
        success_rate = (success_tasks / total_tasks * 100) if total_tasks > 0 else 0.0

        # 总素材数
        total_materials = db.query(Material).join(AdTask).filter(
            AdTask.user_id == user_id
        ).count()

        # 平均延迟
        avg_latency = db.query(func.avg(UsageLog.latency_ms)).filter(
            UsageLog.user_id == user_id
        ).scalar() or 0.0

        # 总成本
        total_cost = db.query(func.sum(UsageLog.estimated_cost)).filter(
            UsageLog.user_id == user_id
        ).scalar() or Decimal("0.0")

        return StatsOverview(
            total_tasks=total_tasks,
            success_tasks=success_tasks,
            failed_tasks=failed_tasks,
            success_rate=round(success_rate, 2),
            total_materials=total_materials,
            avg_latency_ms=round(float(avg_latency), 2),
            estimated_total_cost=total_cost
        )

    @staticmethod
    def get_task_stats(db: Session, user_id: int) -> TaskStats:
        """获取任务统计"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)

        # 今日任务
        today_tasks = db.query(AdTask).filter(
            AdTask.user_id == user_id,
            AdTask.created_at >= today_start
        ).count()

        # 本周任务
        week_tasks = db.query(AdTask).filter(
            AdTask.user_id == user_id,
            AdTask.created_at >= week_start
        ).count()

        # 本月任务
        month_tasks = db.query(AdTask).filter(
            AdTask.user_id == user_id,
            AdTask.created_at >= month_start
        ).count()

        # 平台分布
        platform_stats = db.query(
            AdTask.platform,
            func.count(AdTask.id)
        ).filter(
            AdTask.user_id == user_id
        ).group_by(AdTask.platform).all()

        platform_distribution = {platform: count for platform, count in platform_stats}

        return TaskStats(
            today_tasks=today_tasks,
            week_tasks=week_tasks,
            month_tasks=month_tasks,
            platform_distribution=platform_distribution
        )

    @staticmethod
    def get_cost_stats(db: Session, user_id: int) -> CostStats:
        """获取成本统计"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)

        # 今日成本
        today_cost = db.query(func.sum(UsageLog.estimated_cost)).filter(
            UsageLog.user_id == user_id,
            UsageLog.created_at >= today_start
        ).scalar() or Decimal("0.0")

        # 本周成本
        week_cost = db.query(func.sum(UsageLog.estimated_cost)).filter(
            UsageLog.user_id == user_id,
            UsageLog.created_at >= week_start
        ).scalar() or Decimal("0.0")

        # 本月成本
        month_cost = db.query(func.sum(UsageLog.estimated_cost)).filter(
            UsageLog.user_id == user_id,
            UsageLog.created_at >= month_start
        ).scalar() or Decimal("0.0")

        # 总成本
        total_cost = db.query(func.sum(UsageLog.estimated_cost)).filter(
            UsageLog.user_id == user_id
        ).scalar() or Decimal("0.0")

        return CostStats(
            today_cost=today_cost,
            week_cost=week_cost,
            month_cost=month_cost,
            total_cost=total_cost
        )
