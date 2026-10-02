# GRI Disclosure & Missing Data Workspace Acceptance Report

Date: 2026-10-02  
Scope: Standards, requirement-level coverage, Fact Mapping, applicability and missing-data workflow.

## Result

**Spec 013 Acceptance: PASS**

Validation runs:

- Web CI: **36965185391 — PASS**
- Service CI: **36965185509 — PASS**

Observed Web results:

- locked dependency install: PASS
- Astryx component contracts: PASS
- ESLint: PASS
- TypeScript: PASS
- Vitest: **6 files / 17 tests passed**
- Next.js 16.3.8 production build: PASS
- unauthenticated SSR smoke: PASS

Observed Service regression results:

- Ruff/compile/migrations: PASS
- pytest: **40 passed**
- Agent Eval: **1.0**
- ESG Scenario Eval aggregate calibration: **1.0**
- performance smoke p50: **14.09 ms**
- performance smoke p95: **74.39 ms**
- service image build/non-root verification: PASS

The performance figures are CI regression guards, not production capacity claims.

## Project Standards

Added:

```text
GET /api/v1/projects/{projectId}/standards
```

The response includes:

- ProjectStandard identity
- primary flag
- Standard code/name/publisher
- StandardVersion code/name/effective date/status

The Web workspace can now attach the seeded GRI 2021 version through the existing Service command:

```text
POST /api/v1/projects/{projectId}/standards/{versionId}
```

Attaching a Standard creates the project's Disclosure and Requirement status records.

## Project Disclosure read model

The project Disclosure list now exposes:

- project-disclosure ID
- source Disclosure ID
- code/title/description/topic
- applicability
- coverage status
- notes

Added detail endpoint:

```text
GET /api/v1/projects/{projectId}/disclosures/{projectDisclosureId}
```

It returns one authoritative view containing:

```text
ProjectDisclosure
  ├─ Requirements + project status
  └─ mapped CONFIRMED Facts
```

Mapped Fact rows include mapping type/source/confidence plus the Fact itself, allowing the Web UI to deep-link to Fact Center.

## Requirement read model

```text
GET /api/v1/projects/{projectId}/requirements
```

now includes relationship context:

- Disclosure ID
- Disclosure code/title
- Requirement type
- content/guidance
- required_data_json
- project status/reason

The Web application no longer reconstructs Requirement → Disclosure relationships heuristically.

## Deterministic Fact Mapping hardening

The existing command remains:

```text
POST /api/v1/projects/{projectId}/ai/disclosure-mapping
```

Despite the historical route name, the MVP implementation is deterministic rule-based mapping from confirmed Facts to required metric codes.

This spec hardens the mapping behavior:

1. RULE mappings for the project are rebuilt on each run.
2. Only Facts currently in `CONFIRMED` status participate.
3. A previously mapped Fact that later becomes REJECTED no longer remains as stale disclosure evidence.
4. Requirement status is recalculated after every run.
5. Disclosure coverage is recalculated from requirement results.

Accepted coverage example:

```text
Requirement a → matched confirmed Fact → COVERED
Requirement b → no confirmed Fact      → MISSING
Disclosure                             → PARTIAL
```

## Applicability

Added:

```text
PATCH /api/v1/projects/{projectId}/disclosures/{projectDisclosureId}
```

Supported human decisions:

- UNDETERMINED
- APPLICABLE
- NOT_APPLICABLE

NOT_APPLICABLE is explicitly a project-user decision. The system does not infer it automatically.

When a Disclosure is set NOT_APPLICABLE:

- its project Requirement statuses become NOT_APPLICABLE
- RULE Fact Mappings for that Disclosure are removed
- existing raw Facts remain unchanged
- the UI renders applicability as the effective display state

When it returns to APPLICABLE/UNDETERMINED:

- deterministic Fact Mapping is recomputed from current confirmed Facts
- Requirement coverage is restored from business truth, not from previous UI state

## GRI Workspace

Implemented:

```text
/projects/{projectId}/gri
```

The page includes:

- Standard catalog/version selector
- attached project Standards
- Fact Mapping action
- Disclosure totals
- COVERED count
- PARTIAL count
- MISSING count
- NOT_APPLICABLE count
- requirement counts per Disclosure
- Disclosure navigation

The dashboard intentionally treats applicability separately from coverage.

## Disclosure Detail

Implemented:

```text
/projects/{projectId}/gri/{projectDisclosureId}
```

The page displays:

- Disclosure metadata
- effective status
- Requirement list
- Requirement type/content/guidance
- required metric codes
- coverage reason
- mapped Confirmed Facts
- Fact links
- project applicability controls
- notes

A mapped Fact can be opened directly in Fact Center for full Evidence Trace review.

## Missing Data Analysis

The existing Service command is now exposed in the workspace:

```text
POST /api/v1/projects/{projectId}/ai/missing-data-analysis
```

The MVP implementation generates Missing Items only for Requirements currently in MISSING state.

Creation remains idempotent while an active Missing Item exists in:

- MISSING
- REQUESTED
- RECEIVED

A resolved/inapplicable historical item does not block a future follow-up if the Requirement is still MISSING.

## Missing Item lifecycle

The update contract now supports:

- MISSING
- REQUESTED
- RECEIVED
- RESOLVED
- NOT_APPLICABLE

Implemented Web route:

```text
/projects/{projectId}/missing
```

Each item supports:

- workflow status
- priority
- suggested material
- Requirement/Disclosure context
- link back to the GRI Disclosure

## Critical separation

This spec preserves two different concepts:

### Requirement Coverage

Business/reporting truth:

```text
Requirement
  ↓
Confirmed Fact Mapping
  ↓
COVERED / MISSING / NOT_APPLICABLE
```

### Missing Item Workflow

Operational follow-up:

```text
Need data
  ↓
Requested from client
  ↓
Material received
  ↓
Follow-up resolved
```

Therefore:

> **RECEIVED or RESOLVED Missing Item does not mean the GRI Requirement is COVERED.**

A received document must still pass:

```text
Material
→ Evidence Anchor
→ Fact Extraction
→ Human Confirmation
→ Fact Mapping
→ Requirement COVERED
```

## Regression scenario

The new Service acceptance test verifies the complete chain:

1. Create test Standard/Version/Disclosure/Requirements.
2. Attach Standard to Project.
3. Create and confirm a metric Fact.
4. Run Fact Mapping.
5. Verify one Requirement COVERED and one MISSING.
6. Verify Disclosure PARTIAL.
7. Verify Disclosure detail mapped Fact.
8. Set Disclosure NOT_APPLICABLE.
9. Verify all Requirements NOT_APPLICABLE and RULE mappings removed.
10. Restore APPLICABLE.
11. Verify coverage is recomputed from current confirmed Facts.
12. Run Missing Data Analysis.
13. Verify Missing Item creation.
14. Progress Missing Item MISSING → REQUESTED → RECEIVED → RESOLVED.
15. Reject the previously confirmed Fact.
16. Re-run mapping.
17. Verify stale mapping is removed and Requirement returns to MISSING.

## Conclusion

The product chain has now advanced to:

```text
Evidence
  ↓
Confirmed Fact
  ↓
Disclosure Mapping
  ↓
Requirement Coverage
  ↓
Missing Data
```

The system can now explain not only what enterprise facts exist, but also which GRI requirements are covered and exactly what remains to be collected before report writing.
