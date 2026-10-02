# Fact Center & Evidence Trace

## Intent
Close the core Evidence → Fact human-control loop.

## Core flow

```text
DocumentAnchor
  ↓
Fact Candidate
  ↓
Fact Center
  ↓
Human Review
  ├─ Edit
  ├─ Confirm
  └─ Reject
  ↓
Confirmed Fact
```

Conflicting values are handled separately:

```text
same semantic_key
+ different value
  ↓
Conflict Group
  ↓
Human selects one Fact
  ↓
selected = CONFIRMED
others = REJECTED
```

The AI must never resolve this automatically.

## Scope
- Fact list with status filters/search
- Fact detail
- typed Fact value rendering
- edit pending/conflict Facts
- confirm/reject
- complete Evidence Trace
- Fact Revision history
- conflict groups
- human conflict resolution
- deep link from Fact Evidence back to Material / DocumentAnchor context
- backend Evidence Trace response expansion
- backend Fact Revision read endpoint

## Rules
1. AI-created Facts start PENDING.
2. AI Facts without Evidence cannot be confirmed.
3. CONFIRMED Facts are immutable through ordinary PATCH.
4. REFERENCE / STANDARD must never appear as Fact Evidence.
5. CONFLICT status is never resolved automatically by UI or AI.
6. Conflict resolution must explicitly choose one member Fact.
7. Evidence Trace must terminate in an immutable DocumentVersion + DocumentAnchor.
8. Fact revision history is append-only/read-only.

## Acceptance criteria
- Fact Center consumes real project Facts.
- Fact status counts and filters work for PENDING/CONFIRMED/CONFLICT/REJECTED.
- Editing uses the real FactUpdate contract.
- Confirm/reject use real commands.
- Confirmed Fact edit controls are unavailable.
- Evidence Trace exposes full locator fields and links to source Material.
- Fact revision timeline comes from Service FactRevision records.
- Conflict Center lists open/resolved groups and member candidates.
- Resolve action cannot submit a Fact outside the group's semantic_key candidate set.
- Service and Web CI remain green.
