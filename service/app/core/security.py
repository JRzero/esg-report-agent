from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
try:
    from pwdlib import PasswordHash
    _password_hash = PasswordHash.recommended()
except Exception:
    _password_hash = None
from app.core.config import get_settings

settings=get_settings()

def hash_password(password: str) -> str:
    if _password_hash:
        return _password_hash.hash(password)
    import hashlib
    return 'dev$'+hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    if _password_hash and not hashed.startswith('dev$'):
        return _password_hash.verify(password, hashed)
    import hashlib
    return hashed == 'dev$'+hashlib.sha256(password.encode()).hexdigest()

def create_token(subject: str, tenant_id: str | None, membership_id: str | None, token_type='access') -> str:
    now=datetime.now(timezone.utc)
    delta=timedelta(minutes=settings.jwt_access_token_minutes) if token_type=='access' else timedelta(days=settings.jwt_refresh_token_days)
    payload={'sub':subject,'tenant_id':tenant_id,'membership_id':membership_id,'type':token_type,'iat':now,'exp':now+delta}
    return jwt.encode(payload, settings.jwt_secret, algorithm='HS256')

def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=['HS256'])
