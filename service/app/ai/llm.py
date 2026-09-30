import json
from typing import TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


def _decode_json_content(content: str) -> dict:
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
        if value.startswith("json"):
            value = value[4:].lstrip()
    return json.loads(value)


class LLMGateway:
    async def generate_structured(
        self,
        system: str,
        user: str,
        schema: type[T],
        model_profile: str = "STRONG",
    ) -> T:
        settings = get_settings()
        if not settings.llm_base_url:
            raise RuntimeError("LLM_BASE_URL is not configured")
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        headers = {"Content-Type": "application/json"}
        if settings.llm_api_key:
            headers["Authorization"] = f"Bearer {settings.llm_api_key}"
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                settings.llm_base_url.rstrip("/") + "/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM response did not contain message content") from exc
        return schema.model_validate(_decode_json_content(content))
