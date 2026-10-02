from __future__ import annotations

from io import BytesIO
from uuid import UUID

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.ai.schemas import ClaimDraft, DraftBlock, SectionDraft, SectionPlan
from app.ai.workflows import SectionPlanningWorkflow, SectionWritingWorkflow
from app.core.database import SessionLocal
from app.core.errors import Conflict
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
            "metric_code": "EMPLOYEE_TOTAL_PLANNING",
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
        disclosure_id = str(disclosure.id)

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

    mapped_section_disclosure = await client.post(
        f"/api/v1/sections/{section_id}/disclosures/{disclosure_id}",
        headers=headers,
    )
    assert mapped_section_disclosure.status_code == 201, mapped_section_disclosure.text

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
        assert plan["status"] == "DRAFT"
        await session.commit()

    confirm_plan = await client.put(
        f"/api/v1/sections/{section_id}/writing-plan",
        headers=headers,
        json={
            "goal": plan["goal"],
            "recommended_structure": plan["recommended_structure"],
            "key_messages": plan["key_messages"],
            "disclosure_ids": plan["disclosure_ids"],
            "requirement_ids": plan["requirement_ids"],
            "fact_ids": plan["fact_ids"],
            "evidence_anchor_ids": plan["evidence_anchor_ids"],
            "missing_item_ids": plan["missing_item_ids"],
            "missing_items": plan["missing_items"],
            "warnings": plan["warnings"],
            "status": "CONFIRMED",
        },
    )
    assert confirm_plan.status_code == 200, confirm_plan.text
    assert confirm_plan.json()["status"] == "CONFIRMED"

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


