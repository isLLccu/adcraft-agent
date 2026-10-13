from sqlalchemy.orm import Session
from typing import Optional
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import verify_password, get_password_hash
from app.core.exceptions import ConflictException, UnauthorizedException


class AuthService:
    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """根据 ID 获取用户"""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        """创建新用户"""
        # 检查用户名是否已存在
        if AuthService.get_user_by_username(db, user_data.username):
            raise ConflictException(detail="Username already exists")

        # 检查邮箱是否已存在
        if AuthService.get_user_by_email(db, user_data.email):
            raise ConflictException(detail="Email already exists")

        # 创建用户
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            role="user",
            is_active=True
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> User:
        """验证用户登录"""
        user = AuthService.get_user_by_username(db, username)
        if not user:
            raise UnauthorizedException(detail="Incorrect username or password")

        if not verify_password(password, user.hashed_password):
            raise UnauthorizedException(detail="Incorrect username or password")

        if not user.is_active:
            raise UnauthorizedException(detail="User account is inactive")

        return user
