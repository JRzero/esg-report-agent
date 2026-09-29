from dataclasses import dataclass
from uuid import UUID
@dataclass(frozen=True)
class RequestContext:
    user_id: UUID
    tenant_id: UUID
    membership_id: UUID
    tenant_role: str
    project_id: UUID | None = None
    project_role: str | None = None
