from minio import Minio
from minio.error import S3Error
from app.core.config import settings
from app.core.logging import get_logger
from io import BytesIO
from typing import Optional
import uuid

logger = get_logger("storage")


class StorageService:
    def __init__(self):
        self.client = None
        self.bucket = settings.MINIO_BUCKET
        self._initialized = False

    def _initialize(self):
        """延迟初始化 MinIO 客户端"""
        if self._initialized:
            return

        try:
            self.client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            self._ensure_bucket_exists()
            self._initialized = True
            logger.info("MinIO client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise

    def _ensure_bucket_exists(self):
        """确保存储桶存在并允许公网匿名读取（让浏览器能直接 <img src=> 加载）"""
        import json
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket: {self.bucket}")

            # 设置匿名 GetObject 策略 (public-read)
            policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self.bucket}/*"],
                }],
            }
            self.client.set_bucket_policy(self.bucket, json.dumps(policy))
            logger.info(f"Bucket policy set to public-read: {self.bucket}")
        except S3Error as e:
            logger.error(f"Error initializing bucket: {e}")
            raise

    def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        content_type: str = "application/octet-stream"
    ) -> str:
        """上传文件到 MinIO"""
        self._initialize()  # 确保已初始化

        try:
            # 生成唯一文件名
            file_extension = file_name.split(".")[-1] if "." in file_name else ""
            unique_name = f"{uuid.uuid4()}.{file_extension}" if file_extension else str(uuid.uuid4())

            # 上传文件
            self.client.put_object(
                self.bucket,
                unique_name,
                BytesIO(file_data),
                length=len(file_data),
                content_type=content_type
            )

            # 返回文件 URL
            url = f"http://{settings.MINIO_PUBLIC_ENDPOINT or settings.MINIO_ENDPOINT}/{self.bucket}/{unique_name}"
            logger.info(f"Uploaded file: {url}")
            return url

        except S3Error as e:
            logger.error(f"Error uploading file: {e}")
            raise Exception(f"Failed to upload file: {str(e)}")

    def delete_file(self, file_url: str) -> bool:
        """删除文件"""
        self._initialize()  # 确保已初始化

        try:
            # 从 URL 中提取文件名
            file_name = file_url.split("/")[-1]
            self.client.remove_object(self.bucket, file_name)
            logger.info(f"Deleted file: {file_name}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting file: {e}")
            return False

    def download_file(self, file_name: str) -> bytes:
        """下载文件"""
        self._initialize()  # 确保已初始化

        try:
            response = self.client.get_object(self.bucket, file_name)
            data = response.read()
            response.close()
            response.release_conn()
            logger.info(f"Downloaded file: {file_name}")
            return data
        except S3Error as e:
            logger.error(f"Error downloading file: {e}")
            raise Exception(f"Failed to download file: {str(e)}")

    def get_file_url(self, file_name: str) -> str:
        """获取文件 URL（返回浏览器可访问的地址）"""
        return f"http://{settings.MINIO_PUBLIC_ENDPOINT or settings.MINIO_ENDPOINT}/{self.bucket}/{file_name}"


# 创建全局实例
storage_service = StorageService()
