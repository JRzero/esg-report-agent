from dataclasses import dataclass, field
from typing import Any

@dataclass
class DomainError(Exception):
    code: str
    message: str
    status_code: int = 400
    details: dict[str, Any] = field(default_factory=dict)

class NotFound(DomainError):
    def __init__(self, code='NOT_FOUND', message='Resource not found'):
        super().__init__(code, message, 404)
class Forbidden(DomainError):
    def __init__(self, code='FORBIDDEN', message='Access denied'):
        super().__init__(code, message, 403)
class Conflict(DomainError):
    def __init__(self, code='CONFLICT', message='Resource conflict'):
        super().__init__(code, message, 409)
