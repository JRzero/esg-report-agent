# Report Workspace & Section Planning Acceptance Report

Date: 2026-10-02  
Scope: Report structure, Section-scoped context, AI planning and human plan confirmation.

## Result

**Spec 014 Acceptance: PASS**

Validation runs:

- Web CI: **36970181313 — PASS**
- Service CI: **36970181343 — PASS**

Observed Web results:

- locked dependency install: PASS
- Astryx component contracts: PASS
- ESLint: PASS
- TypeScript: PASS
- Vitest: **7 files / 20 tests passed**
- Next.js 16.3.8 production build: PASS
- unauthenticated SSR smoke: PASS

Observed Service results:

- Ruff/compile/migrations: PASS
- pytest: **41 passed**
- Agent Eval: **1.0**
- ESG Scenario Eval aggregate calibration: **1.0**
- performance smoke p50: **14.8 ms**
- performance smoke p95: **76.28 ms**
- service image build/non-root verification: PASS

The performance figures are CI regression guards, not production capacity claims.

## Report Workspace

Implemented:

```text
/projects/{projectId}/reports
/projects/{projectId}/reports/{reportId}
```

The workspace now supports real Service-backed:

- Report list
- Report creation
- Section list/tree
- Section creation
- Section title/description editing
- Section status
- Section-to-Disclosure mapping
- AI Writing Plan task submission
- Human Writing Plan editing
- Explicit Writing Plan confirmation
- Scoped Planning Context inspection

The UI deliberately does not implement the final rich-text report editor in this spec.

## Section Disclosure boundary

A Section may only map a Disclosure already attached to the same Project.

Service now rejects invalid mapping with:

```text
DISCLOSURE_NOT_ATTACHED_TO_PROJECT
```

The browser cannot bypass this by supplying a global Disclosure ID.

Section Disclosure mappings can be listed and explicitly removed.

Adding/removing a mapping invalidates the current Writing Plan.

## Scoped Planning Context

Added:

```text
GET /api/v1/sections/{sectionId}/planning-context
```

When the Section has mapped Disclosures, the context is restricted to:

```text
Mapped Disclosure
   ↓
Applicable Requirements
   ↓
DisclosureFactMap
   ↓
current CONFIRMED Facts
   ↓
FactEvidence
   ↓
DocumentAnchor
```

Related active Missing Items are included as warning/follow-up context.

The context response includes:

- Section identity
- mapped Disclosures
- Requirements
- scoped CONFIRMED Facts
- exact Evidence Anchors
- active Missing Items
- context warnings

Requirements marked NOT_APPLICABLE are excluded from planning obligations.

If a Section has no mapped Disclosure, the Service may expose all Project CONFIRMED Facts but adds an explicit unbound-section warning.

## Structured SectionPlan

The plan schema now includes explicit resource references:

- disclosure_ids
- requirement_ids
- fact_ids
- evidence_anchor_ids
- missing_item_ids

plus:

- goal
- recommended_structure
- key_messages
- missing_items
- warnings

The Service validates every resource ID against the current Section Planning Context.

Out-of-context resources fail closed with:

```text
WRITING_PLAN_CONTEXT_STALE
```

## AI Planning

Existing command:

```text
POST /api/v1/sections/{sectionId}/ai/writing-plan
```

now executes using the scoped context rather than every Project Fact.

The planning prompt includes only the resources allowed for the selected Section.

The AI plan is always persisted as:

```text
source = AI
status = DRAFT
```

The AI cannot self-confirm a Writing Plan.

## Human Plan confirmation

Added:

```text
PUT /api/v1/sections/{sectionId}/writing-plan
```

A consultant can:

- revise goal
- revise structure
- revise key messages
- include/remove scoped Disclosures
- include/remove scoped Requirements
- include/remove Confirmed Facts
- include/remove Evidence Anchors
- include/remove Missing Items
- add warnings/missing notes
- save DRAFT
- explicitly set CONFIRMED

Human edits are revalidated by the Service against current context IDs before persistence.

## Plan invalidation

A previous plan is cleared when its material context changes:

- Section title changes
- Section description changes
- Section hierarchy changes
- Section Disclosure is added
- Section Disclosure is removed

Saving unchanged Section metadata does not invalidate the plan.

## Section Writing gate

Section Writing now requires:

```text
writing_plan.status == CONFIRMED
```

Otherwise it fails with:

```text
WRITING_PLAN_NOT_CONFIRMED
```

Formal writing is additionally constrained to the plan's selected `fact_ids`.

The runtime no longer reloads all Project Facts after plan confirmation.

If a selected Fact is later rejected/deleted/unavailable, writing fails with:

```text
WRITING_PLAN_CONTEXT_STALE
```

and requires replanning.

## Async planning lifecycle

Submitting Section Planning marks the Section:

```text
GENERATING
```

Successful planning returns the Section to:

```text
DRAFT
```

Planning task responses now expose target metadata so the UI can identify which Section is being processed.

Failure/cancellation recovery resets the Section to:

- DRAFT when an older plan exists
- NOT_STARTED when no plan exists

Retry returns the Section to GENERATING.

## Three-column workspace

The Report Workspace is organized as:

```text
┌────────────────┬────────────────────────────┬────────────────────┐
│ Section Tree   │ Section / Writing Plan     │ Planning Context   │
│                │                            │                    │
│ hierarchy      │ metadata                   │ requirements       │
│ state          │ disclosure mapping         │ confirmed facts    │
│ add section    │ AI plan                    │ evidence anchors   │
│                │ human confirm              │ missing warnings   │
└────────────────┴────────────────────────────┴────────────────────┘
```

This establishes the future Report Editor shell without prematurely introducing Tiptap.

## Regression coverage

Service acceptance tests verify:

1. unattached Disclosure cannot be mapped to Section
2. attached Disclosure can be mapped
3. mapped planning context excludes unrelated Confirmed Facts
4. Fact Evidence Anchor enters planning context
5. active Missing Item enters planning context
6. out-of-scope manual Fact ID is rejected
7. out-of-scope AI plan Fact ID is rejected
8. AI plan persists as DRAFT
9. DRAFT plan cannot enter Section Writing
10. human confirmation changes plan to CONFIRMED
11. removing Disclosure mapping clears the plan

Existing uncited-claim Agent Eval was adapted to a confirmed plan so it continues validating its original fail-closed condition.

## Conclusion

The report pipeline now has a controlled pre-writing boundary:

```text
Evidence
  ↓
Confirmed Fact
  ↓
GRI Requirement
  ↓
Report Section
  ↓
Scoped Context
  ↓
AI Plan
  ↓
Human-confirmed Plan
```

The next vertical slice can safely implement Section Writing, Block editing, Claims and Citations without allowing the model to bypass Evidence/Fact/GRI controls.
