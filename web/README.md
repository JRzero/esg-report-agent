# ESG Report Agent Web

Next.js frontend foundation for the evidence-grounded ESG report workspace.

## Stack

- Next.js 16.3.8
- React 19
- TypeScript
- Astryx 0.6.3
- Tailwind CSS 4.3
- TanStack Query
- Zustand

Astryx is the primary design system. Tailwind is used for layout and domain composition rather than rebuilding primitive controls.

## Run

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000.

The root page is currently a **Foundation Showcase**, not a product feature page. It verifies the persistent shell and the first ESG domain components before route development begins.

## Quality gates

```bash
npm run lint
npm run typecheck
npm run test
npm run build
npm run astryx -- component Button --json
```

## Astryx

All stable Astryx packages are pinned to the same exact version.

Use the locally installed CLI:

```bash
npm run astryx -- search evidence
npm run astryx -- component Button
npm run astryx -- component Card
npm run astryx -- template --list
```

Do not use an unrelated bare `npx astryx` before `@astryxdesign/cli` is installed.

## Domain components

- EvidenceCard
- FactCard
- GRICoverage
- MissingItemCard
- CitationMarker
- AIAction

These components are the first layer of the project's ESG-specific design system.

## Backend

Set:

```text
NEXT_PUBLIC_SERVICE_BASE_URL=http://localhost:8000
```

The current foundation exposes an API client abstraction but does not yet implement the product login route or feature pages.


## Authentication & Project Workspace

The browser does not persist FastAPI access or refresh tokens.

```text
Browser
  ↓ same-origin /api/*
Next.js BFF
  ↓ Authorization: Bearer ...
FastAPI Service
```

The BFF stores access/refresh tokens in HttpOnly, SameSite=Lax cookies and refreshes the access token through the Service when needed.

Current implemented routes:

```text
/login
/projects
/projects/new
/projects/[projectId]
/projects/[projectId]/materials
/projects/[projectId]/facts
/projects/[projectId]/reports
/projects/[projectId]/gri
/projects/[projectId]/missing
/projects/[projectId]/members
```

Only the project Overview is functional in Spec 010. Other project routes are explicit placeholders for later feature specs.

Local seed login:

```text
admin@example.com
admin123
```


## Material Center

Implemented project routes:

```text
/projects/{projectId}/materials
/projects/{projectId}/materials/{documentId}
```

The Material Center uses the real Service document contracts for upload, immutable versions, parsing status,
DocumentAnchor inspection, reprocessing, original-file download and Fact Extraction task submission.

The browser does not independently parse PDF/Excel/Word/PPT into authoritative evidence coordinates.
The Service `DocumentAnchor` remains the provenance source of truth.


## Fact Center

Implemented:

```text
/projects/{projectId}/facts
/projects/{projectId}/facts/{factId}
```

The Fact Center consumes real Service Fact, Evidence, Revision and Conflict contracts.

Decision rules:

- PENDING → edit / confirm / reject
- CONFLICT → explicit Conflict Center resolution only
- CONFIRMED → immutable ordinary edit
- REJECTED → retained for audit

Evidence links deep-link back to the exact Material DocumentVersion and DocumentAnchor.


## GRI & Missing Data

Implemented:

```text
/projects/{projectId}/gri
/projects/{projectId}/gri/{projectDisclosureId}
/projects/{projectId}/missing
```

GRI coverage is requirement-level and is recomputed from CONFIRMED Facts. Project users can explicitly
set Disclosure applicability. Missing Items track evidence/data follow-up separately from coverage.
