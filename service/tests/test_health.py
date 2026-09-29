import pytest


@pytest.mark.asyncio
async def test_health_and_readiness(client):
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    readiness = await client.get("/ready")
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["dependencies"] == {
        "postgres": "ok",
        "redis": "ok",
        "storage": "ok",
    }
