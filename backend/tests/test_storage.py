"""
Tests for the storage abstraction layer (app/storage/).

Tests for LocalStorageBackend, S3StorageBackend, and the factory function.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.storage import (
    StorageError,
    StorageFileNotFoundError,
    clear_storage_cache,
    get_storage,
)
from app.storage.local import LocalStorageBackend
from app.storage.s3 import S3StorageBackend

# =============================================================================
# LocalStorageBackend Tests
# =============================================================================


class TestLocalStorageBackend:
    """Tests for local filesystem storage backend."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for storage tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def local_backend(self, temp_storage_dir):
        """Create a LocalStorageBackend with a temp directory."""
        return LocalStorageBackend(base_path=temp_storage_dir)

    @pytest.mark.asyncio
    async def test_upload_creates_file(self, local_backend, temp_storage_dir):
        """Test that upload creates a file in the storage directory."""
        key = "test/file.txt"
        data = b"Hello, World!"

        result = await local_backend.upload(key, data, "text/plain")

        assert result == key
        file_path = Path(temp_storage_dir) / key
        assert file_path.exists()
        assert file_path.read_bytes() == data

    @pytest.mark.asyncio
    async def test_upload_creates_nested_directories(self, local_backend, temp_storage_dir):
        """Test that upload creates nested directories as needed."""
        key = "deep/nested/path/file.pdf"
        data = b"PDF content"

        await local_backend.upload(key, data, "application/pdf")

        file_path = Path(temp_storage_dir) / key
        assert file_path.exists()

    @pytest.mark.asyncio
    async def test_download_returns_file_content(self, local_backend, temp_storage_dir):
        """Test that download returns the file content."""
        key = "test/file.txt"
        data = b"Test content for download"

        # First upload the file
        await local_backend.upload(key, data, "text/plain")

        # Then download it
        result = await local_backend.download(key)

        assert result == data

    @pytest.mark.asyncio
    async def test_download_nonexistent_file_raises(self, local_backend):
        """Test that downloading a nonexistent file raises StorageFileNotFoundError."""
        with pytest.raises(StorageFileNotFoundError):
            await local_backend.download("nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_delete_removes_file(self, local_backend, temp_storage_dir):
        """Test that delete removes a file."""
        key = "test/to-delete.txt"
        data = b"Delete me"

        await local_backend.upload(key, data, "text/plain")
        file_path = Path(temp_storage_dir) / key
        assert file_path.exists()

        result = await local_backend.delete(key)

        assert result is True
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, local_backend):
        """Test that deleting a nonexistent file returns False."""
        result = await local_backend.delete("nonexistent/file.txt")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing_file(self, local_backend):
        """Test exists returns True for existing files."""
        key = "test/exists.txt"
        await local_backend.upload(key, b"content", "text/plain")

        result = await local_backend.exists(key)

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_missing_file(self, local_backend):
        """Test exists returns False for missing files."""
        result = await local_backend.exists("nonexistent.txt")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_url_returns_file_path(self, local_backend):
        """Test get_url returns a /files/ path for local storage."""
        key = "test/file.pdf"
        await local_backend.upload(key, b"content", "application/pdf")

        url = await local_backend.get_url(key)

        assert url == f"/files/{key}"

    @pytest.mark.asyncio
    async def test_get_url_nonexistent_raises(self, local_backend):
        """Test get_url raises for nonexistent files."""
        with pytest.raises(StorageFileNotFoundError):
            await local_backend.get_url("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_sanitize_key_prevents_directory_traversal(self, local_backend):
        """Test that directory traversal attacks are prevented."""
        with pytest.raises(StorageError):
            await local_backend.upload("../../../etc/passwd", b"malicious", "text/plain")

    @pytest.mark.asyncio
    async def test_sanitize_key_normalizes_slashes(self, local_backend, temp_storage_dir):
        """Test that slashes are normalized."""
        key = "test\\windows\\path.txt"
        data = b"content"

        await local_backend.upload(key, data, "text/plain")

        # File should be stored with forward slashes
        file_path = Path(temp_storage_dir) / "test" / "windows" / "path.txt"
        assert file_path.exists()


# =============================================================================
# S3StorageBackend Tests
# =============================================================================


class TestS3StorageBackend:
    """Tests for S3-compatible storage backend."""

    @pytest.fixture
    def s3_backend(self):
        """Create an S3StorageBackend with mock credentials."""
        return S3StorageBackend(
            access_key_id="test-access-key",
            secret_access_key="test-secret-key",
            bucket_name="test-bucket",
            endpoint_url="https://s3.example.com",
            region="us-east-1",
        )

    @pytest.fixture
    def s3_backend_with_public_url(self):
        """Create an S3StorageBackend with public URL configured."""
        return S3StorageBackend(
            access_key_id="test-access-key",
            secret_access_key="test-secret-key",
            bucket_name="test-bucket",
            endpoint_url="https://s3.example.com",
            region="us-east-1",
            public_url_base="https://cdn.example.com",
        )

    @pytest.mark.asyncio
    async def test_upload_calls_put_object(self, s3_backend):
        """Test that upload calls S3 put_object."""
        mock_client = AsyncMock()

        with patch.object(s3_backend, "_get_client") as mock_ctx:
            mock_ctx.return_value.__aenter__.return_value = mock_client

            result = await s3_backend.upload("test/file.pdf", b"content", "application/pdf")

        assert result == "test/file.pdf"
        mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/file.pdf",
            Body=b"content",
            ContentType="application/pdf",
        )

    @pytest.mark.asyncio
    async def test_download_calls_get_object(self, s3_backend):
        """Test that download calls S3 get_object."""
        mock_client = AsyncMock()
        # The Body is an async context manager that returns a stream
        mock_stream = AsyncMock()
        mock_stream.read.return_value = b"file content"
        mock_body = AsyncMock()
        mock_body.__aenter__.return_value = mock_stream
        mock_client.get_object.return_value = {"Body": mock_body}

        with patch.object(s3_backend, "_get_client") as mock_ctx:
            mock_ctx.return_value.__aenter__.return_value = mock_client

            result = await s3_backend.download("test/file.pdf")

        assert result == b"file content"

    @pytest.mark.asyncio
    async def test_download_not_found_raises(self, s3_backend):
        """Test that download raises StorageFileNotFoundError for missing files."""
        from botocore.exceptions import ClientError

        mock_client = AsyncMock()
        mock_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )

        with patch.object(s3_backend, "_get_client") as mock_ctx:
            mock_ctx.return_value.__aenter__.return_value = mock_client

            with pytest.raises(StorageFileNotFoundError):
                await s3_backend.download("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_delete_calls_delete_object(self, s3_backend):
        """Test that delete calls S3 delete_object."""
        mock_client = AsyncMock()
        mock_client.head_object.return_value = {}  # File exists

        with patch.object(s3_backend, "_get_client") as mock_ctx:
            mock_ctx.return_value.__aenter__.return_value = mock_client

            result = await s3_backend.delete("test/file.pdf")

        assert result is True
        mock_client.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, s3_backend):
        """Test that deleting nonexistent file returns False."""
        from botocore.exceptions import ClientError

        mock_client = AsyncMock()
        mock_client.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")

        with patch.object(s3_backend, "_get_client") as mock_ctx:
            mock_ctx.return_value.__aenter__.return_value = mock_client

            result = await s3_backend.delete("nonexistent.txt")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing(self, s3_backend):
        """Test exists returns True for existing files."""
        mock_client = AsyncMock()
        mock_client.head_object.return_value = {}

        with patch.object(s3_backend, "_get_client") as mock_ctx:
            mock_ctx.return_value.__aenter__.return_value = mock_client

            result = await s3_backend.exists("test/file.pdf")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_missing(self, s3_backend):
        """Test exists returns False for missing files."""
        from botocore.exceptions import ClientError

        mock_client = AsyncMock()
        mock_client.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")

        with patch.object(s3_backend, "_get_client") as mock_ctx:
            mock_ctx.return_value.__aenter__.return_value = mock_client

            result = await s3_backend.exists("nonexistent.txt")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_url_returns_presigned_url(self, s3_backend):
        """Test get_url generates presigned URL when no public URL configured."""
        mock_client = AsyncMock()
        mock_client.head_object.return_value = {}  # File exists
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/signed-url"

        with patch.object(s3_backend, "_get_client") as mock_ctx:
            mock_ctx.return_value.__aenter__.return_value = mock_client

            url = await s3_backend.get_url("test/file.pdf", expires_in=3600)

        assert url == "https://s3.example.com/signed-url"
        mock_client.generate_presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_url_returns_public_url(self, s3_backend_with_public_url):
        """Test get_url returns public URL when configured."""
        mock_client = AsyncMock()
        mock_client.head_object.return_value = {}  # File exists

        with patch.object(s3_backend_with_public_url, "_get_client") as mock_ctx:
            mock_ctx.return_value.__aenter__.return_value = mock_client

            url = await s3_backend_with_public_url.get_url("test/file.pdf")

        assert url == "https://cdn.example.com/test/file.pdf"
        mock_client.generate_presigned_url.assert_not_called()


