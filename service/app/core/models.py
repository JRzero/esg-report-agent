from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.ids import new_id

class UUIDPKMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
