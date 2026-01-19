"""Local filesystem storage backend for development."""

import logging
from pathlib import Path

import aiofiles
import aiofiles.os

from app.storage.exceptions import (
    StorageDeleteError,
    StorageError,
    StorageFileNotFoundError,
    StorageUploadError,
)

logger = logging.getLogger(__name__)


class LocalStorageBackend:
    """Local filesystem storage backend.

    Stores files in a configurable directory, suitable for development.
    Files are served via a separate endpoint at /files/{key}.
    """

    def __init__(self, base_path: str = "./storage"):
        """Initialize the local storage backend.

        Args:
            base_path: Root directory for file storage
        """
        self.base_path = Path(base_path).resolve()
        # Ensure the base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _sanitize_key(self, key: str) -> Path:
        """Sanitize a storage key to prevent directory traversal attacks.

        Args:
            key: The storage key to sanitize

        Returns:
            Resolved path within the base directory

        Raises:
            StorageError: If the key would escape the base directory
        """
        # Remove any leading slashes and normalize
        clean_key = key.lstrip("/").replace("\\", "/")

        # Build the full path
        full_path = (self.base_path / clean_key).resolve()

        # Verify the path is within our base directory
        try:
            full_path.relative_to(self.base_path)
        except ValueError as e:
            raise StorageError(f"Invalid storage key: {key}", key=key) from e

        return full_path

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Upload a file to local storage.

        Args:
            key: Storage key/path for the file
            data: File content as bytes
            content_type: MIME type (stored as metadata, not used for local)

        Returns:
            The storage key where the file was stored
        """
        file_path = self._sanitize_key(key)

        try:
            # Create parent directories if needed
            await aiofiles.os.makedirs(file_path.parent, exist_ok=True)

            # Write the file
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(data)

            logger.info(f"Uploaded file to local storage: {key}")
            return key

        except OSError as e:
            logger.error(f"Failed to upload file {key}: {e}")
            raise StorageUploadError(key, str(e)) from e

    async def download(self, key: str) -> bytes:
        """Download a file from local storage.

        Args:
            key: Storage key/path of the file

        Returns:
            File content as bytes
        """
        file_path = self._sanitize_key(key)

        if not file_path.exists():
            raise StorageFileNotFoundError(key)

        try:
            async with aiofiles.open(file_path, "rb") as f:
                return await f.read()
        except OSError as e:
            logger.error(f"Failed to download file {key}: {e}")
            raise StorageError(f"Failed to read {key}: {e}", key=key) from e

    async def delete(self, key: str) -> bool:
        """Delete a file from local storage.

        Args:
            key: Storage key/path of the file

        Returns:
            True if file was deleted, False if it didn't exist
        """
        file_path = self._sanitize_key(key)

        if not file_path.exists():
            return False

        try:
            await aiofiles.os.remove(file_path)
            logger.info(f"Deleted file from local storage: {key}")

            # Try to remove empty parent directories (cleanup)
            try:
                parent = file_path.parent
                while parent != self.base_path:
                    if not any(parent.iterdir()):
                        await aiofiles.os.rmdir(parent)
                        parent = parent.parent
                    else:
                        break
            except OSError:
                pass  # Ignore errors during cleanup

            return True

        except OSError as e:
            logger.error(f"Failed to delete file {key}: {e}")
            raise StorageDeleteError(key, str(e)) from e

    async def exists(self, key: str) -> bool:
        """Check if a file exists in local storage.

        Args:
            key: Storage key/path of the file

        Returns:
            True if file exists, False otherwise
        """
        file_path = self._sanitize_key(key)
        return file_path.exists()

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Get a URL to access the file.

        For local storage, returns a path to the file serving endpoint.
        The expires_in parameter is ignored for local storage.

        Args:
            key: Storage key/path of the file
            expires_in: Ignored for local storage

        Returns:
            URL path to the file serving endpoint
        """
        file_path = self._sanitize_key(key)

        if not file_path.exists():
            raise StorageFileNotFoundError(key)

        # Return the URL path for the file serving endpoint
        return f"/files/{key}"
