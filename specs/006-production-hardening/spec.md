# Service Production Hardening

## Intent
Harden the accepted Service MVP for production-like operation before frontend development begins.

## Scope
- Tenant-scoped, concurrency-safe idempotency.
- Exactly-once task claiming under Celery redelivery.
- Cancellation race protection and rollback of in-flight AI writes.
- Recoverable document parsing and OpenViking reconciliation.
- OpenViking tenant/project namespace isolation.
- LLM transient retry/backoff.
- Streaming upload limits and parser resource limits.
- Production configuration validation and security headers.
- Non-root container runtime.
- Failure-injection, concurrency, security, and performance-smoke acceptance.
- Deployment smoke scripts for API, worker, Redis/PostgreSQL/storage, OpenViking, and LLM.

## Acceptance criteria
1. The same Idempotency-Key may be reused by different tenants without collision or data disclosure.
2. Concurrent submissions with the same tenant/key create exactly one AI task.
3. A duplicated Celery delivery cannot execute an AI task twice.
4. Cancelling a running AI task prevents uncommitted workflow writes from being committed.
5. Duplicate document-processing deliveries do not create duplicate anchors or duplicate OpenViking imports.
6. OpenViking asynchronous imports are reconciled to READY/FAILED terminal states.
7. OpenViking resource URIs are tenant- and project-scoped.
8. Transient LLM 429/5xx failures are retried with bounded backoff; permanent 4xx failures are not.
9. Upload size limits are enforced while streaming, before the full file is loaded into memory.
10. Parser limits bound anchors and extracted text to prevent pathological documents from exhausting service resources.
11. Production mode rejects unsafe JWT/default runtime configuration.
12. API responses include baseline security headers.
13. The service container runs as a non-root user.
14. PostgreSQL migrations upgrade the previous accepted schema without destructive reset.
15. CI contains deterministic concurrency/failure/security acceptance and a lightweight performance smoke.
16. Live deployment smoke remains explicit and credential-driven; CI does not claim external connectivity without real endpoints.
