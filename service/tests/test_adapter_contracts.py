from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from app.ai.llm import LLMGateway
from app.ai.openviking import OpenVikingAdapter
from app.core.config import get_settings


class Answer(BaseModel):
    answer: str


@pytest.mark.asyncio
async def test_llm_openai_compatible_contract(monkeypatch):
    settings = get_settings()
    settings.llm_base_url = "http://llm.test/v1"
    settings.llm_api_key = "secret"
    settings.llm_model = "test-model"

    async def handler(request: httpx.Request):
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"ok"}'}}]},
        )

    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: original(transport=transport, **kwargs),
    )
    result = await LLMGateway().generate_structured("system", "user", Answer)
    assert result.answer == "ok"


@pytest.mark.asyncio
async def test_openviking_ingest_and_find_contract(monkeypatch):
    settings = get_settings()
    settings.openviking_enabled = True
    settings.openviking_base_url = "http://viking.test"
    settings.openviking_api_key = "key"
    settings.openviking_upload_mode = "shared"

    async def handler(request: httpx.Request):
        if request.url.path == "/ready":
            assert "X-API-Key" not in request.headers
            return httpx.Response(200, json={"status": "ready"})
        assert request.headers["X-API-Key"] == "key"
        if request.url.path.endswith("/temp_upload"):
            assert b'name="upload_mode"' in request.content
            assert b"shared" in request.content
            return httpx.Response(200, json={"result": {"temp_file_id": "tmp-1"}})
        if request.url.path == "/api/v1/resources":
            body = json.loads(request.content)
            assert body["temp_file_id"] == "tmp-1"
            assert body["to"].startswith("viking://resources/projects/")
            return httpx.Response(200, json={"result": {"root_uri": body["to"], "task_id": "task-1"}})
        if request.url.path == "/api/v1/search/find":
            body = json.loads(request.content)
            assert body["target_uri"] == "viking://resources/projects/p1/evidence"
            return httpx.Response(
                200,
                json={
                    "result": {
                        "results": [
                            {
                                "uri": "viking://resources/projects/p1/evidence/a",
                                "content": "1287",
                                "score": 0.9,
                            }
                        ]
                    }
                },
            )
        raise AssertionError(request.url)

    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: original(transport=transport, **kwargs),
    )

    adapter = OpenVikingAdapter()
    assert await adapter.ready() is True
    result = await adapter.add_bytes(
        "employees.xlsx",
        b"data",
        "viking://resources/projects/p1/evidence/employees",
    )
    assert result["task_id"] == "task-1"
    rows = await adapter.find(
        "employee total",
        "viking://resources/projects/p1/evidence",
    )
    assert len(rows) == 1
    assert rows[0].content == "1287"
