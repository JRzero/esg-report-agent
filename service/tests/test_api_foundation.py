import pytest

from app.modules.models import ProjectMember


@pytest.mark.asyncio
async def test_auth_company_project_and_membership_boundaries(
    client,
    seeded,
    admin_headers,
    client_headers,
):
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    assert me.json()["membership"]["member_type"] == "INTERNAL"

    # Client tenant memberships only see their own company.
    companies = await client.get("/api/v1/companies", headers=client_headers)
    assert companies.status_code == 200
    assert [item["id"] for item in companies.json()] == [str(seeded["company"].id)]

    hidden_company = await client.get(
        f"/api/v1/companies/{seeded['other_company'].id}",
        headers=client_headers,
    )
    assert hidden_company.status_code == 404

    client_project_create = await client.post(
        "/api/v1/projects",
        headers=client_headers,
        json={
            "company_id": str(seeded["company"].id),
            "name": "Client-created project",
            "report_year": 2026,
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
        },
    )
    assert client_project_create.status_code == 403

    # Add an internal editor to the project, then transfer ownership.
    add_editor = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/members",
        headers=admin_headers,
        json={
            "membership_id": str(seeded["editor_membership"].id),
            "project_role": "EDITOR",
        },
    )
    assert add_editor.status_code == 201, add_editor.text

    transfer = await client.post(
        f"/api/v1/projects/{seeded['project'].id}/transfer-owner",
        headers=admin_headers,
        json={"membership_id": str(seeded["editor_membership"].id)},
    )
    assert transfer.status_code == 200, transfer.text
    assert transfer.json()["project_role"] == "OWNER"

    # A client from company A cannot be added to a company B project.
    mismatch = await client.post(
        f"/api/v1/projects/{seeded['other_project'].id}/members",
        headers=admin_headers,
        json={
            "membership_id": str(seeded["client_membership"].id),
            "project_role": "CLIENT_MEMBER",
        },
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "CLIENT_COMPANY_MISMATCH"


@pytest.mark.asyncio
async def test_company_delete_is_blocked_by_active_project(client, seeded, admin_headers):
    response = await client.delete(
        f"/api/v1/companies/{seeded['company'].id}",
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "COMPANY_HAS_ACTIVE_PROJECTS"


@pytest.mark.asyncio
async def test_tenant_admin_cannot_deactivate_last_admin(client, seeded, admin_headers):
    response = await client.delete(
        f"/api/v1/tenant/members/{seeded['admin_membership'].id}",
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LAST_TENANT_ADMIN"
