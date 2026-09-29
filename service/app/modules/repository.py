from typing import TypeVar, Generic
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import Base
T=TypeVar('T', bound=Base)
class Repository(Generic[T]):
    def __init__(self, session:AsyncSession, model:type[T]): self.session=session; self.model=model
    async def get(self, id:UUID)->T|None: return await self.session.get(self.model,id)
    async def add(self,obj:T)->T: self.session.add(obj); await self.session.flush(); return obj
    async def list(self,*criteria,offset=0,limit=100)->list[T]:
        q=select(self.model).where(*criteria).offset(offset).limit(limit)
        return list((await self.session.scalars(q)).all())
    async def count(self,*criteria)->int:
        q=select(func.count()).select_from(self.model).where(*criteria)
        return int((await self.session.scalar(q)) or 0)
