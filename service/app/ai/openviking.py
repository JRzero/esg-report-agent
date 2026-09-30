from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class ContextSearchResult:
    uri: str
    content: str = ""
    abstract: str = ""
    score: float | None = None
    metadata: dict | None = None


class OpenVikingAdapter:
    """HTTP adapter for OpenViking context storage/retrieval.

    Business code only sees normalized results. The adapter is optional at runtime:
    evidence parsing and Fact workflows remain available when OpenViking is disabled.
    """

    def __init__(self):
        settings = get_settings()
        self.enabled = settings.openviking_enabled
        self.base = settings.openviking_base_url.rstrip("/")
        self.headers = (
            {"X-API-Key": settings.openviking_api_key}
            if settings.openviking_api_key
            else {}
        )

    def _require_enabled(self):
        if not self.enabled:
            raise RuntimeError("OpenViking integration is disabled")

    async def upload_temp(self, filename: str, data: bytes) -> str:
        self._require_enabled()
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base}/api/v1/resources/temp_upload",
                files={"file": (filename, data)},
                headers=self.headers,
            )
            response.raise_for_status()
            payload = response.json()
        result = payload.get("result", payload)
        temp_file_id = result.get("temp_file_id")
        if not temp_file_id:
            raise RuntimeError("OpenViking temp upload response missing temp_file_id")
        return temp_file_id

    async def add_bytes(
        self,
        filename: str,
        data: bytes,
        to_uri: str,
        reason: str = "ESG project evidence",
    ) -> dict:
        temp_id = await self.upload_temp(filename, data)
        body = {
            "temp_file_id": temp_id,
            "to": to_uri,
            "reason": reason,
            "wait": False,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base}/api/v1/resources",
                json=body,
                headers={**self.headers, "Content-Type": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        return payload.get("result", payload)

    async def get_task(self, task_id: str) -> dict:
        self._require_enabled()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base}/api/v1/tasks/{task_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            payload = response.json()
        return payload.get("result", payload)

    async def find(
        self,
        query: str,
        target_uri: str,
        limit: int = 10,
    ) -> list[ContextSearchResult]:
        self._require_enabled()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base}/api/v1/search/find",
                json={"query": query, "target_uri": target_uri, "limit": limit},
                headers={**self.headers, "Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
        payload = data.get("result", data)
        rows = payload.get("results", payload if isinstance(payload, list) else [])
        return [
            ContextSearchResult(
                uri=item.get("uri", ""),
                content=item.get("content", ""),
                abstract=item.get("abstract", ""),
                score=item.get("score"),
                metadata=item,
            )
            for item in rows
        ]
