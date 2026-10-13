from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.product import Product
from app.models.shop import Shop
from app.schemas.product import ProductCreate, ProductUpdate
from app.core.exceptions import NotFoundException, ForbiddenException


class ProductService:
    @staticmethod
    def verify_shop_access(db: Session, shop_id: int, user_id: int) -> Shop:
        """验证用户是否有权限访问店铺"""
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            raise NotFoundException(detail="Shop not found")

        if shop.user_id != user_id:
            raise ForbiddenException(detail="Not authorized to access this shop")

        return shop

    @staticmethod
    def create_product(db: Session, product_data: ProductCreate, user_id: int) -> Product:
        """创建商品"""
        # 验证店铺权限
        ProductService.verify_shop_access(db, product_data.shop_id, user_id)

        db_product = Product(
            shop_id=product_data.shop_id,
            name=product_data.name,
            category=product_data.category,
            price=product_data.price,
            description=product_data.description,
            selling_points=product_data.selling_points,
            target_audience=product_data.target_audience,
            usage_scenario=product_data.usage_scenario,
            tags=product_data.tags
        )
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product

    @staticmethod
    def get_product(db: Session, product_id: int, user_id: int) -> Product:
        """获取商品详情"""
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise NotFoundException(detail="Product not found")

        # 验证权限
        ProductService.verify_shop_access(db, product.shop_id, user_id)

        return product

    @staticmethod
    def get_shop_products(
        db: Session,
        shop_id: int,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Product]:
        """获取店铺的所有商品"""
        # 验证权限
        ProductService.verify_shop_access(db, shop_id, user_id)

        return db.query(Product).filter(Product.shop_id == shop_id).offset(skip).limit(limit).all()

    @staticmethod
    def get_user_products(
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        shop_id: Optional[int] = None
    ) -> List[Product]:
        """获取当前用户名下所有商品（可选按店铺过滤）"""
        query = db.query(Product).join(Shop, Product.shop_id == Shop.id).filter(Shop.user_id == user_id)
        if shop_id is not None:
            query = query.filter(Product.shop_id == shop_id)
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def update_product(
        db: Session,
        product_id: int,
        product_data: ProductUpdate,
        user_id: int
    ) -> Product:
        """更新商品信息"""
        product = ProductService.get_product(db, product_id, user_id)

        update_data = product_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(product, field, value)

        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def update_product_image(
        db: Session,
        product_id: int,
        image_url: str,
        user_id: int
    ) -> Product:
        """更新商品图片"""
        product = ProductService.get_product(db, product_id, user_id)
        product.image_url = image_url
        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def delete_product(db: Session, product_id: int, user_id: int) -> None:
        """删除商品"""
        product = ProductService.get_product(db, product_id, user_id)
        db.delete(product)
        db.commit()
