from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import UUID

import httpx
import pytest
from openpyxl import Workbook
from pydantic import ValidationError
from sqlalchemy import select, update

from app.ai.llm import LLMGateway
from app.ai.openviking import OpenVikingAdapter
from app.ai.schemas import SectionPlan
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.integrations.parsers import parse_plain_text, parse_xlsx
from app.modules.models import (
    AITask,
    ContextBinding,
    DocumentVersion,
    Standard,
)
from app.modules.services import TaskService
from app.workers import tasks
from conftest import login, seed_tenant


async def _create_project(client, headers, name: str = "Project") -> str:
    company = await client.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": f"{name} Company"},
    )
    assert company.status_code == 201, company.text
    project = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "company_id": company.json()["id"],
            "name": name,
            "report_year": 2026,
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
        },
    )
    assert project.status_code == 201, project.text
    return project.json()["id"]


@pytest.mark.asyncio
async def test_same_idempotency_key_is_isolated_by_tenant_and_principal():
    tenant_a, user_a, _ = await seed_tenant(code="tenant-a", email="a@example.com")
    tenant_b, user_b, _ = await seed_tenant(code="tenant-b", email="b@example.com")

    async with SessionLocal() as session:
        first = await TaskService(session).create(
            tenant_a,
            None,
            user_a,
            "SECTION_PLANNING",
            "SECTION",
            None,
            idempotency_key="same-key",
        )
        await session.commit()
        first_id = first.id

    async with SessionLocal() as session:
        second = await TaskService(session).create(
            tenant_b,
            None,
            user_b,
            "SECTION_PLANNING",
            "SECTION",
            None,
            idempotency_key="same-key",
        )
        await session.commit()
        second_id = second.id

    assert first_id != second_id


@pytest.mark.asyncio
async def test_concurrent_idempotent_submission_creates_one_task():
    tenant_id, user_id, _ = await seed_tenant()

    async def submit() -> UUID:
        async with SessionLocal() as session:
            task = await TaskService(session).create(
                tenant_id,
                None,
                user_id,
                "SECTION_PLANNING",
                "SECTION",
                None,
                idempotency_key="concurrent-key",
            )
            await session.commit()
            return task.id

    task_ids = await asyncio.gather(*(submit() for _ in range(20)))
    assert len(set(task_ids)) == 1

    async with SessionLocal() as session:
        rows = list(
            (
                await session.scalars(
                    select(AITask).where(
                        AITask.tenant_id == tenant_id,
                        AITask.created_by == user_id,
                        AITask.idempotency_key == "concurrent-key",
                    )
                )
            ).all()
        )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_idempotency_key_reuse_with_different_request_is_rejected():
    tenant_id, user_id, _ = await seed_tenant()

    async with SessionLocal() as session:
        await TaskService(session).create(
            tenant_id,
            None,
            user_id,
            "SECTION_PLANNING",
            "SECTION",
            None,
            idempotency_key="reuse-key",
        )
        await session.commit()

    async with SessionLocal() as session:
        with pytest.raises(Exception) as exc:
            await TaskService(session).create(
                tenant_id,
                None,
                user_id,
                "SECTION_WRITING",
                "SECTION",
                None,
                idempotency_key="reuse-key",
            )
        assert getattr(exc.value, "code", None) == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.asyncio
async def test_duplicate_worker_delivery_executes_ai_workflow_once(monkeypatch):
    tenant_id, user_id, _ = await seed_tenant()
    calls = 0

    class FakePlanningWorkflow:
        def __init__(self, session):
            self.session = session

        async def run(self, project_id, target_id):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.05)
            return {"version": 1}

    monkeypatch.setattr(tasks, "SectionPlanningWorkflow", FakePlanningWorkflow)

    async with SessionLocal() as session:
        task = AITask(
            tenant_id=tenant_id,
            project_id=None,
            created_by=user_id,
            task_type="SECTION_PLANNING",
            target_type="SECTION",
            status="PENDING",
        )
        session.add(task)
        await session.commit()
        task_id = str(task.id)

    await asyncio.gather(tasks._run_ai_task(task_id), tasks._run_ai_task(task_id))

    async with SessionLocal() as session:
        saved = await session.get(AITask, UUID(task_id))
        assert saved.status == "SUCCESS"
    assert calls == 1


