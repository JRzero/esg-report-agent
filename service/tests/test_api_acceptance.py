from __future__ import annotations

from io import BytesIO
from uuid import UUID

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.ai.schemas import ClaimDraft, DraftBlock, SectionDraft, SectionPlan
from app.ai.workflows import SectionPlanningWorkflow, SectionWritingWorkflow
from app.core.database import SessionLocal
from app.modules.models import (
    Claim,
    Disclosure,
    DisclosureRequirement,
    Document,
    DocumentAnchor,
    MetricDefinition,
    Project,
    ReportBlock,
    ReportBlockRevision,
    Standard,
    StandardVersion,
    TenantMembership,
)
from app.workers.tasks import _process_document
from conftest import login, seed_tenant


def make_xlsx(employee_total: int = 1287) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "员工统计"
    sheet["A1"] = "员工总数"
    sheet["B1"] = employee_total
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


async def create_company_project(client, headers):
    company_response = await client.post(
        "/api/v1/companies",
        json={"name": "Example Manufacturing", "country": "CN"},
        headers=headers,
    )
    assert company_response.status_code == 201, company_response.text
    company_id = company_response.json()["id"]
    project_response = await client.post(
        "/api/v1/projects",
        json={
            "company_id": company_id,
            "name": "Example 2026 ESG Report",
            "report_year": 2026,
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
        },
        headers=headers,
    )
    assert project_response.status_code == 201, project_response.text
    return company_id, project_response.json()["id"]


@pytest.mark.asyncio
async def test_rbac_and_project_isolation(client):
    await seed_tenant(email="owner@example.com")
    headers = await login(client, "owner@example.com")
    company_id, project_id = await create_company_project(client, headers)

    reviewer_response = await client.post(
        "/api/v1/tenant/members",
        json={
            "email": "reviewer@example.com",
            "name": "Reviewer",
            "password": "reviewer123",
            "member_type": "INTERNAL",
            "tenant_role": "MEMBER",
        },
        headers=headers,
    )
    assert reviewer_response.status_code == 201
    reviewer_membership_id = reviewer_response.json()["membership"]["id"]
    add_response = await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"membership_id": reviewer_membership_id, "project_role": "REVIEWER"},
        headers=headers,
    )
    assert add_response.status_code == 201

    reviewer_headers = await login(client, "reviewer@example.com", "reviewer123")
    assert (await client.get(f"/api/v1/projects/{project_id}", headers=reviewer_headers)).status_code == 200
    denied = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Reviewer must not edit"},
        headers=reviewer_headers,
    )
    assert denied.status_code == 404

    await seed_tenant(code="tenant-b", email="other@example.com")
    other_headers = await login(client, "other@example.com")
    cross_tenant = await client.get(f"/api/v1/projects/{project_id}", headers=other_headers)
    assert cross_tenant.status_code == 404

    active_company_delete = await client.delete(f"/api/v1/companies/{company_id}", headers=headers)
    assert active_company_delete.status_code == 409


