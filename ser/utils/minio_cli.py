import json
import logging
import os
from pathlib import Path
from minio import Minio
from minio.error import S3Error
from .conf import get_config
import io

class MinIOClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MinIOClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化 MinIO 客户端"""
        minio_config = get_config('minio', {})

        self.client = Minio(
            endpoint= minio_config.get('host', 'localhost:9000'),
            access_key= minio_config.get('user',''),
            secret_key= minio_config.get('password',''),
            secure=False

        )

        self.bucket_name = minio_config.get('bucket', 'documents')

        # 确保存储桶存在
        self._ensure_bucket_exists()


        # 设置存储桶为公共读
        self._set_public_read_policy()

    
    def _ensure_bucket_exists(self):
        """确保存储桶存在"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logging.info(f"存储桶 {self.bucket_name} 创建成功")
            else:
                logging.info(f"存储桶 {self.bucket_name} 已存在")
        except S3Error as e:
            logging.info(f"检查/创建存储桶时出错: {e}")
            raise
    def _set_public_read_policy(self):
        """设置存储桶公共读策略"""
        try:
            # 设置公共读策略
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
                        "Resource": f"arn:aws:s3:::{self.bucket_name}"
                    },
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{self.bucket_name}/*"
                    }
                ]
            }
            self.client.set_bucket_policy(self.bucket_name, json.dumps(policy))
            logging.info(f"存储桶 {self.bucket_name} 公共读策略设置成功")
        except Exception as e:
            logging.info(f"设置存储桶策略时出错: {e}")

    def get_content_type(self, file_path: str) -> str:
        """根据文件扩展名获取内容类型"""
        extension_mapping = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
            '.tiff': 'image/tiff',
        }
        ext = Path(file_path).suffix.lower()
        return extension_mapping.get(ext, 'application/octet-stream')

    def upload_file(self, prev:str, file_content: bytes, filename: str, content_type: str = None) -> str:
        """
        上传文件到 MinIO
        :param prev: 指定对象名前缀
        :param file_content: 文件内容 (bytes)
        :param filename: 文件名
        :param content_type: 内容类型
        :return: 对象名称
        """
        try:
            # 生成唯一的对象名称
            from datetime import datetime
            import hashlib
            
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            file_hash = hashlib.md5(file_content).hexdigest()
            extension = filename.split('.')[-1] if '.' in filename else ''
            object_name = f"{prev}_{timestamp}_{file_hash}.{extension}"
            
            # 上传文件
            data = io.BytesIO(file_content)
            self.client.put_object(
                self.bucket_name,
                object_name,
                data,
                len(file_content),
                content_type=content_type
            )
            
            logging.info(f"文件 {filename} 上传成功，对象名称: {object_name}")
            return object_name
            
        except S3Error as e:
            logging.info(f"上传文件时出错: {e}")
            raise

    def upload_file_spec_path(self,local_file_path,object_name):
        # 上传文件
        try:
            # 读取文件内容
            with open(local_file_path, 'rb') as f:
                file_content = f.read()
            # 上传文件
            data = io.BytesIO(file_content)
            self.client.put_object(
                self.bucket_name,
                object_name,
                data,
                len(file_content),
                content_type=self.get_content_type(local_file_path)
            )
            return self.get_public_url(object_name)
        except Exception as e:
            logging.info(f"上传文件失败 {local_file_path}  error: {e}")
            return object_name

    def upload_directory(self,local_dir,remote_dir):
        """
        上传目录下的所有文件到 MinIO
        """
        uploaded_files = []
        object_list = []
        # 确保目录存在
        if not os.path.exists(local_dir):
            raise FileNotFoundError(f"本地目录不存在: {local_dir}")
        # 获取目录下所有文件（包括子目录）
        for root, dirs, files in os.walk(local_dir):
            for file in files:
                local_file_path = os.path.join(root, file)
                object_name = os.path.join(remote_dir, file).replace("\\", "/")

                # 上传文件
                try:
                    # 读取文件内容
                    with open(local_file_path, 'rb') as f:
                        file_content = f.read()
                    # 上传文件
                    data = io.BytesIO(file_content)
                    self.client.put_object(
                        self.bucket_name,
                        object_name,
                        data,
                        len(file_content),
                        content_type = self.get_content_type(local_file_path)
                    )
                    object_list.append(self.get_public_url(object_name))
                except Exception as e:
                    logging.info(f"上传文件失败 {local_file_path}: {e}")
                    object_list.append(None)
        return object_list
    def get_public_url_prev(self):
        """
         获取文件的公共访问 URL 前缀
        """
        minio_config = get_config('minio', {})
        endpoint = minio_config.get('endpoint', 'localhost:9000')
        secure = minio_config.get('secure', False)

        protocol = "https" if secure else "http"
        public_url = f"{protocol}://{endpoint}/{self.bucket_name}"
        return public_url

    def get_public_url(self, object_name: str) -> str:
        """
        获取文件的公共访问 URL（永久有效）
        """
        minio_config = get_config('minio', {})
        endpoint = minio_config.get('endpoint', 'localhost:9000')
        secure = minio_config.get('secure', False)

        protocol = "https" if secure else "http"
        public_url = f"{protocol}://{endpoint}/{self.bucket_name}/{object_name}"
        return public_url


    def get_presigned_url(self, object_name: str, expires: int = 7*24*60*60) -> str:
        """
        获取预签名 URL
        :param object_name: 对象名称
        :param expires: 过期时间（秒），默认7天
        :return: 预签名 URL
        """
        try:
            url = self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=expires
            )
            return url
        except S3Error as e:
            logging.info(f"生成预签名 URL 时出错: {e}")
            raise



    def download_file(self, object_name: str) -> bytes:
        """
        下载文件
        :param object_name: 对象名称
        :return: 文件内容 (bytes)
        """
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            return response.read()
        except S3Error as e:
            logging.info(f"下载文件时出错: {e}")
            raise
        finally:
            response.close()
            response.release_conn()



# 全局实例
minio_client = MinIOClient()
logging.info(f'minio_client {minio_client}')