@pytest.mark.asyncio
async def test_cancelled_running_task_rolls_back_uncommitted_writes(monkeypatch):
    tenant_id, user_id, _ = await seed_tenant()
    started = asyncio.Event()
    resume = asyncio.Event()

    class SlowPlanningWorkflow:
        def __init__(self, session):
            self.session = session

        async def run(self, project_id, target_id):
            self.session.add(Standard(code="SHOULD_ROLLBACK", name="Rollback marker"))
            await self.session.flush()
            started.set()
            await resume.wait()
            return {"version": 1}

    monkeypatch.setattr(tasks, "SectionPlanningWorkflow", SlowPlanningWorkflow)

    async with SessionLocal() as session:
        task = AITask(
            tenant_id=tenant_id,
            project_id=None,
            created_by=user_id,
            task_type="SECTION_PLANNING",
            target_type="SECTION",
            status="PENDING",
        )
        session.add(task)
        await session.commit()
        task_id = task.id

    worker = asyncio.create_task(tasks._run_ai_task(str(task_id)))
    await asyncio.wait_for(started.wait(), timeout=2)

    async with SessionLocal() as session:
        await session.execute(
            update(AITask)
            .where(AITask.id == task_id, AITask.status == "RUNNING")
            .values(
                status="CANCELLED",
                stage="cancelled",
                completed_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    resume.set()
    await worker

    async with SessionLocal() as session:
        saved = await session.get(AITask, task_id)
        marker = await session.scalar(select(Standard).where(Standard.code == "SHOULD_ROLLBACK"))
        assert saved.status == "CANCELLED"
        assert marker is None


@pytest.mark.asyncio
async def test_stale_running_task_is_recovered():
    settings = get_settings()
    settings.task_stale_after_seconds = 60
    tenant_id, user_id, _ = await seed_tenant()

    async with SessionLocal() as session:
        task = AITask(
            tenant_id=tenant_id,
            project_id=None,
            created_by=user_id,
            task_type="SECTION_PLANNING",
            status="RUNNING",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        session.add(task)
        await session.commit()
        task_id = task.id

    result = await tasks._recover_stale_work()
    assert result["tasks"] == 1

    async with SessionLocal() as session:
        saved = await session.get(AITask, task_id)
        assert saved.status == "FAILED"
        assert saved.error_code == "TASK_STALE_RECOVERED"


@pytest.mark.asyncio
async def test_duplicate_document_delivery_parses_once(client):
    await seed_tenant()
    headers = await login(client, "admin@example.com")
    project_id = await _create_project(client, headers)
    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        data={"source_type": "EVIDENCE"},
        files={"file": ("evidence.txt", b"employee total: 1287", "text/plain")},
    )
    version_id = upload.json()["version_id"]

    await asyncio.gather(
        tasks._process_document(version_id),
        tasks._process_document(version_id),
    )

    anchors = await client.get(
        f"/api/v1/document-versions/{version_id}/anchors",
        headers=headers,
    )
    assert anchors.status_code == 200
    assert len(anchors.json()) == 1


@pytest.mark.asyncio
async def test_openviking_uri_is_tenant_and_project_scoped(client, monkeypatch):
    tenant_id, _, _ = await seed_tenant()
    headers = await login(client, "admin@example.com")
    project_id = await _create_project(client, headers)
    captured: dict[str, str] = {}

    class FakeOpenViking:
        enabled = True

        async def add_bytes(self, filename, data, to_uri, reason=""):
            captured["uri"] = to_uri
            return {"status": "success", "root_uri": to_uri}

    monkeypatch.setattr(tasks, "OpenVikingAdapter", FakeOpenViking)

    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        data={"source_type": "EVIDENCE"},
        files={"file": ("evidence.txt", b"hello", "text/plain")},
    )
    await tasks._process_document(upload.json()["version_id"])

    assert f"/tenants/{tenant_id}/projects/{project_id}/" in captured["uri"]


@pytest.mark.asyncio
async def test_openviking_failure_does_not_destroy_parsed_evidence(client, monkeypatch):
    await seed_tenant()
    headers = await login(client, "admin@example.com")
    project_id = await _create_project(client, headers)

    class FailingOpenViking:
        enabled = True

        async def add_bytes(self, filename, data, to_uri, reason=""):
            raise httpx.ConnectError("context unavailable")

    monkeypatch.setattr(tasks, "OpenVikingAdapter", FailingOpenViking)

    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        data={"source_type": "EVIDENCE"},
        files={"file": ("evidence.txt", b"hello", "text/plain")},
    )
    version_id = upload.json()["version_id"]
    await tasks._process_document(version_id)

    async with SessionLocal() as session:
        version = await session.get(DocumentVersion, UUID(version_id))
        binding = await session.scalar(
            select(ContextBinding).where(ContextBinding.resource_id == UUID(version_id))
        )
        assert version.evidence_parse_status == "READY"
        assert version.context_status == "FAILED"
        assert binding.processing_status == "FAILED"


