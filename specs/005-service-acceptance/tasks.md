# Tasks

- [x] Harden schemas and validation
- [x] Complete Company/Project/Project Member lifecycle
- [x] Complete Document/DocumentVersion lifecycle
- [x] Complete Fact lifecycle and evidence guards
- [x] Complete Missing Item lifecycle
- [x] Complete template/report/section/block lifecycle
- [x] Add claim verification
- [x] Add task list/retry/cancel
- [x] Add audit query endpoint
- [x] Add dependency readiness checks
- [x] Add PostgreSQL integration fixtures
- [x] Add RBAC/tenant isolation tests
- [x] Add Evidence-to-Fact E2E
- [x] Add GRI coverage/missing-data E2E
- [x] Add Report/Claim/Citation/DOCX E2E
- [x] Add OpenViking adapter contract test
- [x] Add LLM adapter contract test
- [x] Add acceptance CI workflow
- [x] Add optional live OpenViking/LLM smoke runner
- [x] Publish acceptance report

## External live verification

The live smoke runner is implemented but deliberately excluded from normal CI because it requires
deployment-specific OpenViking/LLM endpoints and credentials. It is executed explicitly in the target
environment with:

```bash
RUN_LIVE_INTEGRATIONS=true uv run python scripts/live_integrations.py
```

A CI pass proves the deterministic service contract and PostgreSQL-backed business workflow; it does
not claim that a third-party deployment endpoint was reachable at that moment.
