# ESG Report Agent

Enterprise ESG report production platform built around evidence, confirmed facts, disclosure mapping, and traceable AI-assisted writing.

## Repository layout

- `service/` — FastAPI service, Celery workers, migrations, parsers, AI runtime, tests
- `web/` — reserved for the later Next.js application
- `specs/` — spec-driven product/engineering requirements and implementation tasks
- `docs/` — API contract and generated OpenAPI material
- `deploy/` — local/production deployment assets
- `AGENTS.md` — engineering invariants for humans and coding agents

## Current focus

Frontend development is intentionally deferred. The current delivery target is the service MVP:

`Document → Evidence Anchor → Fact → Disclosure → Report → Claim → Citation → Verification → DOCX`

## Run the service locally

```bash
cd service
cp .env.example .env
cd ../deploy
docker compose up -d postgres redis minio
cd ../service
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Swagger: `http://localhost:8000/docs`

## Tests

```bash
cd service
uv run pytest
```

## Specs

Development is governed by:

- `specs/constitution.md`
- `specs/001-foundation`
- `specs/002-evidence-fact`
- `specs/003-gri-intelligence`
- `specs/004-report-agent`