@pytest.mark.asyncio
async def test_openviking_reconciliation_marks_completed_import_ready(client, monkeypatch):
    settings = get_settings()
    settings.openviking_enabled = False
    await seed_tenant()
    headers = await login(client, "admin@example.com")
    project_id = await _create_project(client, headers)

    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        data={"source_type": "EVIDENCE"},
        files={"file": ("evidence.txt", b"hello", "text/plain")},
    )
    version_id = UUID(upload.json()["version_id"])
    await tasks._process_document(str(version_id))

    async with SessionLocal() as session:
        binding = await session.scalar(
            select(ContextBinding).where(ContextBinding.resource_id == version_id)
        )
        version = await session.get(DocumentVersion, version_id)
        binding.processing_status = "PROCESSING"
        binding.external_task_id = "task-1"
        version.context_status = "PROCESSING"
        await session.commit()

    settings.openviking_enabled = True

    class FakeAdapter:
        enabled = True

        async def get_task(self, task_id):
            assert task_id == "task-1"
            return {"status": "completed", "result": {"context_count": 1}}

    monkeypatch.setattr(tasks, "OpenVikingAdapter", FakeAdapter)
    result = await tasks._reconcile_context_bindings()
    assert result == {"checked": 1, "updated": 1}

    async with SessionLocal() as session:
        binding = await session.scalar(
            select(ContextBinding).where(ContextBinding.resource_id == version_id)
        )
        version = await session.get(DocumentVersion, version_id)
        assert binding.processing_status == "READY"
        assert binding.metadata_json["external_result"]["context_count"] == 1
        assert version.context_status == "READY"


def test_parser_anchor_limit_is_enforced():
    with pytest.raises(ValueError, match="maximum anchor count"):
        parse_plain_text(b"a\nb\nc\n", max_anchors=2, max_text_chars=100)


def test_parser_text_limit_is_enforced():
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "abcdefghijk"
    stream = BytesIO()
    workbook.save(stream)
    with pytest.raises(ValueError, match="maximum extracted text size"):
        parse_xlsx(stream.getvalue(), max_anchors=10, max_text_chars=5)


@pytest.mark.asyncio
async def test_upload_size_limit_is_enforced_before_full_acceptance(client):
    settings = get_settings()
    settings.max_upload_bytes = 10
    await seed_tenant()
    headers = await login(client, "admin@example.com")
    project_id = await _create_project(client, headers)
    response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        data={"source_type": "EVIDENCE"},
        files={"file": ("large.txt", b"x" * 100, "text/plain")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_production_config_rejects_unsafe_secret():
    with pytest.raises(ValidationError):
        Settings(app_env="production", jwt_secret="short")


@pytest.mark.asyncio
async def test_security_headers_are_present(client):
    response = await client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_llm_retries_transient_503(monkeypatch):
    settings = get_settings()
    settings.llm_base_url = "http://llm.test/v1"
    settings.llm_model = "test"
    settings.llm_max_retries = 2
    settings.llm_retry_base_seconds = 0
    calls = 0

    async def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503, request=request, json={"error": "busy"})
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": '{"goal":"ok"}'}}]},
        )

    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: original(transport=transport, **kwargs),
    )
    result = await LLMGateway().generate_structured("system", "user", SectionPlan)
    assert result.goal == "ok"
    assert calls == 3


@pytest.mark.asyncio
async def test_llm_does_not_retry_permanent_400(monkeypatch):
    settings = get_settings()
    settings.llm_base_url = "http://llm.test/v1"
    settings.llm_model = "test"
    settings.llm_max_retries = 3
    settings.llm_retry_base_seconds = 0
    calls = 0

    async def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(400, request=request, json={"error": "bad request"})

    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: original(transport=transport, **kwargs),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await LLMGateway().generate_structured("system", "user", SectionPlan)
    assert calls == 1
