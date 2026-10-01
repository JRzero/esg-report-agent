# AGENTS.md

## Product invariant
Never treat model output or retrieval output as business truth. PostgreSQL-confirmed Facts are the source of truth. OpenViking is context only.

## Development workflow
1. Read the relevant `specs/<id>/spec.md` and `plan.md`.
2. Pick the next unchecked task from `tasks.md`.
3. Implement the smallest vertical slice.
4. Add or update tests.
5. Mark the task complete only after tests pass.

## Hard rules
- All project-bound reads/writes require tenant and project authorization.
- AI-generated Facts begin as PENDING.
- Evidence extracted from files must reference immutable DocumentAnchor records.
- Reference documents may shape style/structure but may never establish client Facts.
- Agent workflows write through Domain Services, never directly through SQLAlchemy sessions.
- Original DocumentVersion and DocumentAnchor rows are immutable.
- Long-running external calls never hold a DB transaction open.


## Frontend
- Frontend implementation lives under `web/`.
- Before editing frontend code, read `web/AGENTS.md`.
- Astryx is the primary frontend design system; do not add a competing primitive UI kit.
- ESG frontend components must preserve the same Evidence / Reference / Fact provenance boundaries enforced by the Service.
