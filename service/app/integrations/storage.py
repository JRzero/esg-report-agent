import asyncio
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
    async def healthcheck(self) -> bool: ...


class LocalStorage:
    def __init__(self, path: str):
        self.root = Path(path)
        self.root.mkdir(parents=True, exist_ok=True)

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread((self.root / key).read_bytes)

    async def delete(self, key: str) -> None:
        path = self.root / key
        if path.exists():
            await asyncio.to_thread(path.unlink)

    async def exists(self, key: str) -> bool:
        return (self.root / key).exists()

    async def signed_download_url(self, key: str, expires: int = 900) -> str:
        return f"file://{(self.root / key).absolute()}"

    async def healthcheck(self) -> bool:
        return self.root.exists() and self.root.is_dir()


class MinioStorage:
    def __init__(self):
        from minio import Minio

        s = get_settings()
        self.client = Minio(
            s.minio_endpoint,
            access_key=s.minio_access_key,
            secret_key=s.minio_secret_key,
            secure=s.minio_secure,
        )
        self.bucket = s.minio_bucket

    async def _ensure_bucket(self) -> None:
        exists = await asyncio.to_thread(self.client.bucket_exists, self.bucket)
        if not exists:
            await asyncio.to_thread(self.client.make_bucket, self.bucket)

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        await self._ensure_bucket()
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket,
            key,
            BytesIO(data),
            len(data),
            content_type or "application/octet-stream",
        )

    async def get(self, key: str) -> bytes:
        response = await asyncio.to_thread(self.client.get_object, self.bucket, key)
        try:
            return await asyncio.to_thread(response.read)
        finally:
            response.close()
            response.release_conn()

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.remove_object, self.bucket, key)

    async def exists(self, key: str) -> bool:
        try:
            await asyncio.to_thread(self.client.stat_object, self.bucket, key)
            return True
        except Exception:
            return False

    async def signed_download_url(self, key: str, expires: int = 900) -> str:
        from datetime import timedelta

        return await asyncio.to_thread(
            self.client.presigned_get_object,
            self.bucket,
            key,
            expires=timedelta(seconds=expires),
        )

    async def healthcheck(self) -> bool:
        try:
            await asyncio.to_thread(self.client.list_buckets)
            return True
        except Exception:
            return False


def storage() -> ObjectStorage:
    s = get_settings()
    if s.storage_backend == "minio":
        return MinioStorage()
    return LocalStorage(s.local_storage_path)
