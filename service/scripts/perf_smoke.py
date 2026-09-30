"""Lightweight HTTP performance smoke for a running service.

This is a regression guard, not a capacity benchmark.
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
    base = os.getenv("SERVICE_BASE_URL", "http://localhost:8000").rstrip("/")
    requests = int(os.getenv("PERF_REQUESTS", "100"))
    concurrency = int(os.getenv("PERF_CONCURRENCY", "20"))
    max_p95_ms = float(os.getenv("PERF_MAX_P95_MS", "1000"))

    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=10) as client:
        latencies = await asyncio.gather(
            *(one(client, f"{base}/health", semaphore) for _ in range(requests))
        )

    ordered = sorted(latencies)
    p50 = statistics.median(ordered)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    result = {
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
