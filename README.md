# ESG Report Agent

Enterprise ESG report production platform built around evidence, confirmed facts, disclosure mapping, and traceable AI-assisted writing.

## Repository layout

- `service/` — FastAPI service, Celery workers, migrations, parsers, AI runtime, tests
- `web/` — Next.js + Astryx frontend and ESG domain design system
- `specs/` — spec-driven product/engineering requirements and implementation tasks
- `docs/` — API contract and generated OpenAPI material
- `deploy/` — local/production deployment assets
- `AGENTS.md` — engineering invariants for humans and coding agents

## Current focus

The backend Service MVP, production hardening and ESG Agent evaluation gates are accepted. Frontend work now begins at the foundation/design-system layer only.

Current product chain:

`Document → Evidence Anchor → Fact → Disclosure → Report → Claim → Citation → Verification → DOCX`

Current frontend foundation:

`Next.js → Astryx → ESG Domain Components → Service API`

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


## Authentication & Project Workspace

The first real frontend vertical slice is implemented:

```text
/login
  ↓
Next.js HttpOnly BFF session
  ↓
/projects
  ↓
/projects/new
  ↓
/projects/{projectId}
```

Project-scoped navigation is now stable for Materials, Facts, Reports, GRI, Missing Data and Members.
Those later modules remain explicit placeholders until their own specs are implemented.


## Material Center & Evidence Viewer

The project Materials route is now a real evidence workflow:

```text
Project
  ↓
Material upload
  ↓
Immutable DocumentVersion
  ↓
Service parser
  ↓
DocumentAnchor
  ↓
Evidence Viewer
  ↓
Fact Extraction task
```

Reference and Standard sources remain separated from enterprise Evidence in both UI and action availability.
