from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.stats import StatsOverview, TaskStats, CostStats
from app.services.stats_service import StatsService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/overview", response_model=StatsOverview)
def get_stats_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取统计概览"""
    return StatsService.get_overview(db, current_user.id)


@router.get("/tasks", response_model=TaskStats)
def get_task_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务统计"""
    return StatsService.get_task_stats(db, current_user.id)


@router.get("/costs", response_model=CostStats)
def get_cost_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取成本统计"""
    return StatsService.get_cost_stats(db, current_user.id)
