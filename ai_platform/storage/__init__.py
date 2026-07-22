"""Storage package initialization."""

from ai_platform.storage.client import (
    LocalStorageClient,
    S3StorageClient,
    StorageClient,
    get_storage_client,
)

__all__ = [
    "StorageClient",
    "LocalStorageClient",
    "S3StorageClient",
    "get_storage_client",
]
