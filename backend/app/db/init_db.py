from sqlalchemy.orm import Session
from app.db.session import engine
from app.models import Base, User
from app.core.security import get_password_hash


def init_db(db: Session) -> None:
    """初始化数据库，创建默认用户"""
    # 创建所有表
    Base.metadata.create_all(bind=engine)

    # 检查是否已有用户
    user = db.query(User).filter(User.username == "admin").first()
    if not user:
        # 创建默认管理员用户
        admin_user = User(
            username="admin",
            email="admin@adcraft.com",
            hashed_password=get_password_hash("admin123"),
            role="admin",
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        print("Default admin user created: admin / admin123")
