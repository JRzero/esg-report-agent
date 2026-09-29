import json
from typing import TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMGateway:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        settings = get_settings()
        self.client = client
        self.base_url = (base_url if base_url is not None else settings.llm_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model or settings.llm_model

    async def generate_structured(
        self,
        system: str,
        user: str,
        schema: type[T],
        model_profile: str = "STRONG",
    ) -> T:
        if not self.base_url:
            raise RuntimeError("LLM_BASE_URL is not configured")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async def request(client: httpx.AsyncClient):
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

        if self.client:
            data = await request(self.client)
        else:
            async with httpx.AsyncClient(timeout=120) as client:
                data = await request(client)

        content = data["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            if content.startswith("json"):
                content = content[4:].lstrip()
        return schema.model_validate(json.loads(content))
