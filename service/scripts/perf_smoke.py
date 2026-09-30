"""Lightweight performance smoke.

This is a regression guard, not a capacity benchmark.

Set PERF_IN_PROCESS=true for deterministic CI against the ASGI app.
Otherwise SERVICE_BASE_URL targets a running deployment.
"""
import asyncio
import os
import statistics
import time

import httpx


async def one(client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore) -> float:
    async with semaphore:
        start = time.perf_counter()
        response = await client.get(url)
        response.raise_for_status()
        return (time.perf_counter() - start) * 1000


async def main() -> None:
    requests = int(os.getenv("PERF_REQUESTS", "100"))
    concurrency = int(os.getenv("PERF_CONCURRENCY", "20"))
    max_p95_ms = float(os.getenv("PERF_MAX_P95_MS", "1000"))
    in_process = os.getenv("PERF_IN_PROCESS", "").lower() == "true"

    semaphore = asyncio.Semaphore(concurrency)
    if in_process:
        from app.main import app

        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://test", timeout=10)
        url = "/health"
    else:
        base = os.getenv("SERVICE_BASE_URL", "http://localhost:8000").rstrip("/")
        client = httpx.AsyncClient(timeout=10)
        url = f"{base}/health"

    async with client:
        latencies = await asyncio.gather(
            *(one(client, url, semaphore) for _ in range(requests))
        )

    ordered = sorted(latencies)
    p50 = statistics.median(ordered)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    result = {
        "mode": "in-process" if in_process else "http",
        "requests": requests,
        "concurrency": concurrency,
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "max_p95_ms": max_p95_ms,
    }
    print(result)
    if p95 > max_p95_ms:
        raise SystemExit(f"p95 latency {p95:.2f}ms exceeded {max_p95_ms:.2f}ms")


if __name__ == "__main__":
    asyncio.run(main())
