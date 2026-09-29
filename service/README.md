# ESG Report Agent Service

Service-first backend for evidence-grounded ESG report production.

## Architecture
- FastAPI modular monolith
- PostgreSQL as business source of truth
- MinIO/S3 for immutable originals
- OpenViking as context/retrieval layer
- Redis/Celery for async jobs
- Controlled Agent Runtime with versioned Skills

## Specs
Development is managed from repository-root `../specs/`:
- `001-foundation`
- `002-evidence-fact`
- `003-gri-intelligence`
- `004-report-agent`

## Run
```bash
cp .env.example .env
docker compose up -d postgres redis minio
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Swagger: `http://localhost:8000/docs`

## Tests
```bash
uv run pytest
```
