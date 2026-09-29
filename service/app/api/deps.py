from uuid import UUID
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, set_tenant_context
from app.core.security import decode_token
from app.core.errors import DomainError
from app.core.context import RequestContext
from app.modules.models import User,TenantMembership
bearer=HTTPBearer(auto_error=False)
async def current_context(creds:HTTPAuthorizationCredentials|None=Depends(bearer),db:AsyncSession=Depends(get_db))->RequestContext:
    if not creds: raise DomainError('AUTH_REQUIRED','Authentication required',401)
    try: p=decode_token(creds.credentials)
    except Exception: raise DomainError('AUTH_INVALID_TOKEN','Invalid token',401)
    uid=UUID(p['sub']); tid=UUID(p['tenant_id']); mid=UUID(p['membership_id'])
    m=await db.scalar(select(TenantMembership).where(TenantMembership.id==mid,TenantMembership.user_id==uid,TenantMembership.tenant_id==tid,TenantMembership.status=='ACTIVE'))
    if not m: raise DomainError('AUTH_INVALID_MEMBERSHIP','Membership is not active',401)
    await set_tenant_context(db,str(tid)); return RequestContext(uid,tid,mid,m.tenant_role,m.member_type,m.company_id)
