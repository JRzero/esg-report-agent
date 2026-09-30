import asyncio
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class ObjectStorage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def signed_download_url(self, key: str, expires: int = 900) -> str: ...
    async def health(self) -> bool: ...


class LocalStorage:
    def __init__(self, path: str):
        self.root = Path(path)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        root = self.root.resolve()
        if root not in path.parents and path != root:
            raise ValueError("Invalid storage key")
        return path

    async def put(self, key: str, data: bytes, content_type: str | None = None):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def get(self, key: str):
        return self._path(key).read_bytes()

    async def delete(self, key: str):
        path = self._path(key)
        if path.exists():
            path.unlink()

    async def exists(self, key: str):
        return self._path(key).exists()

    async def signed_download_url(self, key: str, expires: int = 900):
        if not await self.exists(key):
            raise FileNotFoundError(key)
        return f"file://{self._path(key)}"

    async def health(self):
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root.exists()


class MinioStorage:
    def __init__(self):
        from minio import Minio

        settings = get_settings()
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket

    async def _ensure_bucket(self):
        exists = await asyncio.to_thread(self.client.bucket_exists, self.bucket)
        if not exists:
            await asyncio.to_thread(self.client.make_bucket, self.bucket)

    async def put(self, key: str, data: bytes, content_type: str | None = None):
        await self._ensure_bucket()
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket,
            key,
            BytesIO(data),
            len(data),
            content_type=content_type or "application/octet-stream",
        )

    async def get(self, key: str):
        response = await asyncio.to_thread(self.client.get_object, self.bucket, key)
        try:
            return await asyncio.to_thread(response.read)
        finally:
            response.close()
            response.release_conn()

    async def delete(self, key: str):
        await asyncio.to_thread(self.client.remove_object, self.bucket, key)

    async def exists(self, key: str):
        try:
            await asyncio.to_thread(self.client.stat_object, self.bucket, key)
            return True
        except Exception:
            return False

    async def signed_download_url(self, key: str, expires: int = 900):
        if not await self.exists(key):
            raise FileNotFoundError(key)
        return await asyncio.to_thread(
            self.client.presigned_get_object,
            self.bucket,
            key,
            expires=timedelta(seconds=expires),
        )

    async def health(self):
        try:
            await self._ensure_bucket()
            return True
        except Exception:
            return False


def storage() -> ObjectStorage:
    settings = get_settings()
    if settings.storage_backend == "minio":
        return MinioStorage()
    return LocalStorage(settings.local_storage_path)
