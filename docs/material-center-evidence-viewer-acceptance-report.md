# Material Center & Evidence Viewer Acceptance Report

Date: 2026-10-02  
Scope: Project Materials vertical slice and evidence-coordinate inspection.

## Result

**Spec 011 Acceptance: PASS**

Validation runs:

- Web CI: **36944699546 — PASS**
- Service CI: **36944699548 — PASS**

Observed Web results:

- locked dependency install: PASS
- Astryx Button contract: PASS
- Astryx FileInput contract: PASS
- Astryx Selector contract: PASS
- ESLint: PASS
- TypeScript: PASS
- Vitest: **4 files / 9 tests passed**
- Next.js 16.3.8 production build: PASS
- unauthenticated SSR smoke: PASS

Observed Service regression results:

- Ruff/compile/migrations: PASS
- pytest: **37 passed**
- Agent Eval: **1.0**
- ESG Scenario Eval: **1.0**
- performance smoke p50: **13.64 ms**
- performance smoke p95: **69.86 ms**
- service image build/non-root verification: PASS

The performance figures are CI regression guards, not production capacity claims.

## Material Center

Implemented:

```text
/projects/{projectId}/materials
```

The page consumes real Service contracts for:

- project document list
- document upload

Supported upload formats match the Service:

- PDF
- DOCX
- XLSX
- XLSM
- PPTX
- TXT
- MD
- CSV

The upload UI enforces the configured 50 MB client-side limit and requires an explicit source role.

## Source roles

The frontend carries the same source semantics as the backend:

### EVIDENCE
Current-project enterprise source material. May substantiate Facts.

### REFERENCE
Industry examples and writing/structure references. Must not substantiate current-enterprise Facts.

### STANDARD
Reporting rules and disclosure requirements. Not enterprise facts.

### HISTORICAL
Prior-period context. May produce candidates only with period awareness and subsequent confirmation.

Reference and Standard documents do not expose a Fact Extraction action in the Evidence Viewer.

## Document Evidence Viewer

Implemented:

```text
/projects/{projectId}/materials/{documentId}
```

The detail page shows:

- source role
- immutable DocumentVersion list
- validation status
- evidence-parse status
- OpenViking/context status
- classification status
- file extension
- file size
- SHA-256 prefix
- upload time
- parser error when present

Version processing state is polled only while a version remains PENDING/PROCESSING.

## Immutable versions

A new upload to an existing document creates a new Service `DocumentVersion`.

The UI does not present version upload as an in-place file replacement.

Users can switch between versions and inspect each version's evidence coordinates independently.

## Evidence Anchor Viewer

The browser deliberately does **not** create a second authoritative parser.

The viewer consumes:

```text
GET /api/v1/document-versions/{versionId}/anchors
```

and treats Service `DocumentAnchor` as the evidence-coordinate source of truth.

Locator rendering supports:

- Excel: Sheet + Cell/Range
- PDF: Page / Page Range
- PPT: Slide
- Word: Heading Path / Paragraph
- fallback: Anchor type

Examples:

```text
Sheet: 员工统计 · Cell: B18
Page 23
Pages 23–24
社会 › 员工发展
Slide 8
```

Anchors display their original `raw_text` and can be searched locally.

The UI currently renders up to 200 matching anchors to avoid accidental unbounded DOM growth.

## Original file actions

For a selected version the viewer supports:

- original-file download via the Service signed-download contract
- reprocess
- upload new immutable version

The default local application environment uses MinIO, so signed download URLs are browser-reachable.

## Fact Extraction

For eligible sources the viewer invokes:

```text
POST /api/v1/document-versions/{versionId}/extract-facts
```

with an idempotency key scoped to the version.

UI eligibility requires:

```text
source ∈ {EVIDENCE, HISTORICAL}
AND
evidence_parse_status == READY
```

REFERENCE and STANDARD are blocked before the request is offered to the user.

## AI task visibility

The Material workspace consumes:

```text
GET /api/v1/projects/{projectId}/tasks
```

and displays recent FACT_EXTRACTION task state:

- PENDING
- RUNNING
- SUCCESS
- FAILED
- CANCELLED
- stage
- progress
- error message

Task polling runs every two seconds only while at least one project task remains PENDING or RUNNING.

## BFF routes

Next.js same-origin BFF proxies were added for:

```text
GET/POST /api/projects/{projectId}/documents
GET      /api/documents/{documentId}
POST     /api/documents/{documentId}/versions
GET      /api/document-versions/{versionId}
GET      /api/document-versions/{versionId}/anchors
POST     /api/document-versions/{versionId}/reprocess
GET      /api/document-versions/{versionId}/download
POST     /api/document-versions/{versionId}/extract-facts
GET      /api/projects/{projectId}/tasks
```

FastAPI tokens remain confined to the HttpOnly BFF session established in Spec 010.

## Automated boundary tests

New tests verify:

- EVIDENCE may expose Fact Extraction
- HISTORICAL may expose candidate extraction
- REFERENCE never exposes Fact Extraction
- STANDARD never exposes Fact Extraction
- Excel locator formatting
- PDF locator formatting
- Word heading locator formatting
- PPT slide locator formatting

These run together with the existing Evidence-vs-Reference domain-component regression tests.

## Intentional exclusions

This spec does not yet implement:

- full rendered PDF page canvas
- spreadsheet grid recreation
- bounding-box highlight overlays
- OCR image-region viewer
- inline Fact confirmation
- bulk material operations
- document deletion
- category correction UI
- Fact Center

Those features are not required to preserve provenance because the current viewer already exposes the
authoritative Service Anchor coordinates.

## Conclusion

The product now has its first evidence-driven workflow:

```text
Authenticated User
  ↓
Project
  ↓
Material
  ↓
Immutable File Version
  ↓
Parser Anchor
  ↓
Evidence Viewer
  ↓
Fact Extraction Task
```

The next vertical slice can implement Fact Center on top of actual extracted Facts and their existing
FactEvidence → DocumentAnchor provenance links.
