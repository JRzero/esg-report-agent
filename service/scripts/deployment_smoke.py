"""Smoke-test a running ESG Report Agent deployment.

Environment:
  SERVICE_BASE_URL=http://localhost:8000
  SMOKE_EMAIL / SMOKE_PASSWORD are optional. When supplied, auth/me is verified.
"""
import asyncio
import os

import httpx


async def main() -> None:
    base = os.getenv("SERVICE_BASE_URL", "http://localhost:8000").rstrip("/")
    async with httpx.AsyncClient(timeout=20) as client:
        health = await client.get(f"{base}/health")
        health.raise_for_status()
        if health.json().get("status") != "ok":
            raise RuntimeError(f"Unexpected health response: {health.text}")

        ready = await client.get(f"{base}/ready")
        ready.raise_for_status()
        if ready.json().get("status") != "ready":
            raise RuntimeError(f"Unexpected readiness response: {ready.text}")

        email = os.getenv("SMOKE_EMAIL")
        password = os.getenv("SMOKE_PASSWORD")
        if email and password:
            login = await client.post(
                f"{base}/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            login.raise_for_status()
            token = login.json()["access_token"]
            me = await client.get(
                f"{base}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            me.raise_for_status()

    print({"service": "PASS", "auth": "PASS" if email and password else "SKIPPED"})


if __name__ == "__main__":
    asyncio.run(main())
