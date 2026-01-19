"""File serving endpoint for local development storage."""

import logging
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.config import get_settings
from app.models import User
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{file_path:path}")
async def serve_file(
    file_path: str,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Serve a file from local storage.

    This endpoint is only used when STORAGE_BACKEND=local.
    For S3/R2 storage, use presigned URLs from the storage backend.

    Security: Verifies the file path contains the current user's ID to prevent
    unauthorized access to other users' files.
    """
    settings = get_settings()

    # Only serve files when using local storage
    if settings.storage_backend.lower() != "local":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File serving is only available with local storage backend",
        )

    # Verify the user owns this file by checking the path contains their user ID
    # Expected format: uploads/{user_id}/{uuid}_{filename}
    user_id_str = str(current_user.id)
    if user_id_str not in file_path:
        logger.warning(f"User {current_user.id} attempted to access file: {file_path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this file",
        )

    # Build the full path and verify it's within the storage directory
    storage_path = Path(settings.local_storage_path).resolve()
    full_path = (storage_path / file_path).resolve()

    # Security check: ensure the path doesn't escape the storage directory
    try:
        full_path.relative_to(storage_path)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid file path",
        ) from e

    # Check if file exists
    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Determine content type
    content_type, _ = mimetypes.guess_type(str(full_path))
    if content_type is None:
        content_type = "application/octet-stream"

    return FileResponse(
        path=full_path,
        media_type=content_type,
        filename=full_path.name,
    )
