# Plan

## P0 correctness
- Fix idempotency scope and concurrency.
- Atomically claim AI/document jobs.
- Fix cancellation visibility.
- Reconcile OpenViking background tasks.

## P0 security/reliability
- Stream uploads with hard size limits.
- Bound parser work.
- Validate production secrets/config.
- Add security response headers.
- Run container as non-root.

## P1 resilience
- Retry transient LLM failures.
- Add OpenViking readiness/task normalization.
- Namespace OpenViking data by tenant/project.
- Add stale RUNNING task recovery.

## Verification
- Migration upgrade test.
- Concurrent idempotency test.
- Duplicate-delivery test.
- Cancellation/failure injection tests.
- OpenViking reconciliation contract tests.
- LLM retry contract tests.
- Upload/parser limit tests.
- Security configuration/header tests.
- Lightweight performance smoke.
- GitHub CI acceptance report.
