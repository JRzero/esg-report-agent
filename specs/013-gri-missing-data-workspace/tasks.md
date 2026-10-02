# Tasks

- [x] Add project Standards read endpoint
- [x] Add Disclosure detail read endpoint
- [x] Enrich project Disclosure/Requirement read models
- [x] Add Disclosure applicability update
- [x] Add RESOLVED Missing Item state
- [x] Add Service regression tests
- [x] Add GRI BFF routes
- [x] Add GRI frontend types/query hooks
- [x] Add Standard attach UI
- [x] Add GRI coverage dashboard
- [x] Add Disclosure detail
- [x] Add mapped Fact display
- [x] Add Fact Mapping action
- [x] Add Missing Data Analysis action
- [x] Add Missing Data workspace
- [x] Add Missing Item workflow
- [x] Add frontend tests
- [x] Run Web CI
- [x] Run Service CI
- [x] Publish acceptance report

## Accepted coverage flow

```text
Confirmed Fact
      ↓
RULE Fact Mapping
      ↓
Requirement Status
  ├─ COVERED
  ├─ MISSING
  └─ NOT_APPLICABLE
      ↓
Disclosure Coverage
  ├─ COVERED
  ├─ PARTIAL
  └─ MISSING
```

Missing Item operational workflow remains separate:

```text
MISSING → REQUESTED → RECEIVED → RESOLVED
```

RECEIVED / RESOLVED does not itself make a Requirement COVERED.
