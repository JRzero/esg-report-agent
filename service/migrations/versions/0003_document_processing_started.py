"""track document processing start time

Revision ID: 0003_document_processing_started
Revises: 0002_task_idempotency_scope
"""
from alembic import op

revision = "0003_document_processing_started"
down_revision = "0002_task_idempotency_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE document_version
        ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ NULL
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE document_version
        DROP COLUMN IF EXISTS processing_started_at
        """
    )
