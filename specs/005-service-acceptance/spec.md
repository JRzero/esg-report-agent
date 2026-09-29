# Service Acceptance & Hardening

## Intent
Complete and verify the entire service-side MVP without a frontend. The service must expose a coherent API for foundation, evidence/fact, GRI intelligence, report authoring, asynchronous tasks, auditability and exports, while enforcing tenant/project/evidence boundaries.

## Acceptance criteria

### Foundation
- Login, refresh, current user and logout contract
- Tenant member list/create/update/deactivate
- Company create/list/get/update/soft-delete
- Project create/list/get/update/archive/soft-delete
- Project member list/add/change-role/remove and owner transfer
- Project RBAC and client-company membership boundary
- Audit log query
- PostgreSQL tenant RLS policies on tenant-bound business tables
- Real readiness checks for PostgreSQL, Redis and object storage

### Documents & Evidence
- Project document list/upload/detail/soft-delete
- Immutable document versions and version upload
- Download through object storage signed URL
- XLSX, DOCX, PDF, PPTX and text parsing
- Parse/reprocess and OpenViking reindex task APIs
- Context binding status
- EVIDENCE / REFERENCE / STANDARD / HISTORICAL source type validation
- REFERENCE and STANDARD documents can never become Fact evidence
- Evidence trace resolves document, version and immutable anchor

### Facts
- List/get/create/update/reject/confirm
- Fact revisions on meaningful mutations
- Add/remove evidence with project/source validation
- Conflict detection/list/detail/resolve
- Confirmed AI facts require evidence

### Standards / GRI
- Standard/version/disclosure/requirement read APIs
- Project-standard attach
- Requirement-level coverage
- Confirmed Fact to Disclosure mapping
- Missing-data analysis and missing-item status updates
- GRI coverage check task/result

### Reports
- Template list/create/version/section APIs
- Report list/create/get/update
- Section CRUD/reorder and disclosure mapping
- Block CRUD with immutable revisions and restore
- Writing-plan task
- Evidence-grounded section-writing task
- Claim/citation list and trace
- Claim verification
- Report consistency check
- DOCX asynchronous export and download

### Collaboration / Operations
- Section/block comments, replies and resolve
- AI task project list/get/cancel/retry
- AI trace read API
- Structured audit history

### Acceptance automation
- PostgreSQL migration from empty database
- API integration tests against PostgreSQL
- Tenant/project isolation tests
- PostgreSQL RLS test using a non-owner application role
- Document -> Anchor -> Fact -> Evidence E2E
- Reference-is-not-evidence E2E
- Fact conflict E2E
- GRI mapping/missing E2E
- Report -> Block Revision -> Claim -> Citation -> DOCX E2E
- OpenViking HTTP contract test
- LLM structured-output contract test
- MinIO object storage integration test
- GitHub Service CI is green
