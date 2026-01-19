"""Base protocol for storage backends."""

from typing import Protocol


class StorageBackend(Protocol):
    """Protocol defining the interface for storage backends.

    All storage backends (local, S3, R2) must implement this interface.
    Methods are async to support non-blocking I/O operations.
    """

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Upload a file to storage.

        Args:
            key: Storage key/path for the file (e.g., "uploads/user-id/file.pdf")
            data: File content as bytes
            content_type: MIME type (e.g., "application/pdf")

        Returns:
            The storage key where the file was stored

        Raises:
            StorageUploadError: If the upload fails
        """
        ...

    async def download(self, key: str) -> bytes:
        """Download a file from storage.

        Args:
            key: Storage key/path of the file

        Returns:
            File content as bytes

        Raises:
            StorageFileNotFoundError: If the file does not exist
            StorageError: If the download fails
        """
        ...

    async def delete(self, key: str) -> bool:
        """Delete a file from storage.

        Args:
            key: Storage key/path of the file

        Returns:
            True if file was deleted, False if it didn't exist

        Raises:
            StorageDeleteError: If deletion fails
        """
        ...

    async def exists(self, key: str) -> bool:
        """Check if a file exists in storage.

        Args:
            key: Storage key/path of the file

        Returns:
            True if file exists, False otherwise
        """
        ...

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Get a URL to access the file.

        Args:
            key: Storage key/path of the file
            expires_in: URL expiration time in seconds (for presigned URLs)

        Returns:
            URL to access the file (presigned for S3/R2, local path for local storage)

        Raises:
            StorageFileNotFoundError: If the file does not exist
        """
        ...