# =============================================================================
# Factory Tests
# =============================================================================


class TestStorageFactory:
    """Tests for the storage factory function."""

    def teardown_method(self):
        """Clear storage cache after each test."""
        clear_storage_cache()

    @pytest.mark.asyncio
    async def test_get_storage_returns_local_by_default(self):
        """Test that get_storage returns LocalStorageBackend by default."""
        with patch("app.storage.factory.get_settings") as mock_settings:
            mock_settings.return_value.storage_backend = "local"
            mock_settings.return_value.local_storage_path = "./storage"

            storage = get_storage()

        assert isinstance(storage, LocalStorageBackend)

    @pytest.mark.asyncio
    async def test_get_storage_returns_s3_backend(self):
        """Test that get_storage returns S3StorageBackend for s3 config."""
        with patch("app.storage.factory.get_settings") as mock_settings:
            mock_settings.return_value.storage_backend = "s3"
            mock_settings.return_value.s3_access_key_id = "access-key"
            mock_settings.return_value.s3_secret_access_key = "secret-key"
            mock_settings.return_value.s3_bucket_name = "test-bucket"
            mock_settings.return_value.s3_endpoint_url = ""
            mock_settings.return_value.s3_region = "us-east-1"

            storage = get_storage()

        assert isinstance(storage, S3StorageBackend)

    @pytest.mark.asyncio
    async def test_get_storage_returns_r2_backend(self):
        """Test that get_storage returns S3StorageBackend for r2 config."""
        with patch("app.storage.factory.get_settings") as mock_settings:
            mock_settings.return_value.storage_backend = "r2"
            mock_settings.return_value.r2_access_key_id = "r2-access-key"
            mock_settings.return_value.r2_secret_access_key = "r2-secret-key"
            mock_settings.return_value.r2_bucket_name = "test-bucket"
            mock_settings.return_value.r2_endpoint = "https://r2.example.com"
            mock_settings.return_value.r2_public_url_base = ""

            storage = get_storage()

        assert isinstance(storage, S3StorageBackend)

    def test_get_storage_raises_for_unknown_backend(self):
        """Test that get_storage raises ValueError for unknown backend."""
        with patch("app.storage.factory.get_settings") as mock_settings:
            mock_settings.return_value.storage_backend = "unknown"

            with pytest.raises(ValueError, match="Unknown storage backend"):
                get_storage()

    def test_get_storage_raises_for_missing_s3_credentials(self):
        """Test that get_storage raises for missing S3 credentials."""
        with patch("app.storage.factory.get_settings") as mock_settings:
            mock_settings.return_value.storage_backend = "s3"
            mock_settings.return_value.s3_access_key_id = ""
            mock_settings.return_value.s3_secret_access_key = ""

            with pytest.raises(ValueError, match="S3_ACCESS_KEY_ID"):
                get_storage()

    def test_get_storage_raises_for_missing_r2_endpoint(self):
        """Test that get_storage raises for missing R2 endpoint."""
        with patch("app.storage.factory.get_settings") as mock_settings:
            mock_settings.return_value.storage_backend = "r2"
            mock_settings.return_value.r2_access_key_id = "key"
            mock_settings.return_value.r2_secret_access_key = "secret"
            mock_settings.return_value.r2_bucket_name = "bucket"
            mock_settings.return_value.r2_endpoint = ""

            with pytest.raises(ValueError, match="R2_ENDPOINT"):
                get_storage()

    def test_get_storage_is_cached(self):
        """Test that get_storage returns the same instance."""
        with patch("app.storage.factory.get_settings") as mock_settings:
            mock_settings.return_value.storage_backend = "local"
            mock_settings.return_value.local_storage_path = "./storage"

            storage1 = get_storage()
            storage2 = get_storage()

        assert storage1 is storage2

    def test_clear_storage_cache_resets_cache(self):
        """Test that clear_storage_cache allows creating new instance."""
        with patch("app.storage.factory.get_settings") as mock_settings:
            mock_settings.return_value.storage_backend = "local"
            mock_settings.return_value.local_storage_path = "./storage1"

            storage1 = get_storage()
            clear_storage_cache()

            mock_settings.return_value.local_storage_path = "./storage2"
            storage2 = get_storage()

        # Different paths means different instances
        assert storage1.base_path != storage2.base_path
