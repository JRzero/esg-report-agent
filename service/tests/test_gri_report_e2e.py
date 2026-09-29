from io import BytesIO

import pytest
from openpyxl import Workbook

from app.ai.schemas import SectionDraft, SectionPlan
from app.core.database import SessionLocal
from app.modules.models import (
    Disclosure,
    DisclosureRequirement,
    MetricDefinition,
    Standard,
    StandardVersion,
)


def employee_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "员工统计"
    sheet["A1"] = "员工总人数"
    sheet["B1"] = 1287
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


async def create_evidence_fact(client, headers, project_id):
    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        data={"source_type": "EVIDENCE", "category_code": "employee"},
        files={
            "file": (
                "employee.xlsx",
                employee_workbook(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    version_id = upload.json()["version_id"]
    anchors = await client.get(
        f"/api/v1/document-versions/{version_id}/anchors",
        headers=headers,
    )
    anchor = next(item for item in anchors.json() if item["cell_range"] == "B1")
    fact = await client.post(
        f"/api/v1/projects/{project_id}/facts",
        headers=headers,
        json={
            "fact_type": "METRIC",
            "metric_code": "EMPLOYEE_TOTAL",
            "name": "员工总人数",
            "value_type": "NUMBER",
            "number_value": 1287,
            "unit": "person",
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
            "entity_scope": "GROUP",
            "anchor_ids": [anchor["id"]],
            "source_type": "AI",
        },
    )
    assert fact.status_code == 201, fact.text
    confirm = await client.post(
        f"/api/v1/facts/{fact.json()['id']}/confirm",
        headers=headers,
    )
    assert confirm.status_code == 200
    return fact.json()["id"], anchor["id"]


async def seed_standard():
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
        employee = Disclosure(
            standard_version_id=version.id,
            code="GRI 2-7",
            title="Employees",
            sort_order=1,
        )
        governance = Disclosure(
            standard_version_id=version.id,
            code="GRI 2-9",
            title="Governance structure",
            sort_order=2,
        )
        session.add_all([employee, governance])
        await session.flush()
        session.add_all(
            [
                DisclosureRequirement(
                    disclosure_id=employee.id,
                    requirement_code="a",
                    content="Report total employees.",
                    required_data_json={"metric_codes": ["EMPLOYEE_TOTAL"]},
                ),
                DisclosureRequirement(
                    disclosure_id=governance.id,
                    requirement_code="a",
                    content="Describe governance structure.",
                    required_data_json={"metric_codes": ["GOVERNANCE_STRUCTURE"]},
                ),
            ]
        )
        await session.commit()
        return version.id


class FakeGateway:
    async def generate_structured(self, system, user, schema, model_profile="STRONG"):
        if schema is SectionPlan:
            return SectionPlan(
                goal="Describe the workforce using confirmed evidence.",
                recommended_structure=["员工规模", "数据口径"],
                key_messages=["员工总人数为1287人"],
                missing_items=[],
                warnings=[],
            )
        if schema is SectionDraft:
            # The test replaces FACT_ID at construction time below.
            raise AssertionError("SectionDraft must be configured with a fact id")
        raise AssertionError(f"Unexpected schema: {schema}")


class WritingGateway:
    def __init__(self, fact_id):
        self.fact_id = fact_id

    async def generate_structured(self, system, user, schema, model_profile="STRONG"):
        if schema is SectionPlan:
            return SectionPlan(
                goal="Describe confirmed workforce data.",
                recommended_structure=["员工概况"],
                key_messages=["使用已确认事实"],
            )
        if schema is SectionDraft:
            return SectionDraft(
                blocks=[
                    {
                        "type": "PARAGRAPH",
                        "content": "截至2026年末，公司员工总人数为1287人。",
                        "claims": [
                            {
                                "text": "公司员工总人数为1287人",
                                "claim_type": "FACTUAL",
                                "risk_level": "HIGH",
                                "fact_ids": [self.fact_id],
                            }
                        ],
                    }
                ]
            )
        raise AssertionError(f"Unexpected schema: {schema}")


@pytest.mark.asyncio
async def test_gri_mapping_coverage_and_missing_items(client, seeded, admin_headers):
    version_id = await seed_standard()
    await create_evidence_fact(client, admin_headers, seeded["project"].id)

    attach = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/standards/{version_id}",
        headers=admin_headers,
    )
    assert attach.status_code == 201, attach.text

    mapping = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/ai/disclosure-mapping",
        headers=admin_headers,
    )
    assert mapping.status_code == 202, mapping.text
    task = await client.get(
        f"/api/v1/tasks/{mapping.json()['task_id']}",
        headers=admin_headers,
    )
    assert task.json()["status"] == "SUCCESS", task.text

    disclosures = await client.get(
        f"/api/v1/projects/{seeded['project'].id}/disclosures",
        headers=admin_headers,
    )
    by_code = {item["code"]: item["coverage_status"] for item in disclosures.json()}
    assert by_code["GRI 2-7"] == "COVERED"
    assert by_code["GRI 2-9"] == "MISSING"

    missing = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/ai/missing-data-analysis",
        headers=admin_headers,
    )
    assert missing.status_code == 202
    missing_task = await client.get(
        f"/api/v1/tasks/{missing.json()['task_id']}",
        headers=admin_headers,
    )
    assert missing_task.json()["status"] == "SUCCESS"

    items = await client.get(
        f"/api/v1/projects/{seeded['project'].id}/missing-items",
        headers=admin_headers,
    )
    assert len(items.json()) == 1
    assert items.json()[0]["name"].startswith("GRI 2-9")

    check = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/ai/gri-check",
        headers=admin_headers,
    )
    check_task = await client.get(
        f"/api/v1/tasks/{check.json()['task_id']}",
        headers=admin_headers,
    )
    assert check_task.json()["status"] == "SUCCESS"
    assert check_task.json()["result_json"]["requirements"]["COVERED"] == 1
    assert check_task.json()["result_json"]["requirements"]["MISSING"] == 1


