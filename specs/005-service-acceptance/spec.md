# Service Completion & Acceptance

## Intent
Complete and harden the backend before any frontend work. The service must support the full ESG production lifecycle and prove it with automated acceptance tests against real PostgreSQL plus contract fakes for external AI/context providers.

## Scope
- Foundation CRUD completeness: company/project/member lifecycle, owner transfer, audit access
- Document lifecycle: versions, download, reprocess, PDF/DOCX/XLSX/PPTX/TXT parsing
- Evidence → Fact: extraction task, evidence trace, revisions, reject/edit/confirm, conflict resolution
- Standards: attach GRI version, disclosure/requirement coverage, mapping, missing-item lifecycle
- Report: templates, sections, blocks/revisions, comments, claims/citations, consistency and GRI checks
- Async task lifecycle: enqueue, retry, cancel, status, idempotency
- DOCX export via export worker
- Health/readiness/dependency status
- Tenant/project isolation and PostgreSQL RLS baseline
- OpenViking and LLM adapter contract tests
- End-to-end service acceptance test

## Acceptance criteria
1. alembic upgrade head succeeds on PostgreSQL 16.
2. Core API tests run with real PostgreSQL.
3. Tenant A cannot enumerate or access Tenant B resources.
4. Project role matrix is enforced.
5. XLSX/PDF/DOCX/PPTX/TXT are parsed into immutable anchors.
6. Evidence-backed Fact can be confirmed; AI Fact without evidence cannot.
7. Conflicts are detected and resolved deterministically.
8. Project standard creates requirement coverage rows.
9. Confirmed Facts can satisfy metric-backed requirements.
10. Missing items can be generated and lifecycle-managed.
11. Report templates create section trees.
12. AI plan/writing workflows only consume confirmed Facts and create Claim/Citation links.
13. High-risk unsupported claims are surfaced by consistency checking.
14. Report can export DOCX asynchronously and produce a downloadable object.
15. AI/context dependency failures do not break business CRUD.
16. Task retry/cancel are implemented.
17. /health, /ready, /internal/dependencies are implemented.
18. CI executes migration + integration + API + E2E tests.