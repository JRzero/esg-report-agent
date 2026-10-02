# Fact Center & Evidence Trace Acceptance Report

Date: 2026-10-02  
Scope: Evidence → Fact human-control loop, revision history and conflict resolution.

## Result

**Spec 012 Acceptance: PASS**

Validation runs:

- Web CI: **36959124022 — PASS**
- Service CI: **36959124032 — PASS**

Observed Web results:

- locked dependency install: PASS
- Astryx Button/FileInput/Selector/TextArea/SegmentedControl contracts: PASS
- ESLint: PASS
- TypeScript: PASS
- Vitest: **5 files / 14 tests passed**
- Next.js 16.3.8 production build: PASS
- unauthenticated SSR smoke: PASS

Observed Service regression results:

- Ruff/compile/migrations: PASS
- pytest: **39 passed**
- Agent Eval: **1.0**
- ESG Scenario Eval aggregate calibration: **1.0**
- performance smoke p50: **7.65 ms**
- performance smoke p95: **42.61 ms**
- service image build/non-root verification: PASS

The performance figures are CI regression guards, not production capacity claims.

## Service contract changes

### Fact detail

Added:

```text
GET /api/v1/facts/{factId}
```

The endpoint enforces project membership/VIEW_FACT before returning the Fact.

### Complete Evidence Trace

Expanded:

```text
GET /api/v1/facts/{factId}/evidence
```

The response now includes:

- FactEvidence ID
- evidence role
- evidence confidence
- complete DocumentAnchor locator fields
- raw/normalized text
- Anchor content hash
- Document identity/source type/category
- immutable DocumentVersion identity/version number
- original filename
- DocumentVersion SHA-256

This closes the trace:

```text
Fact
  ↓
FactEvidence
  ↓
DocumentAnchor
  ↓
DocumentVersion
  ↓
Original source file
```

### Fact Revision history

Added:

```text
GET /api/v1/facts/{factId}/revisions
```

Revision history is returned newest-first and is read-only.

The accepted lifecycle includes append-only revisions such as:

```text
AI_CREATED / HUMAN_CREATED
HUMAN_EDIT
CONFIRMED
REJECTED
```

### Conflict detail

Added:

```text
GET /api/v1/fact-conflicts/{groupId}
```

It returns the authoritative conflict group plus its member Facts. The browser no longer reconstructs conflict membership from semantic keys.

## Conflict hardening

A Service-level bypass was found and fixed during this spec.

Previously a Fact already marked `CONFLICT` could still be passed directly to the ordinary confirm endpoint.

The Service now rejects direct Confirm **and** Reject for CONFLICT Facts with:

```text
FACT_CONFLICT_UNRESOLVED
```

Conflicting Facts must use:

```text
POST /api/v1/fact-conflicts/{groupId}/resolve?fact_id={selectedFactId}
```

The Service verifies the selected Fact is a member of that conflict group.

On resolution:

```text
selected member → CONFIRMED
other members   → REJECTED
group           → RESOLVED
```

No AI or UI heuristic selects a winner automatically.

## Fact Center

Implemented:

```text
/projects/{projectId}/facts
```

The page displays:

- total Fact count
- PENDING count
- CONFIRMED count
- CONFLICT count
- REJECTED count
- status filter
- search
- typed Fact value
- unit
- period
- entity scope
- source type
- confidence
- semantic key

## Fact detail

Implemented:

```text
/projects/{projectId}/facts/{factId}
```

The page shows:

- status
- source
- typed value
- unit
- reporting period
- entity scope
- confidence
- semantic key
- Evidence Trace
- Revision History
- human decision/edit controls according to Fact state

## Human-control UI rules

### PENDING

Allowed:

- edit
- confirm
- reject

### CONFLICT

Allowed:

- candidate value/unit correction
- explicit conflict-group resolution

Not allowed:

- direct confirm
- direct reject
- changing semantic-key fields from the conflict candidate editor

### CONFIRMED

Ordinary PATCH editing is unavailable.

This matches the Service rule that confirmed facts are immutable through the normal update path.

### REJECTED

The Fact remains visible for audit but ordinary editing/confirmation actions are not offered.

## Typed Fact editing

The frontend supports the existing Service Fact value types:

- NUMBER
- TEXT
- BOOLEAN
- DATE
- JSON

The editor normalizes/validates each type before PATCH.

For PENDING Facts it may update:

- name
- value
- unit
- period
- entity scope

For CONFLICT candidates it may update only:

- value
- unit

This prevents the UI from mutating the semantic-key identity while a conflict group is open.

## Evidence deep link

Fact Evidence now links directly back to the exact Material source:

```text
/projects/{projectId}/materials/{documentId}
  ?version={documentVersionId}
  &anchor={documentAnchorId}
```

The Material Evidence Viewer:

- selects the requested immutable DocumentVersion
- moves the requested Anchor to the top
- marks it as the current Fact evidence

This supports one-step review from a Fact back to:

```text
Excel → Sheet + Cell/Range
PDF   → Page/Page Range
Word  → Heading/Paragraph
PPT   → Slide
```

## Conflict Center

The Fact Center contains a dedicated conflict section.

For each group it shows the Service-authoritative member Facts and allows a human to choose one candidate.

The UI explicitly states that resolution is a human decision and does not rank or recommend a value.

## Automated tests

New frontend tests cover:

- direct decision allowed only for PENDING
- editability rules
- numeric normalization
- conflict edit boundary
- typed Fact value rendering

New Service tests cover:

- complete Excel Evidence Trace
- immutable DocumentVersion metadata in trace
- Fact Revision sequence
- Conflict Group member detail
- direct conflict Confirm rejection
- direct conflict Reject rejection
- explicit conflict resolution
- winner CONFIRMED / others REJECTED

## Conclusion

The core business boundary is now operational in the product:

```text
Evidence
   ↓
Fact Candidate
   ↓
Human Review
   ↓
Confirmed Fact
   ↓
Report-ready business truth
```

and conflicts cannot silently cross that boundary.

The next vertical slice can build GRI/Disclosure mapping on top of the now-visible and human-controlled Fact Center.
