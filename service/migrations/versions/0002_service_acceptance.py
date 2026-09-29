"""service acceptance hardening: comments and tenant RLS

Revision ID: 0002_service_acceptance
Revises: 0001_initial
"""

from alembic import op

from app.modules.models import Comment

revision = "0002_service_acceptance"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


DIRECT_TENANT_TABLES = [
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
    "comment",
]

CHILD_POLICIES = {
    "document_version": "EXISTS (SELECT 1 FROM document d WHERE d.id = document_id AND d.tenant_id = app_current_tenant())",
    "fact_evidence": "EXISTS (SELECT 1 FROM fact f WHERE f.id = fact_id AND f.tenant_id = app_current_tenant())",
    "fact_revision": "EXISTS (SELECT 1 FROM fact f WHERE f.id = fact_id AND f.tenant_id = app_current_tenant())",
    "fact_conflict_member": "EXISTS (SELECT 1 FROM fact_conflict_group g WHERE g.id = conflict_group_id AND g.tenant_id = app_current_tenant())",
    "project_standard": "EXISTS (SELECT 1 FROM project p WHERE p.id = project_id AND p.tenant_id = app_current_tenant())",
    "project_disclosure": "EXISTS (SELECT 1 FROM project p WHERE p.id = project_id AND p.tenant_id = app_current_tenant())",
    "project_requirement_status": "EXISTS (SELECT 1 FROM project p WHERE p.id = project_id AND p.tenant_id = app_current_tenant())",
    "disclosure_fact_map": "EXISTS (SELECT 1 FROM project p WHERE p.id = project_id AND p.tenant_id = app_current_tenant())",
    "report_template_version": "EXISTS (SELECT 1 FROM report_template t WHERE t.id = template_id AND (t.tenant_id IS NULL OR t.tenant_id = app_current_tenant()))",
    "report_template_section": "EXISTS (SELECT 1 FROM report_template_version v JOIN report_template t ON t.id = v.template_id WHERE v.id = template_version_id AND (t.tenant_id IS NULL OR t.tenant_id = app_current_tenant()))",
    "section_disclosure_map": "EXISTS (SELECT 1 FROM report_section s WHERE s.id = section_id AND s.tenant_id = app_current_tenant())",
    "report_block_revision": "EXISTS (SELECT 1 FROM report_block b WHERE b.id = block_id AND b.tenant_id = app_current_tenant())",
    "claim": "EXISTS (SELECT 1 FROM report_block_revision r JOIN report_block b ON b.id = r.block_id WHERE r.id = block_revision_id AND b.tenant_id = app_current_tenant())",
    "citation": "EXISTS (SELECT 1 FROM claim c JOIN report_block_revision r ON r.id = c.block_revision_id JOIN report_block b ON b.id = r.block_id WHERE c.id = claim_id AND b.tenant_id = app_current_tenant())",
    "ai_trace": "EXISTS (SELECT 1 FROM ai_task t WHERE t.id = ai_task_id AND t.tenant_id = app_current_tenant())",
    "ai_trace_context": "EXISTS (SELECT 1 FROM ai_trace tr JOIN ai_task t ON t.id = tr.ai_task_id WHERE tr.id = trace_id AND t.tenant_id = app_current_tenant())",
    "report_export": "EXISTS (SELECT 1 FROM report r WHERE r.id = report_id AND r.tenant_id = app_current_tenant())",
}


def _policy(table: str, using: str, check: str | None = None) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
    statement = f'CREATE POLICY tenant_isolation ON "{table}" USING ({using})'
    if check:
        statement += f' WITH CHECK ({check})'
    op.execute(statement)


def upgrade() -> None:
    # 0001 is the pre-release bootstrap migration and uses current metadata.
    # checkfirst keeps this migration valid both for databases upgraded from the
    # original 0001 and for fresh developer databases created after Comment existed.
    Comment.__table__.create(bind=op.get_bind(), checkfirst=True)

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_tenant()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        AS $$
          SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid
        $$;
        """
    )

    for table in DIRECT_TENANT_TABLES:
        expr = "tenant_id = app_current_tenant()"
        _policy(table, expr, expr)

    _policy(
        "report_template",
        "tenant_id IS NULL OR tenant_id = app_current_tenant()",
        "tenant_id = app_current_tenant()",
    )
    _policy(
        "metric_definition",
        "tenant_id IS NULL OR tenant_id = app_current_tenant()",
        "tenant_id IS NULL OR tenant_id = app_current_tenant()",
    )

    for table, expr in CHILD_POLICIES.items():
        _policy(table, expr, expr)


def downgrade() -> None:
    for table in [*DIRECT_TENANT_TABLES, "report_template", "metric_definition", *CHILD_POLICIES]:
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    op.execute("DROP FUNCTION IF EXISTS app_current_tenant()")
    Comment.__table__.drop(bind=op.get_bind(), checkfirst=True)
