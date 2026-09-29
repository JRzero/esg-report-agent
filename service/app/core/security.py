from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

settings = get_settings()
_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _password_hash.verify(password, hashed)
    except Exception:
        return False


def create_token(
    subject: str,
    tenant_id: str | None,
    membership_id: str | None,
    token_type: str = "access",
) -> str:
    now = datetime.now(timezone.utc)
    delta = (
        timedelta(minutes=settings.jwt_access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.jwt_refresh_token_days)
    )
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "membership_id": membership_id,
        "type": token_type,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
