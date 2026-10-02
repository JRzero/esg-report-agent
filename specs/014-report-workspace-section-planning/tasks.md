# Tasks

- [x] Extend SectionPlan schema
- [x] Add planning-context builder
- [x] Add Section detail endpoint
- [x] Add Section Disclosure list/remove endpoints
- [x] Enforce Project Disclosure mapping boundary
- [x] Invalidate plan when disclosure mappings change
- [x] Add Writing Plan update/confirm endpoint
- [x] Require confirmed plan for writing
- [x] Add Service regression tests
- [x] Add Report/Section BFF routes
- [x] Add frontend Report/Section contracts
- [x] Add Report list/create UI
- [x] Add Report Workspace
- [x] Add Section Tree/create/edit
- [x] Add Disclosure Mapping UI
- [x] Add Planning Context UI
- [x] Add AI Planning task UI
- [x] Add Writing Plan editor/confirm UI
- [x] Add frontend tests
- [x] Run Web CI
- [x] Run Service CI
- [x] Publish acceptance report

## Accepted planning lifecycle

```text
Section
  ↓
Disclosure Mapping
  ↓
Scoped Planning Context
  ↓
AI Writing Plan
  ↓
DRAFT
  ↓
Human Edit / Confirm
  ↓
CONFIRMED
```

Section Writing is blocked unless the current plan is CONFIRMED.

Changing Section context or Disclosure mappings invalidates the plan.
