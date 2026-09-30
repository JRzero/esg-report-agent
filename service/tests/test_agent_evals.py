from __future__ import annotations

from io import BytesIO
from uuid import UUID, uuid4

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.ai.schemas import (
    ClaimDraft,
    DraftBlock,
    FactCandidate,
    FactExtractionResult,
    SectionDraft,
)
from app.ai.workflows import FactExtractionWorkflow, SectionWritingWorkflow
from app.core.database import SessionLocal
from app.evals.quality import numeric_faithfulness, validate_fact_extraction, validate_section_draft
from app.modules.models import Fact, ReportSection, TenantMembership
from app.modules.schemas import FactCreate
from app.modules.services import FactService
from app.workers.tasks import _process_document
from conftest import login, seed_tenant


async def _create_project(client, headers) -> str:
    company = await client.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "Eval Company"},
    )
    project = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "company_id": company.json()["id"],
            "name": "Eval Project",
            "report_year": 2026,
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
        },
    )
    return project.json()["id"]


def test_fact_grounding_validator_rejects_unknown_anchor():
    allowed = {uuid4()}
    output = FactExtractionResult(
        facts=[
            FactCandidate(
                name="Employee total",
                value_type="NUMBER",
                number_value=1287,
                anchor_ids=[uuid4()],
            )
        ]
    )
    result = validate_fact_extraction(output, allowed)
    assert not result.passed
    assert result.metrics["fact_grounding_precision"] == 0
    assert result.findings[0].code == "UNKNOWN_EVIDENCE_ANCHOR"


def test_section_draft_validator_rejects_missing_fact_reference():
    draft = SectionDraft(
        blocks=[
            DraftBlock(
                content="The Group employed 1,287 people.",
                claims=[
                    ClaimDraft(
                        text="The Group employed 1,287 people.",
                        claim_type="FACTUAL",
                        fact_ids=[],
                    )
                ],
            )
        ]
    )
    result = validate_section_draft(draft, {uuid4()})
    assert not result.passed
    assert result.findings[0].code == "FACTUAL_CLAIM_WITHOUT_FACT"


def test_numeric_faithfulness_rejects_invented_number():
    draft = SectionDraft(
        blocks=[DraftBlock(content="The company delivered 58 training sessions.")]
    )
    result = numeric_faithfulness(draft, [42])
    assert not result.passed
    assert result.findings[0].code == "UNSUPPORTED_NUMBER"


@pytest.mark.asyncio
async def test_fact_extraction_workflow_fails_closed_on_hallucinated_anchor(client):
    await seed_tenant()
    headers = await login(client, "admin@example.com")
    project_id = await _create_project(client, headers)

    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "员工总数"
    sheet["B1"] = 1287
    stream = BytesIO()
    workbook.save(stream)

    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        data={"source_type": "EVIDENCE"},
        files={
            "file": (
                "employees.xlsx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    version_id = upload.json()["version_id"]
    await _process_document(version_id)

    class HallucinatingLLM:
        async def generate_structured(self, system, user, schema, model_profile="STRONG"):
            return FactExtractionResult(
                facts=[
                    FactCandidate(
                        name="Employee total",
                        value_type="NUMBER",
                        number_value=1287,
                        anchor_ids=[uuid4()],
                    )
                ]
            )

    async with SessionLocal() as session:
        membership = await session.scalar(select(TenantMembership))
        with pytest.raises(Exception) as exc:
            await FactExtractionWorkflow(session, HallucinatingLLM()).run(
                membership.tenant_id,
                UUID(project_id),
                membership.user_id,
                UUID(version_id),
            )
        assert getattr(exc.value, "code", None) == "AI_OUTPUT_UNGROUNDED"


@pytest.mark.asyncio
async def test_section_writing_workflow_fails_closed_on_uncited_factual_claim(client):
    tenant_id, user_id, _ = await seed_tenant()
    headers = await login(client, "admin@example.com")
    project_id = await _create_project(client, headers)

    report = await client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers=headers,
        json={"title": "Eval Report"},
    )
    section = await client.post(
        f"/api/v1/reports/{report.json()['id']}/sections",
        headers=headers,
        json={"title": "Employees"},
    )
    section_id = UUID(section.json()["id"])

    async with SessionLocal() as session:
        fact = await FactService(session).create_candidate(
            tenant_id,
            UUID(project_id),
            user_id,
            FactCreate(
                name="Employee total",
                value_type="NUMBER",
                number_value=1287,
                unit="person",
                source_type="HUMAN",
            ),
        )
        await FactService(session).confirm(UUID(project_id), fact.id, user_id)
        report_section = await session.get(ReportSection, section_id)
        report_section.writing_plan = {
            "version": 1,
            "goal": "Describe workforce",
            "fact_ids": [str(fact.id)],
        }
        await session.commit()

    class UngroundedLLM:
        async def generate_structured(self, system, user, schema, model_profile="STRONG"):
            return SectionDraft(
                blocks=[
                    DraftBlock(
                        content="The Group employed 1,287 people.",
                        claims=[
                            ClaimDraft(
                                text="The Group employed 1,287 people.",
                                claim_type="FACTUAL",
                                risk_level="HIGH",
                                fact_ids=[],
                            )
                        ],
                    )
                ]
            )

    async with SessionLocal() as session:
        with pytest.raises(Exception) as exc:
            await SectionWritingWorkflow(session, UngroundedLLM()).run(
                tenant_id,
                UUID(project_id),
                user_id,
                section_id,
            )
        assert getattr(exc.value, "code", None) == "AI_OUTPUT_UNGROUNDED"
        blocks = await session.scalar(
            select(Fact).where(Fact.project_id == UUID(project_id))
        )
        assert blocks is not None
