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
    """HTTP adapter for OpenViking.

    Business code receives normalized results and never depends on raw OpenViking
    response shapes.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        settings = get_settings()
        self.client = client
        self.base = (
            base_url if base_url is not None else settings.openviking_base_url
        ).rstrip("/")
        key = api_key if api_key is not None else settings.openviking_api_key
        self.headers = {"X-API-Key": key} if key else {}

    async def _request(self, method: str, path: str, **kwargs):
        async def invoke(client: httpx.AsyncClient):
            response = await client.request(
                method,
                f"{self.base}{path}",
                headers={**self.headers, **kwargs.pop("headers", {})},
                **kwargs,
            )
            response.raise_for_status()
            return response.json()

        if self.client:
            return await invoke(self.client)
        async with httpx.AsyncClient(timeout=60) as client:
            return await invoke(client)

    async def healthcheck(self) -> bool:
        try:
            data = await self._request("GET", "/health")
            return bool(data.get("healthy", data.get("status") == "ok"))
        except Exception:
            return False

    async def upload_temp(self, filename: str, data: bytes) -> str:
        payload = await self._request(
            "POST",
            "/api/v1/resources/temp_upload",
            files={"file": (filename, data)},
        )
        return payload["result"]["temp_file_id"]

    async def add_bytes(
        self,
        filename: str,
        data: bytes,
        to_uri: str,
        reason: str = "ESG project evidence",
    ) -> dict:
        temp_id = await self.upload_temp(filename, data)
        payload = await self._request(
            "POST",
            "/api/v1/resources",
            json={
                "temp_file_id": temp_id,
                "to": to_uri,
                "reason": reason,
                "wait": False,
            },
            headers={"Content-Type": "application/json"},
        )
        return payload.get("result", payload)

    async def get_task(self, task_id: str) -> dict:
        payload = await self._request("GET", f"/api/v1/tasks/{task_id}")
        return payload.get("result", payload)

    async def find(
        self,
        query: str,
        target_uri: str,
        limit: int = 10,
    ) -> list[ContextSearchResult]:
        data = await self._request(
            "POST",
            "/api/v1/search/find",
            json={"query": query, "target_uri": target_uri, "limit": limit},
            headers={"Content-Type": "application/json"},
        )
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
