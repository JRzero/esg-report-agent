from io import BytesIO

import pytest
from openpyxl import Workbook


def workbook_bytes(value: int = 1287) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "员工统计"
    sheet["A1"] = "员工总人数"
    sheet["B1"] = value
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


async def upload_sheet(client, headers, project_id, source_type="EVIDENCE", value=1287):
    response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        data={"source_type": source_type, "category_code": "employee"},
        files={
            "file": (
                "employee.xlsx",
                workbook_bytes(value),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_document_anchor_fact_evidence_trace(client, seeded, admin_headers):
    uploaded = await upload_sheet(
        client, admin_headers, seeded["project"].id, source_type="EVIDENCE"
    )
    version_id = uploaded["version_id"]

    anchors = await client.get(
        f"/api/v1/document-versions/{version_id}/anchors",
        headers=admin_headers,
    )
    assert anchors.status_code == 200, anchors.text
    employee_count = next(item for item in anchors.json() if item["cell_range"] == "B1")
    assert employee_count["raw_text"] == "1287"

    fact = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/facts",
        headers=admin_headers,
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
            "anchor_ids": [employee_count["id"]],
            "source_type": "AI",
        },
    )
    assert fact.status_code == 201, fact.text
    fact_id = fact.json()["id"]

    confirm = await client.post(
        f"/api/v1/facts/{fact_id}/confirm",
        headers=admin_headers,
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "CONFIRMED"

    evidence = await client.get(
        f"/api/v1/facts/{fact_id}/evidence",
        headers=admin_headers,
    )
    assert evidence.status_code == 200
    assert evidence.json()[0]["anchor"]["cell"] == "B1"
    assert evidence.json()[0]["document"]["name"] == "employee.xlsx"

    revisions = await client.get(
        f"/api/v1/facts/{fact_id}/revisions",
        headers=admin_headers,
    )
    assert [item["change_type"] for item in revisions.json()] == [
        "CONFIRMED",
        "AI_CREATED",
    ]


@pytest.mark.asyncio
async def test_reference_document_cannot_establish_client_fact(
    client,
    seeded,
    admin_headers,
):
    uploaded = await upload_sheet(
        client,
        admin_headers,
        seeded["project"].id,
        source_type="REFERENCE",
        value=9999,
    )
    anchors = await client.get(
        f"/api/v1/document-versions/{uploaded['version_id']}/anchors",
        headers=admin_headers,
    )
    reference_anchor = next(item for item in anchors.json() if item["cell_range"] == "B1")

    fact = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/facts",
        headers=admin_headers,
        json={
            "fact_type": "METRIC",
            "metric_code": "EMPLOYEE_TOTAL",
            "name": "员工总人数",
            "value_type": "NUMBER",
            "number_value": 9999,
            "anchor_ids": [reference_anchor["id"]],
            "source_type": "AI",
        },
    )
    assert fact.status_code == 422
    assert fact.json()["error"]["code"] == "DOCUMENT_NOT_FACT_EVIDENCE"


@pytest.mark.asyncio
async def test_fact_conflict_detection_and_resolution(client, seeded, admin_headers):
    payload = {
        "fact_type": "METRIC",
        "metric_code": "EMPLOYEE_TOTAL",
        "name": "员工总人数",
        "value_type": "NUMBER",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "entity_scope": "GROUP",
        "source_type": "HUMAN",
    }
    first = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/facts",
        headers=admin_headers,
        json={**payload, "number_value": 1287},
    )
    second = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/facts",
        headers=admin_headers,
        json={**payload, "number_value": 1293},
    )
    assert first.status_code == 201 and second.status_code == 201

    conflicts = await client.get(
        f"/api/v1/projects/{seeded['project'].id}/fact-conflicts",
        headers=admin_headers,
    )
    assert conflicts.status_code == 200
    assert len(conflicts.json()) == 1
    group_id = conflicts.json()[0]["id"]

    resolution = await client.post(
        f"/api/v1/fact-conflicts/{group_id}/resolve",
        headers=admin_headers,
        params={"fact_id": second.json()["id"]},
    )
    assert resolution.status_code == 200, resolution.text

    selected = await client.get(
        f"/api/v1/facts/{second.json()['id']}",
        headers=admin_headers,
    )
    rejected = await client.get(
        f"/api/v1/facts/{first.json()['id']}",
        headers=admin_headers,
    )
    assert selected.json()["status"] == "CONFIRMED"
    assert rejected.json()["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_document_version_and_download(client, seeded, admin_headers):
    uploaded = await upload_sheet(client, admin_headers, seeded["project"].id)
    document_id = uploaded["document_id"]

    new_version = await client.post(
        f"/api/v1/documents/{document_id}/versions",
        headers=admin_headers,
        files={
            "file": (
                "employee-v2.xlsx",
                workbook_bytes(1300),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert new_version.status_code == 201, new_version.text
    version_id = new_version.json()["version"]["id"]

    versions = await client.get(
        f"/api/v1/documents/{document_id}/versions",
        headers=admin_headers,
    )
    assert [item["version_no"] for item in versions.json()] == [2, 1]

    download = await client.get(
        f"/api/v1/document-versions/{version_id}/download",
        headers=admin_headers,
    )
    assert download.status_code == 200
    assert download.json()["download_url"]
