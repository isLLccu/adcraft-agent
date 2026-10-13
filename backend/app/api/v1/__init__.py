from fastapi import APIRouter
from app.api.v1 import auth, shops, products, ad_tasks, materials, stats

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(shops.router, prefix="/shops", tags=["店铺管理"])
api_router.include_router(products.router, prefix="/products", tags=["商品管理"])
api_router.include_router(ad_tasks.router, prefix="/ad-tasks", tags=["广告任务"])
api_router.include_router(materials.router, prefix="/materials", tags=["素材管理"])
api_router.include_router(stats.router, prefix="/stats", tags=["统计"])
