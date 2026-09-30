"""Optional live smoke checks for external AI/context providers."""
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
            '{"answer":"ok"}',
            SmokeAnswer,
        )
        if result.answer.lower() != "ok":
            raise RuntimeError(f"Unexpected LLM smoke result: {result.answer}")
        results["llm"] = "PASS"
    else:
        results["llm"] = "SKIPPED_NOT_CONFIGURED"

    if settings.openviking_enabled:
        adapter = OpenVikingAdapter()
        if not await adapter.ready():
            raise RuntimeError("OpenViking /ready did not report ready")

        marker = uuid4().hex
        root = "viking://resources/tenants/live-smoke/projects/smoke/evidence"
        target = f"{root}/{marker}/smoke.txt"
        result = await adapter.add_bytes(
            "smoke.txt",
            f"ESG live smoke {marker}".encode(),
            target,
            reason="ESG Report Agent live integration smoke",
        )
        task_id = result.get("task_id")
        if task_id:
            timeout = int(os.getenv("LIVE_OPENVIKING_TIMEOUT_SECONDS", "120"))
            deadline = asyncio.get_running_loop().time() + timeout
            while True:
                task = await adapter.get_task(task_id)
                status = str(task.get("status", "")).lower()
                if status == "completed":
                    break
                if status in {"failed", "cancelled"}:
                    raise RuntimeError(
                        f"OpenViking import {status}: {task.get('error') or 'unknown error'}"
                    )
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError(f"OpenViking import did not complete within {timeout}s")
                await asyncio.sleep(2)

        rows = await adapter.find(marker, root, limit=5)
        if not any(marker in (row.content or row.abstract or "") for row in rows):
            raise RuntimeError("OpenViking smoke resource was not retrievable after import completion")
        results["openviking"] = "PASS"
    else:
        results["openviking"] = "SKIPPED_DISABLED"

    print(results)


if __name__ == "__main__":
    asyncio.run(main())
