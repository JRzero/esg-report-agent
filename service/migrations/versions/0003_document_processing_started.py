"""track document processing start time

Revision ID: 0003_document_processing_started
Revises: 0002_task_idempotency_scope
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_document_processing_started"
down_revision = "0002_task_idempotency_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "document_version",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("document_version", "processing_started_at")
