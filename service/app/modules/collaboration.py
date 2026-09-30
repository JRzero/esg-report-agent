from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.models import UUIDPKMixin


class Comment(UUIDPKMixin, Base):
    __tablename__ = "comment"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(40), index=True)
    target_id: Mapped[UUID] = mapped_column(index=True)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("comment.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
