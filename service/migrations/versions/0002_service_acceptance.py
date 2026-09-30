"""service acceptance hardening

Revision ID: 0002_service_acceptance
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_service_acceptance"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


TENANT_TABLES = [
    "company",
    "project",
    "project_member",
    "document",
    "document_anchor",
    "context_binding",
    "fact",
    "fact_conflict_group",
    "report",
    "report_section",
    "report_block",
    "missing_item",
    "ai_task",
    "audit_log",
]


def upgrade():
    op.create_table(
        "comment",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("comment.id"), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("resolved_by", sa.Uuid(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_comment_tenant_id", "comment", ["tenant_id"])
    op.create_index("ix_comment_project_id", "comment", ["project_id"])
    op.create_index("ix_comment_target_type", "comment", ["target_type"])
    op.create_index("ix_comment_status", "comment", ["status"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in TENANT_TABLES:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(
                    f"""CREATE POLICY {table}_tenant_isolation ON "{table}"
                    USING (
                      current_setting('app.tenant_id', true) IS NULL
                      OR current_setting('app.tenant_id', true) = ''
                      OR tenant_id = current_setting('app.tenant_id', true)::uuid
                    )
                    WITH CHECK (
                      current_setting('app.tenant_id', true) IS NULL
                      OR current_setting('app.tenant_id', true) = ''
                      OR tenant_id = current_setting('app.tenant_id', true)::uuid
                    )"""
                )
            )
        op.execute("ALTER TABLE comment ENABLE ROW LEVEL SECURITY")
        op.execute(
            """CREATE POLICY comment_tenant_isolation ON comment
            USING (
              current_setting('app.tenant_id', true) IS NULL
              OR current_setting('app.tenant_id', true) = ''
              OR tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
              current_setting('app.tenant_id', true) IS NULL
              OR current_setting('app.tenant_id', true) = ''
              OR tenant_id = current_setting('app.tenant_id', true)::uuid
            )"""
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in TENANT_TABLES:
            op.execute(sa.text(f'DROP POLICY IF EXISTS {table}_tenant_isolation ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.execute("DROP POLICY IF EXISTS comment_tenant_isolation ON comment")
        op.execute("ALTER TABLE comment DISABLE ROW LEVEL SECURITY")
    op.drop_table("comment")
