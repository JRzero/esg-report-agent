"""scope AI task idempotency to tenant principal

Revision ID: 0002_task_idempotency_scope
Revises: 0001_initial
"""
from alembic import op

revision = "0002_task_idempotency_scope"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE ai_task
        DROP CONSTRAINT IF EXISTS uq_ai_task_idempotency_key
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_ai_task_principal_idempotency'
            ) THEN
                ALTER TABLE ai_task
                ADD CONSTRAINT uq_ai_task_principal_idempotency
                UNIQUE (tenant_id, created_by, idempotency_key);
            END IF;
        END $$;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE ai_task
        DROP CONSTRAINT IF EXISTS uq_ai_task_principal_idempotency
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_ai_task_idempotency_key'
            ) THEN
                ALTER TABLE ai_task
                ADD CONSTRAINT uq_ai_task_idempotency_key
                UNIQUE (idempotency_key);
            END IF;
        END $$;
        """
    )
