# ESG Report Agent Service Production-Hardening Acceptance Report

Date: 2026-09-30  
Scope: Backend Service only. Frontend remains frozen.

## Result

**Production-Hardening Deterministic Acceptance: PASS**

GitHub Actions Service CI run **36661656664** passed all configured gates on the hardening branch.

Observed automated results:

- fatal Ruff/static checks: PASS
- Python compileall: PASS
- dependency consistency: PASS
- PostgreSQL migration from an empty database: PASS
- PostgreSQL forward upgrade from frozen accepted v1 schema to current head: PASS
- pytest production-hardening suite: **27 passed**
- lightweight ASGI performance smoke:
  - requests: 100
  - concurrency: 20
  - p50: **17.75 ms**
  - p95: **69.37 ms**
  - acceptance ceiling: 1000 ms
- service Docker image build: PASS
- non-root container runtime verification: PASS

The performance smoke is a regression guard for the CI environment, not a production capacity claim.

## Production-hardening changes

### 1. Concurrency-safe idempotency

AI-task idempotency is scoped to:

> tenant + authenticated principal + Idempotency-Key

Task creation uses PostgreSQL atomic conflict handling rather than select-then-insert.

Verified behavior:

- two tenants may use the same key independently
- twenty concurrent submissions using the same principal/key create exactly one task
- reusing a key for different request semantics returns a conflict instead of silently reusing a task

### 2. Worker duplicate-delivery protection

AI and document workers claim work through conditional database state transitions.

AI execution:

```text
PENDING -> RUNNING -> SUCCESS
                 \-> FAILED
                 \-> CANCELLED
```

Only one duplicate delivery can claim a PENDING task. Final success is also guarded by a
`WHERE status = RUNNING` transition.

Document parsing similarly atomically claims PENDING document versions.

### 3. Cancellation correctness

AI workflow writes are not committed before the final task-state commit gate.

If a running task is cancelled from another transaction, the final RUNNING-to-SUCCESS update fails and
the workflow transaction is rolled back. Acceptance verifies that an intentionally injected business
write does not survive cancellation.

### 4. Stale-work recovery

Periodic maintenance identifies stale RUNNING AI jobs and stale document-processing jobs and moves them
to explicit failure states rather than leaving permanent PROCESSING/RUNNING rows.

### 5. OpenViking isolation and reconciliation

OpenViking resources are namespaced by tenant and project:

```text
viking://resources/tenants/{tenant_id}/projects/{project_id}/...
```

Document Evidence remains valid even when OpenViking is unavailable.

Asynchronous OpenViking imports are reconciled in a maintenance task:

- completed -> READY
- failed/cancelled -> FAILED
- pending/running/cancelling -> remain PROCESSING
- repeated unknown/network reconciliation failures eventually -> FAILED

### 6. LLM resilience

The OpenAI-compatible gateway retries only transient failures:

- transport errors
- HTTP 429
- HTTP 500/502/503/504

Retries are bounded with exponential backoff. Permanent 4xx failures are not retried.

### 7. Resource exhaustion controls

Uploads are read incrementally and rejected as soon as they exceed `MAX_UPLOAD_BYTES`.

Document parsers enforce:

- maximum anchor count
- maximum extracted-text characters

This bounds pathological spreadsheet/PDF/Office parsing work at the application layer.

### 8. Production configuration validation

Production/staging startup rejects:

- default JWT secret
- JWT secret shorter than 32 characters
- default MinIO credentials when MinIO storage is selected
- invalid OpenViking/LLM URL schemes
- unsupported storage/upload-mode configuration

### 9. HTTP and observability baseline

Responses include baseline browser/API security headers.

Request middleware emits structured telemetry containing:

- request ID
- HTTP method
- path
- status
- duration

Production/staging logging uses structured JSON output.

### 10. Migration reproducibility

The original v1 migration no longer imports live application ORM metadata.

A frozen `migrations/schema_v1.py` snapshot defines the accepted initial schema, and CI verifies:

```text
empty DB -> current head
frozen v1 -> current head
```

This prevents future ORM changes from rewriting migration history.

### 11. Container/deployment hardening

The service image runs as a dedicated non-root `esg` user.

Docker Compose now includes:

- API
- worker
- Celery beat maintenance scheduler
- PostgreSQL
- Redis
- optional MinIO

## Failure/concurrency acceptance matrix

Automated tests cover:

- same idempotency key across tenants/principals
- twenty-way concurrent idempotent submission
- idempotency-key semantic mismatch
- duplicate Celery AI delivery
- cancel-during-execution rollback
- stale task recovery
- duplicate document delivery
- OpenViking tenant/project URI isolation
- OpenViking failure while Evidence remains usable
- OpenViking asynchronous reconciliation
- upload-size rejection
- parser anchor limit
- parser extracted-text limit
- unsafe production configuration rejection
- API security headers
- transient LLM retry
- permanent LLM error no-retry

These tests are in addition to the Service MVP business-flow acceptance suite.

## Deployment smoke tools

Running service:

```bash
SERVICE_BASE_URL=http://localhost:8000 uv run python scripts/deployment_smoke.py
```

Optional auth verification:

```bash
SERVICE_BASE_URL=http://localhost:8000 \
SMOKE_EMAIL=... \
SMOKE_PASSWORD=... \
uv run python scripts/deployment_smoke.py
```

External LLM/OpenViking integration:

```bash
RUN_LIVE_INTEGRATIONS=true uv run python scripts/live_integrations.py
```

Performance regression smoke:

```bash
PERF_IN_PROCESS=true uv run python scripts/perf_smoke.py
```

or against a deployed service:

```bash
SERVICE_BASE_URL=http://localhost:8000 uv run python scripts/perf_smoke.py
```

## External integration status

The deterministic HTTP contracts for LLM and OpenViking are accepted.

Real external OpenViking/LLM connectivity is **environment-dependent** and is only considered verified
after the explicit live integration script runs with the actual deployment endpoint and credentials.

Therefore:

- backend production-hardening contract: **PASS**
- concurrency/failure/security acceptance: **PASS**
- migration reproducibility: **PASS**
- container hardening: **PASS**
- deterministic adapter contracts: **PASS**
- real deployment-specific OpenViking/LLM connectivity: **READY TO RUN; NOT CLAIMED WITHOUT CREDENTIALS**

## Conclusion

The backend service is suitable to move from functional MVP acceptance into deployment-environment
integration and pre-frontend API stabilization.

Frontend development should begin only after the final hardening PR is merged and the resulting
`main` Service CI is green.