@pytest.mark.asyncio
async def test_fact_evidence_trace_and_revision_history(client):
    await seed_tenant()
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

    anchors = await client.get(
        f"/api/v1/document-versions/{version_id}/anchors",
        headers=headers,
    )
    b1 = next(item for item in anchors.json() if item["cell_range"] == "B1")

    created = await client.post(
        f"/api/v1/projects/{project_id}/facts",
        headers=headers,
        json={
            "fact_type": "METRIC",
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
    assert created.status_code == 201, created.text
    fact_id = created.json()["id"]

    edited = await client.patch(
        f"/api/v1/facts/{fact_id}",
        headers=headers,
        json={"unit": "people"},
    )
    assert edited.status_code == 200, edited.text

    confirmed = await client.post(
        f"/api/v1/facts/{fact_id}/confirm",
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    evidence = await client.get(
        f"/api/v1/facts/{fact_id}/evidence",
        headers=headers,
    )
    assert evidence.status_code == 200, evidence.text
    trace = evidence.json()[0]
    assert trace["document"]["source_type"] == "EVIDENCE"
    assert trace["document"]["version_id"] == version_id
    assert trace["document"]["version_no"] == 1
    assert len(trace["document"]["sha256"]) == 64
    assert trace["anchor"]["type"] == "EXCEL_CELL"
    assert trace["anchor"]["sheet_name"] == "员工统计"
    assert trace["anchor"]["cell_range"] == "B1"
    assert trace["anchor"]["raw_text"] == "1287"
    assert trace["anchor"]["content_hash"]

    revisions = await client.get(
        f"/api/v1/facts/{fact_id}/revisions",
        headers=headers,
    )
    assert revisions.status_code == 200, revisions.text
    history = revisions.json()
    assert [item["change_type"] for item in history[:3]] == [
        "CONFIRMED",
        "HUMAN_EDIT",
        "AI_CREATED",
    ]
    assert [item["revision_no"] for item in history[:3]] == [3, 2, 1]
    assert history[0]["snapshot"]["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_fact_conflict_detail_and_human_resolution(client):
    await seed_tenant()
    headers = await login(client, "admin@example.com")
    _, project_id = await create_company_project(client, headers)

    base = {
        "fact_type": "METRIC",
        "metric_code": "EMPLOYEE_TOTAL",
        "name": "Employee total",
        "value_type": "NUMBER",
        "unit": "person",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "entity_scope": "GROUP",
        "anchor_ids": [],
        "source_type": "HUMAN",
    }
    first = await client.post(
        f"/api/v1/projects/{project_id}/facts",
        headers=headers,
        json={**base, "number_value": 1287, "raw_value": "1287"},
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        f"/api/v1/projects/{project_id}/facts",
        headers=headers,
        json={**base, "number_value": 1293, "raw_value": "1293"},
    )
    assert second.status_code == 201, second.text

    conflicts = await client.get(
        f"/api/v1/projects/{project_id}/fact-conflicts",
        headers=headers,
    )
    assert conflicts.status_code == 200, conflicts.text
    group = next(item for item in conflicts.json() if item["status"] == "OPEN")

    detail = await client.get(
        f"/api/v1/fact-conflicts/{group['id']}",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    member_ids = {item["id"] for item in detail.json()["members"]}
    assert member_ids == {first.json()["id"], second.json()["id"]}

    direct_confirm = await client.post(
        f"/api/v1/facts/{first.json()['id']}/confirm",
        headers=headers,
    )
    assert direct_confirm.status_code == 409
    assert direct_confirm.json()["error"]["code"] == "FACT_CONFLICT_UNRESOLVED"

    direct_reject = await client.post(
        f"/api/v1/facts/{second.json()['id']}/reject",
        headers=headers,
        json={"reason": "must resolve group"},
    )
    assert direct_reject.status_code == 409
    assert direct_reject.json()["error"]["code"] == "FACT_CONFLICT_UNRESOLVED"

    resolved = await client.post(
        f"/api/v1/fact-conflicts/{group['id']}/resolve",
        headers=headers,
        params={"fact_id": first.json()["id"]},
    )
    assert resolved.status_code == 200, resolved.text

    selected = await client.get(f"/api/v1/facts/{first.json()['id']}", headers=headers)
    rejected = await client.get(f"/api/v1/facts/{second.json()['id']}", headers=headers)
    assert selected.json()["status"] == "CONFIRMED"
    assert rejected.json()["status"] == "REJECTED"

    detail_after = await client.get(
        f"/api/v1/fact-conflicts/{group['id']}",
        headers=headers,
    )
    assert detail_after.json()["group"]["status"] == "RESOLVED"
    assert detail_after.json()["group"]["resolved_fact_id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_gri_workspace_applicability_mapping_and_missing_workflow(client):
    await seed_tenant()
    headers = await login(client, "admin@example.com")
    _, project_id = await create_company_project(client, headers)

    async with SessionLocal() as session:
        metric = MetricDefinition(
            code="EMPLOYEE_TOTAL_GRI_TEST",
            name="Employee total GRI test",
            data_type="NUMBER",
            default_unit="person",
        )
        standard = Standard(
            code="GRI-TEST",
            name="GRI Test Standard",
            publisher="Test Publisher",
        )
        session.add_all([metric, standard])
        await session.flush()
        version = StandardVersion(
            standard_id=standard.id,
            version_code="2021",
            name="GRI Test 2021",
        )
        session.add(version)
        await session.flush()
        disclosure = Disclosure(
            standard_version_id=version.id,
            code="GRI TEST 2-7",
            title="Employees",
            sort_order=1,
        )
        session.add(disclosure)
        await session.flush()
        session.add_all(
            [
                DisclosureRequirement(
                    disclosure_id=disclosure.id,
                    requirement_code="a",
                    content="Report total employees.",
                    required_data_json={"metric_codes": ["EMPLOYEE_TOTAL_GRI_TEST"]},
                    sort_order=1,
                ),
                DisclosureRequirement(
                    disclosure_id=disclosure.id,
                    requirement_code="b",
                    content="Report employee breakdown.",
                    required_data_json={"metric_codes": ["EMPLOYEE_BREAKDOWN_GRI_TEST"]},
                    sort_order=2,
                ),
            ]
        )
        await session.commit()
        metric_id = str(metric.id)
        standard_id = str(standard.id)
        version_id = str(version.id)

    attach = await client.post(
        f"/api/v1/projects/{project_id}/standards/{version_id}",
        headers=headers,
    )
    assert attach.status_code == 201, attach.text

    project_standards = await client.get(
        f"/api/v1/projects/{project_id}/standards",
        headers=headers,
    )
    assert project_standards.status_code == 200, project_standards.text
    attached = next(
        item for item in project_standards.json() if item["standard"]["id"] == standard_id
    )
    assert attached["version"]["id"] == version_id
    assert attached["is_primary"] is True

    fact = await client.post(
        f"/api/v1/projects/{project_id}/facts",
        headers=headers,
        json={
            "fact_type": "METRIC",
            "metric_definition_id": metric_id,
            "metric_code": "EMPLOYEE_TOTAL_GRI_TEST",
            "name": "Employee total",
            "value_type": "NUMBER",
            "number_value": 1287,
            "unit": "person",
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
            "entity_scope": "GROUP",
            "source_type": "HUMAN",
        },
    )
    assert fact.status_code == 201, fact.text
    fact_id = fact.json()["id"]
    confirmed = await client.post(f"/api/v1/facts/{fact_id}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text

    mapping = await client.post(
        f"/api/v1/projects/{project_id}/ai/disclosure-mapping",
        headers=headers,
    )
    assert mapping.status_code == 200, mapping.text
    assert mapping.json()["mappings_created"] == 1

    disclosures = await client.get(
        f"/api/v1/projects/{project_id}/disclosures",
        headers=headers,
    )
    project_disclosure = next(
        item for item in disclosures.json() if item["code"] == "GRI TEST 2-7"
    )
    assert project_disclosure["coverage_status"] == "PARTIAL"
    assert project_disclosure["disclosure_id"]

    detail = await client.get(
        f"/api/v1/projects/{project_id}/disclosures/{project_disclosure['id']}",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    detail_json = detail.json()
    requirement_statuses = {
        item["code"]: item["status"] for item in detail_json["requirements"]
    }
    assert requirement_statuses == {"a": "COVERED", "b": "MISSING"}
    assert [item["fact"]["id"] for item in detail_json["fact_maps"]] == [fact_id]

    requirements = await client.get(
        f"/api/v1/projects/{project_id}/requirements",
        headers=headers,
    )
    assert requirements.status_code == 200
    requirement = next(item for item in requirements.json() if item["code"] == "a")
    assert requirement["disclosure_code"] == "GRI TEST 2-7"
    assert requirement["disclosure_title"] == "Employees"

    not_applicable = await client.patch(
        f"/api/v1/projects/{project_id}/disclosures/{project_disclosure['id']}",
        headers=headers,
        json={
            "applicability": "NOT_APPLICABLE",
            "notes": "Not applicable for this project.",
        },
    )
    assert not_applicable.status_code == 200, not_applicable.text
    assert not_applicable.json()["applicability"] == "NOT_APPLICABLE"

    na_detail = await client.get(
        f"/api/v1/projects/{project_id}/disclosures/{project_disclosure['id']}",
        headers=headers,
    )
    assert {item["status"] for item in na_detail.json()["requirements"]} == {
        "NOT_APPLICABLE"
    }
    assert na_detail.json()["fact_maps"] == []

    applicable = await client.patch(
        f"/api/v1/projects/{project_id}/disclosures/{project_disclosure['id']}",
        headers=headers,
        json={"applicability": "APPLICABLE"},
    )
    assert applicable.status_code == 200, applicable.text

    restored_detail = await client.get(
        f"/api/v1/projects/{project_id}/disclosures/{project_disclosure['id']}",
        headers=headers,
    )
    restored = {
        item["code"]: item["status"] for item in restored_detail.json()["requirements"]
    }
    assert restored == {"a": "COVERED", "b": "MISSING"}
    assert [item["fact"]["id"] for item in restored_detail.json()["fact_maps"]] == [fact_id]

    missing_analysis = await client.post(
        f"/api/v1/projects/{project_id}/ai/missing-data-analysis",
        headers=headers,
    )
    assert missing_analysis.status_code == 200, missing_analysis.text
    assert missing_analysis.json()["missing_items_created"] == 1

    missing_items = await client.get(
        f"/api/v1/projects/{project_id}/missing-items",
        headers=headers,
    )
    assert missing_items.status_code == 200, missing_items.text
    missing_item = next(
        item for item in missing_items.json() if item["requirement_id"]
    )
    assert missing_item["status"] == "MISSING"

    for status in ["REQUESTED", "RECEIVED", "RESOLVED"]:
        updated = await client.patch(
            f"/api/v1/missing-items/{missing_item['id']}",
            headers=headers,
            json={"status": status},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["status"] == status

    rejected = await client.post(
        f"/api/v1/facts/{fact_id}/reject",
        headers=headers,
        json={"reason": "Superseded by corrected data"},
    )
    assert rejected.status_code == 200, rejected.text

    remap = await client.post(
        f"/api/v1/projects/{project_id}/ai/disclosure-mapping",
        headers=headers,
    )
    assert remap.status_code == 200, remap.text
    assert remap.json()["mappings_created"] == 0

    stale_free_detail = await client.get(
        f"/api/v1/projects/{project_id}/disclosures/{project_disclosure['id']}",
        headers=headers,
    )
    assert stale_free_detail.json()["fact_maps"] == []
    assert {
        item["status"] for item in stale_free_detail.json()["requirements"]
    } == {"MISSING"}


@pytest.mark.asyncio
async def test_report_section_planning_context_is_scoped_and_invalidated(client):
    await seed_tenant()
    headers = await login(client, "admin@example.com")
    _, project_id = await create_company_project(client, headers)

    async with SessionLocal() as session:
        employee_metric = MetricDefinition(
            code="EMPLOYEE_TOTAL_PLANNING",
            name="Employee total planning",
            data_type="NUMBER",
            default_unit="person",
        )
        scope1_metric = MetricDefinition(
            code="GHG_SCOPE1_PLANNING",
            name="Scope 1 planning",
            data_type="NUMBER",
            default_unit="tCO2e",
        )
        standard = Standard(
            code="GRI-PLANNING",
            name="GRI Planning Test",
            publisher="Test Publisher",
        )
        session.add_all([employee_metric, scope1_metric, standard])
        await session.flush()
        standard_version = StandardVersion(
            standard_id=standard.id,
            version_code="2021",
            name="GRI Planning 2021",
        )
        session.add(standard_version)
        await session.flush()
        disclosure = Disclosure(
            standard_version_id=standard_version.id,
            code="GRI 2-7",
            title="Employees",
            sort_order=1,
        )
        session.add(disclosure)
        await session.flush()
        session.add_all(
            [
                DisclosureRequirement(
                    disclosure_id=disclosure.id,
                    requirement_code="a",
                    content="Report total employees.",
                    required_data_json={"metric_codes": ["EMPLOYEE_TOTAL_PLANNING"]},
                    sort_order=1,
                ),
                DisclosureRequirement(
                    disclosure_id=disclosure.id,
                    requirement_code="b",
                    content="Report employee breakdown.",
                    required_data_json={"metric_codes": ["EMPLOYEE_BREAKDOWN_PLANNING"]},
                    sort_order=2,
                ),
            ]
        )
        await session.commit()
        employee_metric_id = str(employee_metric.id)
        scope1_metric_id = str(scope1_metric.id)
        gri_2021 = {"id": str(standard_version.id)}
        employees_disclosure = {"id": str(disclosure.id)}

    report = await client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers=headers,
        json={"title": "2026 ESG Report", "language": "zh-CN"},
    )
    assert report.status_code == 201, report.text
    report_id = report.json()["id"]
    section = await client.post(
        f"/api/v1/reports/{report_id}/sections",
        headers=headers,
        json={
            "title": "员工与发展",
            "description": "披露员工规模与结构。",
            "level": 1,
            "sort_order": 1,
        },
    )
    assert section.status_code == 201, section.text
    section_id = section.json()["id"]

    unattached = await client.post(
        f"/api/v1/sections/{section_id}/disclosures/{employees_disclosure['id']}",
        headers=headers,
    )
    assert unattached.status_code == 409, unattached.text
    assert unattached.json()["error"]["code"] == "DISCLOSURE_NOT_ATTACHED_TO_PROJECT"

    attached = await client.post(
        f"/api/v1/projects/{project_id}/standards/{gri_2021['id']}",
        headers=headers,
    )
    assert attached.status_code == 201, attached.text

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
    anchors = await client.get(
        f"/api/v1/document-versions/{version_id}/anchors",
        headers=headers,
    )
    employee_anchor = next(item for item in anchors.json() if item["cell_range"] == "B1")

    employee_fact = await client.post(
        f"/api/v1/projects/{project_id}/facts",
        headers=headers,
        json={
            "fact_type": "METRIC",
            "metric_definition_id": employee_metric_id,
            "metric_code": "EMPLOYEE_TOTAL",
            "name": "员工总人数",
            "value_type": "NUMBER",
            "number_value": 1287,
            "raw_value": "1287",
            "unit": "person",
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
            "entity_scope": "GROUP",
            "anchor_ids": [employee_anchor["id"]],
            "source_type": "AI",
        },
    )
    assert employee_fact.status_code == 201, employee_fact.text
    employee_fact_id = employee_fact.json()["id"]
    assert (
        await client.post(f"/api/v1/facts/{employee_fact_id}/confirm", headers=headers)
    ).status_code == 200

    unrelated_fact = await client.post(
        f"/api/v1/projects/{project_id}/facts",
        headers=headers,
        json={
            "fact_type": "METRIC",
            "metric_definition_id": scope1_metric_id,
            "metric_code": "GHG_SCOPE1_PLANNING",
            "name": "Scope 1 emissions",
            "value_type": "NUMBER",
            "number_value": 1200,
            "unit": "tCO2e",
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
            "entity_scope": "GROUP",
            "source_type": "HUMAN",
        },
    )
    assert unrelated_fact.status_code == 201, unrelated_fact.text
    unrelated_fact_id = unrelated_fact.json()["id"]
    assert (
        await client.post(f"/api/v1/facts/{unrelated_fact_id}/confirm", headers=headers)
    ).status_code == 200

    mapped = await client.post(
        f"/api/v1/projects/{project_id}/ai/disclosure-mapping",
        headers=headers,
    )
    assert mapped.status_code == 200, mapped.text

    section_mapping = await client.post(
        f"/api/v1/sections/{section_id}/disclosures/{employees_disclosure['id']}",
        headers=headers,
    )
    assert section_mapping.status_code == 201, section_mapping.text

    missing = await client.post(
        f"/api/v1/projects/{project_id}/ai/missing-data-analysis",
        headers=headers,
    )
    assert missing.status_code == 200, missing.text

    context = await client.get(
        f"/api/v1/sections/{section_id}/planning-context",
        headers=headers,
    )
    assert context.status_code == 200, context.text
    context_json = context.json()
    assert [item["id"] for item in context_json["facts"]] == [employee_fact_id]
    assert unrelated_fact_id not in {item["id"] for item in context_json["facts"]}
    assert employee_anchor["id"] in {
        item["anchor_id"] for item in context_json["evidence"]
    }
    assert context_json["missing_items"]
    assert context_json["warnings"] == []

    stale_manual_plan = await client.put(
        f"/api/v1/sections/{section_id}/writing-plan",
        headers=headers,
        json={
            "goal": "Describe employees",
            "fact_ids": [unrelated_fact_id],
            "status": "CONFIRMED",
        },
    )
    assert stale_manual_plan.status_code == 409, stale_manual_plan.text
    assert stale_manual_plan.json()["error"]["code"] == "WRITING_PLAN_CONTEXT_STALE"

    class OutOfScopePlanLLM:
        async def generate_structured(self, system, user, schema, model_profile="STRONG"):
            assert schema is SectionPlan
            return SectionPlan(
                goal="Describe employees",
                fact_ids=[UUID(unrelated_fact_id)],
            )

    async with SessionLocal() as session:
        with pytest.raises(Conflict) as exc:
            await SectionPlanningWorkflow(session, OutOfScopePlanLLM()).run(
                UUID(project_id), UUID(section_id)
            )
        assert exc.value.code == "WRITING_PLAN_CONTEXT_STALE"

    requirement_ids = [item["id"] for item in context_json["requirements"]]
    missing_item_ids = [item["id"] for item in context_json["missing_items"]]

    class ValidPlanLLM:
        async def generate_structured(self, system, user, schema, model_profile="STRONG"):
            if schema is SectionPlan:
                return SectionPlan(
                    goal="Describe employees",
                    recommended_structure=["员工概览", "员工结构"],
                    key_messages=["Use confirmed employee data only"],
                    disclosure_ids=[UUID(employees_disclosure["id"])],
                    requirement_ids=[UUID(value) for value in requirement_ids],
                    fact_ids=[UUID(employee_fact_id)],
                    evidence_anchor_ids=[UUID(employee_anchor["id"])],
                    missing_item_ids=[UUID(value) for value in missing_item_ids],
                    warnings=["Employee breakdown remains missing"],
                )
            if schema is SectionDraft:
                return SectionDraft(blocks=[])
            raise AssertionError(schema)

    async with SessionLocal() as session:
        plan = await SectionPlanningWorkflow(session, ValidPlanLLM()).run(
            UUID(project_id), UUID(section_id)
        )
        assert plan["status"] == "DRAFT"
        assert plan["fact_ids"] == [employee_fact_id]
        await session.commit()

    async with SessionLocal() as session:
        with pytest.raises(Conflict) as exc:
            await SectionWritingWorkflow(session, ValidPlanLLM()).run(
                (await session.scalar(select(Project.tenant_id).where(Project.id == UUID(project_id)))),
                UUID(project_id),
                (await session.scalar(
                    select(TenantMembership.user_id).where(
                        TenantMembership.tenant_id
                        == (await session.scalar(
                            select(Project.tenant_id).where(Project.id == UUID(project_id))
                        ))
                    )
                )),
                UUID(section_id),
            )
        assert exc.value.code == "WRITING_PLAN_NOT_CONFIRMED"

    confirmed_plan = await client.put(
        f"/api/v1/sections/{section_id}/writing-plan",
        headers=headers,
        json={
            "goal": plan["goal"],
            "recommended_structure": plan["recommended_structure"],
            "key_messages": plan["key_messages"],
            "disclosure_ids": plan["disclosure_ids"],
            "requirement_ids": plan["requirement_ids"],
            "fact_ids": plan["fact_ids"],
            "evidence_anchor_ids": plan["evidence_anchor_ids"],
            "missing_item_ids": plan["missing_item_ids"],
            "missing_items": plan["missing_items"],
            "warnings": plan["warnings"],
            "status": "CONFIRMED",
        },
    )
    assert confirmed_plan.status_code == 200, confirmed_plan.text
    assert confirmed_plan.json()["status"] == "CONFIRMED"

    removed = await client.delete(
        f"/api/v1/sections/{section_id}/disclosures/{employees_disclosure['id']}",
        headers=headers,
    )
    assert removed.status_code == 204, removed.text
    refreshed_section = await client.get(
        f"/api/v1/sections/{section_id}",
        headers=headers,
    )
    assert refreshed_section.status_code == 200
    assert refreshed_section.json()["writing_plan"] == {}