@pytest.mark.asyncio
async def test_reference_document_cannot_be_fact_evidence(client):
    await seed_tenant()
    headers = await login(client, "admin@example.com")
    _, project_id = await create_company_project(client, headers)

    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        data={"source_type": "REFERENCE"},
        files={
            "file": (
                "industry.xlsx",
                make_xlsx(999),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    version_id = upload.json()["version_id"]
    await _process_document(version_id)

    anchors = await client.get(f"/api/v1/document-versions/{version_id}/anchors", headers=headers)
    assert anchors.status_code == 200
    anchor_id = next(item["id"] for item in anchors.json() if item["cell_range"] == "B1")

    fact = await client.post(
        f"/api/v1/projects/{project_id}/facts",
        headers=headers,
        json={
            "name": "Employee total",
            "metric_code": "EMPLOYEE_TOTAL",
            "value_type": "NUMBER",
            "number_value": 999,
            "unit": "person",
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
            "entity_scope": "GROUP",
            "anchor_ids": [anchor_id],
            "source_type": "AI",
        },
    )
    assert fact.status_code == 409
    assert fact.json()["error"]["code"] == "INVALID_FACT_EVIDENCE"


@pytest.mark.asyncio
async def test_evidence_fact_gri_report_citation_export_e2e(client):
    tenant_id, _, _ = await seed_tenant()
    headers = await login(client, "admin@example.com")
    _, project_id = await create_company_project(client, headers)

    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        data={"source_type": "EVIDENCE", "category_code": "employees"},
        files={
            "file": (
                "employees.xlsx",
                make_xlsx(1287),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    version_id = upload.json()["version_id"]
    await _process_document(version_id)

    anchors_response = await client.get(
        f"/api/v1/document-versions/{version_id}/anchors",
        headers=headers,
    )
    assert anchors_response.status_code == 200
    b1 = next(item for item in anchors_response.json() if item["cell_range"] == "B1")
    assert b1["raw_text"] == "1287"

    async with SessionLocal() as session:
        metric = MetricDefinition(
            code="EMPLOYEE_TOTAL",
            name="Employee total",
            data_type="NUMBER",
            default_unit="person",
        )
        standard = Standard(code="GRI", name="GRI Standards", publisher="GRI")
        session.add_all([metric, standard])
        await session.flush()
        version = StandardVersion(
            standard_id=standard.id,
            version_code="2021",
            name="GRI 2021",
        )
        session.add(version)
        await session.flush()
        disclosure = Disclosure(
            standard_version_id=version.id,
            code="GRI 2-7",
            title="Employees",
        )
        session.add(disclosure)
        await session.flush()
        session.add_all(
            [
                DisclosureRequirement(
                    disclosure_id=disclosure.id,
                    requirement_code="a",
                    content="Report total employees",
                    required_data_json={"metric_codes": ["EMPLOYEE_TOTAL"]},
                ),
                DisclosureRequirement(
                    disclosure_id=disclosure.id,
                    requirement_code="b",
                    content="Report employee breakdowns",
                    required_data_json={"metric_codes": ["EMPLOYEE_BY_GENDER"]},
                ),
            ]
        )
        await session.commit()
        metric_id = str(metric.id)
        standard_version_id = str(version.id)

    fact_response = await client.post(
        f"/api/v1/projects/{project_id}/facts",
        headers=headers,
        json={
            "fact_type": "METRIC",
            "metric_definition_id": metric_id,
            "metric_code": "EMPLOYEE_TOTAL",
            "name": "Employee total",
            "value_type": "NUMBER",
            "number_value": 1287,
            "raw_value": "1287",
            "unit": "person",
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
            "entity_scope": "GROUP",
            "anchor_ids": [b1["id"]],
            "source_type": "AI",
        },
    )
    assert fact_response.status_code == 201, fact_response.text
    fact_id = fact_response.json()["id"]

    confirm = await client.post(f"/api/v1/facts/{fact_id}/confirm", headers=headers)
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "CONFIRMED"

    evidence = await client.get(f"/api/v1/facts/{fact_id}/evidence", headers=headers)
    assert evidence.status_code == 200
    assert evidence.json()[0]["document"]["source_type"] == "EVIDENCE"

    attach = await client.post(
        f"/api/v1/projects/{project_id}/standards/{standard_version_id}",
        headers=headers,
    )
    assert attach.status_code == 201

    mapping = await client.post(
        f"/api/v1/projects/{project_id}/ai/disclosure-mapping",
        headers=headers,
    )
    assert mapping.status_code == 200
    assert mapping.json()["mappings_created"] == 1

    requirements = await client.get(
        f"/api/v1/projects/{project_id}/requirements",
        headers=headers,
    )
    statuses = {item["code"]: item["status"] for item in requirements.json()}
    assert statuses == {"a": "COVERED", "b": "MISSING"}

    missing = await client.post(
        f"/api/v1/projects/{project_id}/ai/missing-data-analysis",
        headers=headers,
    )
    assert missing.status_code == 200
    assert missing.json()["missing_items_created"] == 1

    template = await client.post(
        "/api/v1/report-templates",
        headers=headers,
        json={"name": "Consulting ESG Template"},
    )
    assert template.status_code == 201
    template_version = await client.post(
        f"/api/v1/report-templates/{template.json()['id']}/versions",
        headers=headers,
        json={"source_type": "MANUAL"},
    )
    assert template_version.status_code == 201
    template_version_id = template_version.json()["id"]
    template_section = await client.post(
        f"/api/v1/report-template-versions/{template_version_id}/sections",
        headers=headers,
        json={"title": "Employees", "level": 1, "sort_order": 1},
    )
    assert template_section.status_code == 201

    report_response = await client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers=headers,
        json={
            "title": "Example 2026 ESG Report",
            "template_version_id": template_version_id,
            "language": "en",
        },
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]
    sections = await client.get(f"/api/v1/reports/{report_id}/sections", headers=headers)
    section_id = sections.json()[0]["id"]

    class FakeLLM:
        async def generate_structured(self, system, user, schema, model_profile="STRONG"):
            if schema is SectionPlan:
                return SectionPlan(
                    goal="Describe workforce",
                    recommended_structure=["Workforce overview"],
                    fact_ids=[UUID(fact_id)],
                )
            if schema is SectionDraft:
                return SectionDraft(
                    blocks=[
                        DraftBlock(
                            type="PARAGRAPH",
                            content="The Group employed 1,287 people in 2026.",
                            claims=[
                                ClaimDraft(
                                    text="The Group employed 1,287 people in 2026.",
                                    risk_level="HIGH",
                                    fact_ids=[UUID(fact_id)],
                                )
                            ],
                        )
                    ]
                )
            raise AssertionError(schema)

    async with SessionLocal() as session:
        plan = await SectionPlanningWorkflow(session, FakeLLM()).run(
            UUID(project_id), UUID(section_id)
        )
        assert plan["fact_ids"] == [fact_id]
        await session.commit()

    async with SessionLocal() as session:
        blocks = await SectionWritingWorkflow(session, FakeLLM()).run(
            tenant_id,
            UUID(project_id),
            (await session.scalar(select(TenantMembership.user_id).where(TenantMembership.tenant_id == tenant_id))),
            UUID(section_id),
        )
        assert len(blocks) == 1
        await session.commit()
        block_id = blocks[0].id

    revisions = await client.get(f"/api/v1/blocks/{block_id}/revisions", headers=headers)
    revision_id = revisions.json()[0]["id"]
    claims = await client.get(f"/api/v1/block-revisions/{revision_id}/claims", headers=headers)
    claim_id = claims.json()[0]["id"]
    assert claims.json()[0]["verification_status"] == "VERIFIED"

    citations = await client.get(f"/api/v1/claims/{claim_id}/citations", headers=headers)
    citation_id = citations.json()[0]["id"]
    trace = await client.get(f"/api/v1/citations/{citation_id}/trace", headers=headers)
    assert trace.status_code == 200
    assert trace.json()["fact"]["id"] == fact_id
    assert trace.json()["anchor"]["cell"] == "B1"

    verify = await client.post(f"/api/v1/claims/{claim_id}/verify", headers=headers)
    assert verify.status_code == 200
    assert verify.json() == {"claim_id": claim_id, "status": "VERIFIED", "reasons": []}

    edit = await client.patch(
        f"/api/v1/blocks/{block_id}",
        headers=headers,
        json={"content": "Edited content.", "change_reason": "Consultant edit"},
    )
    assert edit.status_code == 200
    assert edit.json()["current_revision_no"] == 2
    restore = await client.post(
        f"/api/v1/blocks/{block_id}/restore/{revision_id}",
        headers=headers,
    )
    assert restore.status_code == 200
    assert restore.json()["current_revision_no"] == 3

    export = await client.post(f"/api/v1/reports/{report_id}/exports", headers=headers)
    assert export.status_code == 201, export.text
    assert export.json()["status"] == "SUCCESS"
    assert export.json()["download_url"].startswith("file://")


@pytest.mark.asyncio
async def test_task_cancel_and_retry(client):
    await seed_tenant()
    headers = await login(client, "admin@example.com")
    _, project_id = await create_company_project(client, headers)
    report = await client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers=headers,
        json={"title": "Report"},
    )
    section = await client.post(
        f"/api/v1/reports/{report.json()['id']}/sections",
        headers=headers,
        json={"title": "Environment"},
    )
    queued = await client.post(
        f"/api/v1/sections/{section.json()['id']}/ai/writing-plan",
        headers={**headers, "Idempotency-Key": "plan-1"},
    )
    assert queued.status_code == 202
    task_id = queued.json()["task_id"]

    cancelled = await client.post(f"/api/v1/tasks/{task_id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    retried = await client.post(f"/api/v1/tasks/{task_id}/retry", headers=headers)
    assert retried.status_code == 200
    assert retried.json()["status"] == "PENDING"

    same = await client.post(
        f"/api/v1/sections/{section.json()['id']}/ai/writing-plan",
        headers={**headers, "Idempotency-Key": "plan-1"},
    )
    assert same.status_code == 202
    assert same.json()["task_id"] == task_id
