from pydantic import BaseModel
from typing import Dict
from decimal import Decimal


class StatsOverview(BaseModel):
    total_tasks: int
    success_tasks: int
    failed_tasks: int
    success_rate: float
    total_materials: int
    avg_latency_ms: float
    estimated_total_cost: Decimal


class TaskStats(BaseModel):
    today_tasks: int
    week_tasks: int
    month_tasks: int
    platform_distribution: Dict[str, int]


class CostStats(BaseModel):
    today_cost: Decimal
    week_cost: Decimal
    month_cost: Decimal
    total_cost: Decimal
