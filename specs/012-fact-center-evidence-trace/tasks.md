# Tasks

- [x] Expand Service Fact Evidence trace
- [x] Add Fact Revision endpoint
- [x] Add Service regression tests
- [x] Add Fact BFF routes
- [x] Add Fact frontend types
- [x] Add Fact queries/mutations
- [x] Add Fact Center
- [x] Add Fact status filtering
- [x] Add Fact detail
- [x] Add Fact editing
- [x] Add confirm/reject
- [x] Add Evidence Trace
- [x] Add Revision timeline
- [x] Add Conflict Center
- [x] Add human conflict resolution
- [x] Add frontend tests
- [x] Run Web CI
- [x] Run Service CI
- [x] Publish acceptance report

## Accepted Fact lifecycle

```text
AI / Human Candidate
      ↓
   PENDING
      ↓
 Human Review
 ┌────┴─────┐
Confirm   Reject
  ↓          ↓
CONFIRMED  REJECTED
```

Conflict lifecycle:

```text
same semantic_key + different value
            ↓
         CONFLICT
            ↓
Conflict Group Resolution
            ↓
selected = CONFIRMED
others   = REJECTED
```

Direct Confirm/Reject on a CONFLICT Fact is rejected by the Service.
