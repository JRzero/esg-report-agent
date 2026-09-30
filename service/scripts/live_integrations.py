"""Optional live smoke checks for external AI/context providers.

Usage:
  RUN_LIVE_INTEGRATIONS=true uv run python scripts/live_integrations.py

Required for LLM smoke:
  LLM_BASE_URL, LLM_MODEL (LLM_API_KEY when provider requires it)

Required for OpenViking smoke:
  OPENVIKING_ENABLED=true, OPENVIKING_BASE_URL
  OPENVIKING_API_KEY when configured by the server
"""
import asyncio
import os
from uuid import uuid4

from pydantic import BaseModel

from app.ai.llm import LLMGateway
from app.ai.openviking import OpenVikingAdapter
from app.core.config import get_settings


class SmokeAnswer(BaseModel):
    answer: str


async def main() -> None:
    if os.getenv("RUN_LIVE_INTEGRATIONS", "").lower() != "true":
        raise SystemExit("Set RUN_LIVE_INTEGRATIONS=true to run external live smoke checks.")

    settings = get_settings()
    results: dict[str, str] = {}

    if settings.llm_base_url:
        result = await LLMGateway().generate_structured(
            "Return valid JSON only.",
            'Return {"answer":"ok"}.',
            SmokeAnswer,
        )
        if result.answer.lower() != "ok":
            raise RuntimeError(f"Unexpected LLM smoke result: {result.answer}")
        results["llm"] = "PASS"
    else:
        results["llm"] = "SKIPPED_NOT_CONFIGURED"

    if settings.openviking_enabled:
        adapter = OpenVikingAdapter()
        marker = uuid4().hex
        target = f"viking://resources/projects/live-smoke/evidence/{marker}/smoke.txt"
        result = await adapter.add_bytes(
            "smoke.txt",
            f"ESG live smoke {marker}".encode(),
            target,
            reason="ESG Report Agent live integration smoke",
        )
        task_id = result.get("task_id")
        if task_id:
            await adapter.get_task(task_id)
        rows = await adapter.find(
            marker,
            "viking://resources/projects/live-smoke/evidence",
            limit=5,
        )
        if not isinstance(rows, list):
            raise RuntimeError("OpenViking search did not return a result list")
        results["openviking"] = "PASS"
    else:
        results["openviking"] = "SKIPPED_DISABLED"

    print(results)


if __name__ == "__main__":
    asyncio.run(main())
