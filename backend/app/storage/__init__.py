"""Storage abstraction layer for Alexandria.

Provides a pluggable storage backend supporting:
- Local filesystem (for development)
- AWS S3
- Cloudflare R2 (S3-compatible)

Usage:
    from app.storage import get_storage

    storage = get_storage()
    await storage.upload("uploads/user-id/file.pdf", content, "application/pdf")
    url = await storage.get_url("uploads/user-id/file.pdf")
    await storage.delete("uploads/user-id/file.pdf")
"""

from app.storage.base import StorageBackend
from app.storage.exceptions import (
    StorageDeleteError,
    StorageError,
    StorageFileNotFoundError,
    StorageUploadError,
)
from app.storage.factory import clear_storage_cache, get_storage

__all__ = [
    "StorageBackend",
    "get_storage",
    "clear_storage_cache",
    "StorageError",
    "StorageFileNotFoundError",
    "StorageUploadError",
    "StorageDeleteError",
]
