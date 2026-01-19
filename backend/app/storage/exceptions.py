"""Storage exceptions for the Alexandria storage abstraction layer."""


class StorageError(Exception):
    """Base exception for storage operations."""

    def __init__(self, message: str, key: str | None = None):
        self.key = key
        super().__init__(message)


class StorageFileNotFoundError(StorageError):
    """Raised when a requested file does not exist in storage."""

    def __init__(self, key: str):
        super().__init__(f"File not found: {key}", key=key)


class StorageUploadError(StorageError):
    """Raised when a file upload fails."""

    def __init__(self, key: str, reason: str):
        super().__init__(f"Failed to upload {key}: {reason}", key=key)


class StorageDeleteError(StorageError):
    """Raised when a file deletion fails."""

    def __init__(self, key: str, reason: str):
        super().__init__(f"Failed to delete {key}: {reason}", key=key)
