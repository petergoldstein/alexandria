"""S3-compatible storage backend for AWS S3 and Cloudflare R2."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aioboto3
from botocore.exceptions import ClientError

from app.storage.exceptions import (
    StorageDeleteError,
    StorageError,
    StorageFileNotFoundError,
    StorageUploadError,
)

logger = logging.getLogger(__name__)


class S3StorageBackend:
    """S3-compatible storage backend.

    Works with AWS S3 and Cloudflare R2 (which is S3-compatible).
    Uses aioboto3 for async operations.
    """

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        endpoint_url: str | None = None,
        region: str = "us-east-1",
        public_url_base: str | None = None,
    ):
        """Initialize the S3 storage backend.

        Args:
            access_key_id: AWS access key ID or R2 access key
            secret_access_key: AWS secret access key or R2 secret
            bucket_name: Name of the S3/R2 bucket
            endpoint_url: Custom endpoint URL (required for R2, optional for S3)
            region: AWS region (default: us-east-1)
            public_url_base: Base URL for public bucket access (e.g., "https://pub.example.com")
        """
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region = region
        self.public_url_base = public_url_base.rstrip("/") if public_url_base else None

        # Create the aioboto3 session
        self.session = aioboto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    @asynccontextmanager
    async def _get_client(self) -> AsyncGenerator:
        """Get an async S3 client."""
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
        ) as client:
            yield client

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Upload a file to S3/R2.

        Args:
            key: Storage key/path for the file
            data: File content as bytes
            content_type: MIME type

        Returns:
            The storage key where the file was stored
        """
        try:
            async with self._get_client() as client:
                await client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                )

            logger.info(f"Uploaded file to S3/R2: {key}")
            return key

        except ClientError as e:
            logger.error(f"Failed to upload file {key}: {e}")
            raise StorageUploadError(key, str(e)) from e

    async def download(self, key: str) -> bytes:
        """Download a file from S3/R2.

        Args:
            key: Storage key/path of the file

        Returns:
            File content as bytes
        """
        try:
            async with self._get_client() as client:
                response = await client.get_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )
                async with response["Body"] as stream:
                    return await stream.read()

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise StorageFileNotFoundError(key) from e
            logger.error(f"Failed to download file {key}: {e}")
            raise StorageError(f"Failed to download {key}: {e}", key=key) from e

    async def delete(self, key: str) -> bool:
        """Delete a file from S3/R2.

        Args:
            key: Storage key/path of the file

        Returns:
            True if file was deleted, False if it didn't exist
        """
        # First check if file exists (S3 delete_object doesn't error on missing files)
        if not await self.exists(key):
            return False

        try:
            async with self._get_client() as client:
                await client.delete_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )

            logger.info(f"Deleted file from S3/R2: {key}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete file {key}: {e}")
            raise StorageDeleteError(key, str(e)) from e

    async def exists(self, key: str) -> bool:
        """Check if a file exists in S3/R2.

        Args:
            key: Storage key/path of the file

        Returns:
            True if file exists, False otherwise
        """
        try:
            async with self._get_client() as client:
                await client.head_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            # Re-raise other errors
            raise StorageError(f"Failed to check existence of {key}: {e}", key=key) from e

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Get a URL to access the file.

        If public_url_base is configured, returns a public URL.
        Otherwise, generates a presigned URL that expires after expires_in seconds.

        Args:
            key: Storage key/path of the file
            expires_in: URL expiration time in seconds (for presigned URLs)

        Returns:
            URL to access the file
        """
        # Verify file exists first
        if not await self.exists(key):
            raise StorageFileNotFoundError(key)

        # If public URL base is configured, use that
        if self.public_url_base:
            return f"{self.public_url_base}/{key}"

        # Otherwise, generate a presigned URL
        try:
            async with self._get_client() as client:
                url = await client.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": self.bucket_name,
                        "Key": key,
                    },
                    ExpiresIn=expires_in,
                )
                return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            raise StorageError(f"Failed to generate URL for {key}: {e}", key=key) from e
