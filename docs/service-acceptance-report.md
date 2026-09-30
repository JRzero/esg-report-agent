# ESG Report Agent Service Acceptance Report

Date: 2026-09-30  
Scope: Backend Service MVP only. Frontend is explicitly excluded.

## Result

**Deterministic Service MVP Acceptance: PASS**

GitHub Actions Service CI run **36657386979** passed all configured gates:
- dependency installation
- fatal Ruff/static checks
- Python compileall
- PostgreSQL 16 migration from an empty database
- PostgreSQL-backed pytest acceptance suite
- Redis-backed readiness verification

A later change added only the optional external live-smoke runner; final PR CI remains the release gate.

## Accepted capability matrix

| Area | Accepted capability |
|---|---|
| Authentication | JWT access/refresh, active membership validation |
| Tenant | member creation/listing, tenant isolation |
| Project security | RBAC + Project Member, cross-project/cross-tenant concealment |
| Company | create/read/update/delete guard |
| Project | create/read/update, member lifecycle, owner transfer |
| Documents | upload, versions, reprocess, download, deterministic parsing |
| Parsers | PDF, DOCX paragraphs/tables, XLSX/XLSM, PPTX, TXT/MD/CSV |
| Evidence | immutable anchors and source traceability |
| Facts | create/update/confirm/reject/revisions/conflict detection |
| Evidence policy | Reference/Standard content cannot substantiate client Facts |
| GRI | standard/version/disclosure/requirement, mapping and coverage |
| Missing data | missing-item generation and state update |
| Templates | tenant template, versions and section tree |
| Reports | reports, sections, disclosure mapping |
| Blocks | create/edit/delete, immutable revisions, restore-as-new-revision |
| AI planning | evidence/fact-grounded section plan contract |
| AI writing | confirmed-Fact-only context and mandatory factual claim citations |
| Claims | Claim/Citation persistence and verification |
| Citation trace | Claim → Fact → FactEvidence → Anchor → Document |
| Consistency | high-risk unverified claim detection |
| Tasks | idempotency, list/detail, cancel/retry, worker lifecycle |
| Export | DOCX generation and storage-backed download |
| Audit | project audit log query |
| Operations | /health, dependency-aware /ready, request IDs |
| OpenViking | optional context adapter + graceful disabled/failure behavior |
| LLM | OpenAI-compatible structured-output adapter |

## Automated acceptance scenarios

1. **RBAC and tenant isolation**
   - reviewer may view but cannot edit
   - unrelated tenant receives not-found semantics
   - active-project company deletion is blocked

2. **Reference/Evidence boundary**
   - Reference spreadsheet parses normally
   - its anchor is rejected when used as Fact evidence

3. **Full ESG production vertical slice**
   - create company/project
   - upload Evidence XLSX
   - parse exact cell anchor
   - create and confirm ESG Fact
   - trace Fact to original evidence
   - attach GRI 2021-like test standard
   - map confirmed Fact to requirement
   - identify remaining missing requirement
   - create template/report/section
   - Fake LLM creates deterministic writing plan and report claim
   - claim is verified against confirmed Fact + Evidence
   - citation traces back to XLSX cell
   - human edit creates next revision
   - restore creates another new revision
   - report exports to DOCX

4. **Task recovery**
   - Idempotency-Key returns the same task
   - task can be cancelled
   - cancelled/failed task can be retried

5. **External adapter contracts**
   - OpenAI-compatible LLM HTTP contract verified with MockTransport
   - OpenViking upload/resource/find contract verified with MockTransport

6. **Readiness**
   - PostgreSQL, Redis and storage all participate in readiness state

## Live external integration status

OpenViking and LLM **real external endpoints were not invoked by GitHub CI**, because no deployment
credentials/endpoints are stored in the repository. This is intentional.

The codebase includes:

```bash
RUN_LIVE_INTEGRATIONS=true uv run python scripts/live_integrations.py
```

This performs opt-in live smoke checks against configured LLM and OpenViking endpoints.

Therefore:

- internal service/business acceptance: **PASS**
- HTTP adapter contract acceptance: **PASS**
- live deployment-specific OpenViking/LLM connectivity: **READY TO RUN, environment-dependent**

## Intentional MVP exclusions

The following are not acceptance defects:
- frontend / Next.js UI
- approval/BPMN workflow
- professional publication-quality PDF layout
- carbon accounting
- ESG ratings/risk platform
- deep ERP/HR integrations
- OCR/vision extraction for scanned images
- complex multi-agent orchestration

## Release conclusion

The Service MVP is considered accepted when the final PR head has a green Service CI after this report.
The frontend should remain frozen until this backend contract is merged into `main`.
