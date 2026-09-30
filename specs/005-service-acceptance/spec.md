# Service Completion & Acceptance

## Intent
Complete the backend MVP without frontend dependencies and make every core workflow objectively verifiable.

## Scope
- Complete CRUD/state transitions for companies, projects, project members, documents/versions, facts, missing items, report templates, reports, sections, blocks, claims/citations and AI tasks.
- Harden tenant/project authorization and not-found behavior.
- Add task retry/cancel and recoverable document/context processing.
- Add deterministic integration/E2E tests on PostgreSQL.
- Add OpenViking and LLM adapter contract tests.
- Add acceptance CI and acceptance report.

## Acceptance criteria
1. Auth/RBAC/project membership isolation is enforced for all project resources.
2. Evidence -> Anchor -> Fact -> Confirm -> Disclosure -> Missing -> Report -> Claim/Citation -> DOCX is covered by automated tests.
3. AI-generated facts cannot be confirmed without evidence.
4. Reference documents cannot be used as factual evidence.
5. Task retry/cancel transitions are deterministic and auditable.
6. Block edits always create immutable revisions and restore creates a new revision.
7. Citation verification validates Fact/Evidence/Anchor ownership and status.
8. PostgreSQL migration from empty database succeeds.
9. Unit, API integration and service E2E tests pass in GitHub Actions.
10. External OpenViking/LLM integrations have contract tests and optional live smoke commands.
