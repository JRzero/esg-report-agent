# Service Hardening & Eval

## Intent
Harden the accepted Service MVP for production-like operation before frontend development.

## Acceptance criteria
- Tenant-scoped AI task idempotency cannot collide across tenants or task types.
- Concurrent/repeated document processing does not create duplicate context bindings or anchors.
- Production startup rejects insecure JWT configuration.
- Upload validation rejects obvious extension/content mismatches for supported Office/PDF formats.
- AI workflows have deterministic quality evaluators for evidence grounding and citation integrity.
- Live integration smoke supports polling OpenViking asynchronous ingestion and a real structured LLM call.
- Failure/retry paths preserve evidence data and do not silently mark partial AI output successful.
- CI includes hardening, concurrency, security and eval tests.
