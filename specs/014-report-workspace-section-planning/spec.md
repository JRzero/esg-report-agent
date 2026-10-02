# Report Workspace & Section Planning

## Intent
Turn the verified project truth layer into a controlled report-writing workspace before any long-form generation.

## Core flow

```text
Project
  ↓
Report
  ↓
Section Tree
  ↓
Section ↔ Disclosure Mapping
  ↓
Planning Context
  ├─ Requirements
  ├─ Confirmed Facts
  ├─ Evidence Anchors
  └─ Missing Items
  ↓
AI Writing Plan (DRAFT)
  ↓
Human Edit / Confirm
  ↓
CONFIRMED Writing Plan
```

Section Writing is out of scope for this spec except for enforcing that it may only consume a CONFIRMED plan.

## Scope
- Project Report list/create
- Report detail
- Section tree/list/create/edit
- Section detail read model
- Section ↔ Project Disclosure map/list/remove
- Planning Context read model
- AI Section Planning trigger/task status
- Structured Writing Plan
- human edit and explicit plan confirmation
- Fact/Evidence/Missing Item links from plan/context
- hardening Section Writing so DRAFT plans cannot generate content

## Rules
1. A Section may only map Disclosures already attached to the same Project.
2. Planning context is project/section scoped; the model cannot choose arbitrary project IDs.
3. When a Section has mapped Disclosures, planning Facts are limited to current CONFIRMED Facts mapped to those Disclosures.
4. When a Section has no mapped Disclosure, planning may use project CONFIRMED Facts but the context must warn that the section is unbound.
5. Requirements marked NOT_APPLICABLE are excluded from planning obligations.
6. REJECTED/PENDING/CONFLICT Facts never enter formal planning Fact context.
7. Evidence is derived from FactEvidence → DocumentAnchor; Reference/Standard material cannot become enterprise evidence.
8. Missing Items are warnings/follow-up context, not Facts.
9. AI-generated Writing Plan begins DRAFT.
10. Section Writing requires an explicitly CONFIRMED Writing Plan.
11. Human plan edits must be validated against the current allowed context IDs.
12. Updating section Disclosure mappings invalidates any previously confirmed/draft Writing Plan because its context has changed.

## Acceptance criteria
- Report list/create works with real Service contracts.
- Section tree can be created and edited.
- Mapping a Disclosure not attached to the Project is rejected by Service.
- Planning Context returns mapped Disclosure/Requirement/Confirmed Fact/Evidence/Missing Item data.
- Section Planning prompt uses scoped context instead of all project facts when mappings exist.
- AI output referencing out-of-context IDs is rejected.
- Plan is saved as DRAFT and can be edited/confirmed by a human.
- Changing Disclosure mappings clears the old Writing Plan.
- Section Writing refuses DRAFT/unconfirmed plans.
- Web and Service CI remain green.
