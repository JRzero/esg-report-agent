# ESG Report Agent Service

Service-first backend for evidence-grounded ESG report production.

## Architecture

- FastAPI modular monolith
- PostgreSQL as business source of truth
- MinIO/S3-compatible object storage for immutable originals
- OpenViking as optional context/retrieval layer
- Redis/Celery for asynchronous processing
- Controlled AI workflows with evidence and confirmed-Fact boundaries

## Specs

Development is managed from repository-root `../specs/`:

- `001-foundation`
- `002-evidence-fact`
- `003-gri-intelligence`
- `004-report-agent`
- `005-service-acceptance`

The engineering rules are defined in `../specs/constitution.md`.

## Run locally

```bash
cp .env.example .env
docker compose -f ../deploy/docker-compose.yml up -d postgres redis minio
uv sync --extra dev
uv run alembic upgrade head
uv run python scripts/seed.py
uv run uvicorn app.main:app --reload
```

Swagger: `http://localhost:8000/docs`  
Runtime OpenAPI: `http://localhost:8000/openapi.json`

## Health

- `GET /health`: process liveness only
- `GET /ready`: verifies PostgreSQL, Redis and object storage

OpenViking and the LLM are intentionally **not** hard readiness dependencies. Their failure must not
make ordinary project, document, Fact or report CRUD unavailable.

## Automated acceptance

```bash
uv run ruff check app tests migrations scripts --select E9,F63,F7,F82
uv run python -m compileall -q app migrations scripts
uv run alembic upgrade head
uv run pytest -q
```

The acceptance suite covers:

- RBAC + Project Member isolation
- cross-tenant concealment
- document parsing and immutable anchors
- Evidence vs Reference enforcement
- Fact lifecycle, confirmation, revisions and conflicts
- GRI mapping, coverage and missing-data detection
- template/report/section/block lifecycle
- immutable block revisions and restore
- Claim/Citation verification and source trace
- AI task idempotency/cancel/retry
- DOCX export
- PostgreSQL/Redis/storage readiness
- OpenViking and OpenAI-compatible LLM HTTP contracts

See `../docs/service-acceptance-report.md`.

## External live smoke

Normal CI does not require third-party credentials. To validate a configured deployment against real
OpenViking and/or LLM endpoints:

```bash
RUN_LIVE_INTEGRATIONS=true uv run python scripts/live_integrations.py
```

Configure the relevant environment variables first:

```text
OPENVIKING_ENABLED=true
OPENVIKING_BASE_URL=...
OPENVIKING_API_KEY=...

LLM_BASE_URL=...
LLM_API_KEY=...
LLM_MODEL=...
```

The live check is opt-in and is not a substitute for the deterministic acceptance suite.

## Frontend

Frontend development is intentionally frozen during Service MVP acceptance. The future Next.js app
will consume the stable `/api/v1` contract from the repository-root `web/` directory.
