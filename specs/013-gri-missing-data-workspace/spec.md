# GRI Disclosure & Missing Data Workspace

## Intent
Turn Confirmed Facts into requirement-level disclosure coverage and an actionable missing-data queue.

## Core flow

```text
Project
  ↓
Attach Standard Version
  ↓
Project Disclosures / Requirements
  ↓
Confirmed Fact Mapping
  ↓
Requirement Coverage
  ├─ COVERED
  ├─ PARTIAL
  ├─ MISSING
  └─ NOT_APPLICABLE
  ↓
Missing Data Analysis
  ↓
Missing Items
  ↓
REQUESTED → RECEIVED → RESOLVED
```

## Scope
- list available Standards and Versions
- list attached project Standards
- attach Standard Version
- project Disclosure coverage dashboard
- Disclosure detail with Requirements
- mapped Confirmed Facts per Disclosure
- deterministic Fact Mapping trigger
- applicability decision: APPLICABLE / NOT_APPLICABLE / UNDETERMINED
- Missing Data Analysis trigger
- Missing Item list/filter
- Missing Item status/priority/suggested-material update
- links from mapped Fact to Fact Center
- links from Missing Item to related Disclosure/Requirement

## Rules
1. Coverage is requirement-level and computed from confirmed Facts.
2. PENDING/CONFLICT/REJECTED Facts do not satisfy requirements.
3. Fact Mapping does not confirm Facts.
4. NOT_APPLICABLE is a human project decision, not an AI assumption.
5. Setting a Disclosure NOT_APPLICABLE marks its project requirement statuses NOT_APPLICABLE.
6. Returning a Disclosure to APPLICABLE/UNDETERMINED recomputes requirement coverage from confirmed Facts.
7. Missing Data Analysis creates items only for currently MISSING requirements and is idempotent for active items.
8. Missing Item RESOLVED is workflow state; it does not by itself mark the GRI Requirement COVERED.
9. Requirement COVERED requires confirmed mapped Fact(s) or an explicit future domain rule, not merely received documents.
10. AI/Reference content cannot substitute for Confirmed Fact coverage.

## Acceptance criteria
- Project can attach GRI 2021 from the seeded standard catalog.
- Attached standards are visible with version and primary flag.
- Project disclosures show COVERED/PARTIAL/MISSING counts.
- Disclosure detail returns authoritative requirements and mapped confirmed Facts.
- Applicability changes obey Service-side invariants.
- Running mapping updates coverage based only on confirmed Facts.
- Running missing analysis generates actionable Missing Items.
- Missing Item workflow supports MISSING/REQUESTED/RECEIVED/RESOLVED/NOT_APPLICABLE.
- Web and Service CI remain green.