@pytest.mark.asyncio
async def test_report_claim_citation_comment_and_docx_export(
    client,
    seeded,
    admin_headers,
    monkeypatch,
):
    fact_id, anchor_id = await create_evidence_fact(
        client, admin_headers, seeded["project"].id
    )

    template = await client.post(
        "/api/v1/report-templates",
        headers=admin_headers,
        json={"name": "ESG Standard Template"},
    )
    assert template.status_code == 201
    version = await client.post(
        f"/api/v1/report-templates/{template.json()['id']}/versions",
        headers=admin_headers,
        json={"source_type": "MANUAL"},
    )
    assert version.status_code == 201
    section_template = await client.post(
        f"/api/v1/report-template-versions/{version.json()['id']}/sections",
        headers=admin_headers,
        json={"title": "员工与发展", "level": 1, "sort_order": 1},
    )
    assert section_template.status_code == 201

    report = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/reports",
        headers=admin_headers,
        json={
            "title": "Example 2026 ESG Report",
            "template_version_id": version.json()["id"],
            "language": "zh-CN",
        },
    )
    assert report.status_code == 201, report.text

    sections = await client.get(
        f"/api/v1/reports/{report.json()['id']}/sections",
        headers=admin_headers,
    )
    assert len(sections.json()) == 1
    section_id = sections.json()[0]["id"]

    gateway = WritingGateway(fact_id)
    monkeypatch.setattr("app.ai.workflows.LLMGateway", lambda: gateway)

    plan = await client.post(
        f"/api/v1/sections/{section_id}/ai/writing-plan",
        headers=admin_headers,
    )
    plan_task = await client.get(
        f"/api/v1/tasks/{plan.json()['task_id']}",
        headers=admin_headers,
    )
    assert plan_task.json()["status"] == "SUCCESS", plan_task.text

    generate = await client.post(
        f"/api/v1/sections/{section_id}/ai/generate",
        headers=admin_headers,
    )
    generation_task = await client.get(
        f"/api/v1/tasks/{generate.json()['task_id']}",
        headers=admin_headers,
    )
    assert generation_task.json()["status"] == "SUCCESS", generation_task.text

    blocks = await client.get(
        f"/api/v1/sections/{section_id}/blocks",
        headers=admin_headers,
    )
    assert len(blocks.json()) == 1
    block_id = blocks.json()[0]["id"]

    revisions = await client.get(
        f"/api/v1/blocks/{block_id}/revisions",
        headers=admin_headers,
    )
    revision_id = revisions.json()[0]["id"]
    claims = await client.get(
        f"/api/v1/block-revisions/{revision_id}/claims",
        headers=admin_headers,
    )
    assert claims.json()[0]["verification_status"] == "VERIFIED"
    claim_id = claims.json()[0]["id"]

    citations = await client.get(
        f"/api/v1/claims/{claim_id}/citations",
        headers=admin_headers,
    )
    assert len(citations.json()) == 1
    trace = await client.get(
        f"/api/v1/citations/{citations.json()[0]['id']}/trace",
        headers=admin_headers,
    )
    assert trace.json()["fact"]["id"] == fact_id
    assert trace.json()["anchor"]["id"] == anchor_id
    assert trace.json()["document"]["name"] == "employee.xlsx"

    comment = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/comments",
        headers=admin_headers,
        json={"section_id": section_id, "block_id": block_id, "body": "请复核员工口径"},
    )
    assert comment.status_code == 201
    resolved = await client.post(
        f"/api/v1/comments/{comment.json()['id']}/resolve",
        headers=admin_headers,
    )
    assert resolved.json()["status"] == "RESOLVED"

    consistency = await client.post(
        f"/api/v1/reports/{report.json()['id']}/ai/consistency-check",
        headers=admin_headers,
    )
    consistency_task = await client.get(
        f"/api/v1/tasks/{consistency.json()['task_id']}",
        headers=admin_headers,
    )
    assert consistency_task.json()["status"] == "SUCCESS"
    assert consistency_task.json()["result_json"]["issues"] == []

    export = await client.post(
        f"/api/v1/reports/{report.json()['id']}/exports",
        headers=admin_headers,
        json={"format": "DOCX"},
    )
    assert export.status_code == 202, export.text
    export_detail = await client.get(
        f"/api/v1/report-exports/{export.json()['id']}",
        headers=admin_headers,
    )
    assert export_detail.status_code == 200
    assert export_detail.json()["status"] == "SUCCESS"
    assert export_detail.json()["download_url"]

    traces = await client.get(
        f"/api/v1/tasks/{generate.json()['task_id']}/traces",
        headers=admin_headers,
    )
    assert traces.status_code == 200
    assert traces.json()[0]["trace"]["result_status"] == "SUCCESS"
