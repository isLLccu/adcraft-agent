from fastapi import APIRouter, Depends, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.services.product_service import ProductService
from app.services.storage_service import storage_service
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建商品"""
    return ProductService.create_product(db, product_data, current_user.id)


@router.get("", response_model=List[ProductResponse])
def get_products(
    skip: int = 0,
    limit: int = 100,
    shop_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户名下所有商品（可选按店铺过滤）"""
    return ProductService.get_user_products(db, current_user.id, skip, limit, shop_id)


@router.get("/shop/{shop_id}", response_model=List[ProductResponse])
def get_shop_products(
    shop_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取店铺的所有商品"""
    return ProductService.get_shop_products(db, shop_id, current_user.id, skip, limit)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取商品详情"""
    return ProductService.get_product(db, product_id, current_user.id)


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新商品信息"""
    return ProductService.update_product(db, product_id, product_data, current_user.id)


@router.post("/{product_id}/upload-image", response_model=ProductResponse)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传商品图片"""
    # 读取文件内容
    file_data = await file.read()

    # 上传到 MinIO
    image_url = storage_service.upload_file(
        file_data=file_data,
        file_name=file.filename,
        content_type=file.content_type
    )

    # 更新商品图片 URL
    return ProductService.update_product_image(db, product_id, image_url, current_user.id)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除商品"""
    ProductService.delete_product(db, product_id, current_user.id)
