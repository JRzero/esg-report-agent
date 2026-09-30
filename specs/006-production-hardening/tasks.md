# Tasks

- [x] Tenant-scope AITask idempotency key
- [x] Add forward Alembic migration
- [x] Make idempotent task creation concurrency-safe
- [x] Atomically claim AI jobs
- [x] Atomically claim document parse jobs
- [x] Fix cancellation race
- [x] Add stale RUNNING task recovery
- [x] Add OpenViking tenant/project URI namespace
- [x] Add OpenViking async task reconciliation
- [x] Add OpenViking ready probe
- [x] Add bounded LLM retry/backoff
- [x] Stream upload with early size enforcement
- [x] Add parser resource limits
- [x] Validate production configuration
- [x] Add security response headers
- [x] Harden Docker runtime as non-root
- [x] Freeze initial migration schema snapshot
- [x] Add forward migration-from-v1 CI gate
- [x] Add structured request telemetry
- [x] Add concurrency acceptance tests
- [x] Add failure-injection tests
- [x] Add security acceptance tests
- [x] Add performance smoke
- [x] Extend deployment/live smoke
- [x] Publish production-hardening acceptance report

## External live verification

Deterministic service hardening and HTTP adapter contracts are verified in CI.

Real OpenViking and LLM endpoints are deliberately not required by normal CI because their endpoints,
credentials, latency and availability belong to the deployment environment. The repository provides:

```bash
RUN_LIVE_INTEGRATIONS=true uv run python scripts/live_integrations.py
```

The live runner checks LLM structured output and, when OpenViking is enabled, verifies readiness,
asynchronous import completion and subsequent retrieval.

A green Service CI therefore means the backend's production-hardening contract passed; it does not
claim that an unconfigured third-party endpoint was reachable during that CI run.
