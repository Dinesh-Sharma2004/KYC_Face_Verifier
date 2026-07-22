"""Object Storage Abstraction supporting MinIO (Local) and Cloudflare R2 (Production)."""

import abc
import hashlib
import os
from typing import Dict, Optional


class StorageClient(abc.ABC):
    """Abstract interface for document object storage."""

    @abc.abstractmethod
    def put_object(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Store bytes and return object key/URI."""
        pass

    @abc.abstractmethod
    def get_object(self, bucket: str, key: str) -> bytes:
        """Retrieve stored bytes for a given bucket and key."""
        pass

    @abc.abstractmethod
    def delete_object(self, bucket: str, key: str) -> bool:
        """Remove object from storage."""
        pass

    @abc.abstractmethod
    def get_presigned_url(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned access URL for the target object."""
        pass

    @staticmethod
    def calculate_sha256(data: bytes) -> str:
        """Utility method to calculate SHA256 hex digest for data integrity."""
        return hashlib.sha256(data).hexdigest()

    def verify_checksum(self, data: bytes, expected_sha256: str) -> bool:
        """Verify byte integrity against expected hash."""
        return self.calculate_sha256(data).lower() == expected_sha256.lower()


class LocalStorageClient(StorageClient):
    """In-memory and local disk storage implementation for testing and local fallback."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir
        self._memory_store: Dict[str, bytes] = {}

    def _full_key(self, bucket: str, key: str) -> str:
        return f"{bucket}/{key}".lstrip("/")

    def put_object(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        full_key = self._full_key(bucket, key)
        if self.base_dir:
            file_path = os.path.join(self.base_dir, bucket, key)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(data)
        else:
            self._memory_store[full_key] = data
        return full_key

    def get_object(self, bucket: str, key: str) -> bytes:
        full_key = self._full_key(bucket, key)
        if self.base_dir:
            file_path = os.path.join(self.base_dir, bucket, key)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Object {full_key} not found in storage.")
            with open(file_path, "rb") as f:
                return f.read()
        else:
            if full_key not in self._memory_store:
                raise FileNotFoundError(f"Object {full_key} not found in memory store.")
            return self._memory_store[full_key]

    def delete_object(self, bucket: str, key: str) -> bool:
        full_key = self._full_key(bucket, key)
        if self.base_dir:
            file_path = os.path.join(self.base_dir, bucket, key)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        else:
            if full_key in self._memory_store:
                del self._memory_store[full_key]
                return True
            return False

    def get_presigned_url(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        raise RuntimeError("Local storage does not issue public document URLs.")


class S3StorageClient(StorageClient):
    """S3-compatible storage client for MinIO and Cloudflare R2."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
    ):
        self.endpoint_url = endpoint_url or os.getenv("STORAGE_ENDPOINT_URL")
        self.aws_access_key_id = aws_access_key_id or os.getenv("STORAGE_ACCESS_KEY")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("STORAGE_SECRET_KEY")
        self.region_name = region_name or os.getenv("STORAGE_REGION", "us-east-1")
        self._s3_client = None

    def _get_client(self):
        if not self.endpoint_url or not self.aws_access_key_id or not self.aws_secret_access_key:
            raise RuntimeError("S3-compatible storage requires endpoint, access key, and secret key configuration.")

        if self._s3_client is None:
            try:
                import boto3
                from botocore.config import Config

                self._s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    region_name=self.region_name,
                    config=Config(signature_version="s3v4"),
                )
            except ImportError:
                return _shared_local_client
        return self._s3_client

    def put_object(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        client = self._get_client()
        if isinstance(client, StorageClient):
            return client.put_object(bucket, key, data, content_type)
        client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        return key

    def get_object(self, bucket: str, key: str) -> bytes:
        client = self._get_client()
        if isinstance(client, StorageClient):
            return client.get_object(bucket, key)
        response = client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def delete_object(self, bucket: str, key: str) -> bool:
        client = self._get_client()
        if isinstance(client, StorageClient):
            return client.delete_object(bucket, key)
        client.delete_object(Bucket=bucket, Key=key)
        return True

    def get_presigned_url(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        client = self._get_client()
        if isinstance(client, StorageClient):
            return client.get_presigned_url(bucket, key, expires_in)
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )


_shared_local_client = LocalStorageClient()


def get_storage_client() -> StorageClient:
    """Factory function returning the configured StorageClient."""
    provider = os.getenv("STORAGE_PROVIDER", "local").lower()
    if provider in ("s3", "minio", "r2"):
        return S3StorageClient()
    return _shared_local_client
