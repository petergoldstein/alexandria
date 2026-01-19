"""Factory function for creating storage backends."""

import logging
from functools import lru_cache

from app.config import get_settings
from app.storage.base import StorageBackend
from app.storage.local import LocalStorageBackend
from app.storage.s3 import S3StorageBackend

logger = logging.getLogger(__name__)


@lru_cache
def get_storage() -> StorageBackend:
    """Get the configured storage backend.

    Returns a singleton instance based on the STORAGE_BACKEND setting:
    - "local": LocalStorageBackend (filesystem)
    - "s3": S3StorageBackend (AWS S3)
    - "r2": S3StorageBackend (Cloudflare R2, S3-compatible)

    Returns:
        StorageBackend instance

    Raises:
        ValueError: If the storage backend is not recognized
    """
    settings = get_settings()
    backend = settings.storage_backend.lower()

    if backend == "local":
        logger.info(f"Using local storage backend at: {settings.local_storage_path}")
        return LocalStorageBackend(base_path=settings.local_storage_path)

    elif backend == "s3":
        if not settings.s3_access_key_id or not settings.s3_secret_access_key:
            raise ValueError("S3 storage requires S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY")
        if not settings.s3_bucket_name:
            raise ValueError("S3 storage requires S3_BUCKET_NAME")

        logger.info(f"Using S3 storage backend: bucket={settings.s3_bucket_name}")
        return S3StorageBackend(
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            bucket_name=settings.s3_bucket_name,
            endpoint_url=settings.s3_endpoint_url or None,
            region=settings.s3_region,
        )

    elif backend == "r2":
        if not settings.r2_access_key_id or not settings.r2_secret_access_key:
            raise ValueError("R2 storage requires R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY")
        if not settings.r2_bucket_name:
            raise ValueError("R2 storage requires R2_BUCKET_NAME")
        if not settings.r2_endpoint:
            raise ValueError("R2 storage requires R2_ENDPOINT")

        logger.info(f"Using R2 storage backend: bucket={settings.r2_bucket_name}")
        return S3StorageBackend(
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket_name=settings.r2_bucket_name,
            endpoint_url=settings.r2_endpoint,
            region="auto",  # R2 uses "auto" for region
            public_url_base=settings.r2_public_url_base or None,
        )

    else:
        raise ValueError(f"Unknown storage backend: {backend}. Use 'local', 's3', or 'r2'.")


def clear_storage_cache() -> None:
    """Clear the storage backend cache.

    Useful for testing or when settings change.
    """
    get_storage.cache_clear()
