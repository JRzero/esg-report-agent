import pytest


@pytest.mark.asyncio
async def test_readiness_checks_postgres_redis_and_storage(client):
    response = await client.get("/ready")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "postgres": "ok",
            "redis": "ok",
            "storage": "ok",
        },
    }
