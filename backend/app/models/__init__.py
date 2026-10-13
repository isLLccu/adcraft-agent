# Import all models here for Alembic to detect them
from app.db.base import Base
from app.models.user import User
from app.models.shop import Shop
from app.models.product import Product
from app.models.ad_task import AdTask
from app.models.ad_copy import AdCopy
from app.models.image_prompt import ImagePrompt
from app.models.material import Material
from app.models.audit_result import AuditResult
from app.models.usage_log import UsageLog

__all__ = [
    "Base",
    "User",
    "Shop",
    "Product",
    "AdTask",
    "AdCopy",
    "ImagePrompt",
    "Material",
    "AuditResult",
    "UsageLog",
]
