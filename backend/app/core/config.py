from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "AdCraft Agent"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://adcraft:adcraft123@localhost:5432/adcraft"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_PUBLIC_ENDPOINT: str = ""  # 浏览器可访问的地址（容器场景下与 MINIO_ENDPOINT 不同）
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "adcraft"
    MINIO_SECURE: bool = False

    # JWT
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # LLM API (默认 DeepSeek，兼容 OpenAI 协议)
    LLM_API_BASE: str = "https://api.deepseek.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    LLM_TIMEOUT: int = 60

    # Image API (默认阿里云 DashScope 通义万相)
    IMAGE_PROVIDER: str = "dashscope"  # dashscope | openai | mock
    IMAGE_API_BASE: str = "https://dashscope.aliyuncs.com/api/v1"
    IMAGE_API_KEY: str = ""
    IMAGE_MODEL: str = "wanx-v1"
    IMAGE_TIMEOUT: int = 180

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # CORS
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
