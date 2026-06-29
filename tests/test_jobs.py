"""tests/test_jobs.py — /jobs CRUD endpoints."""
import pytest


async def _recruiter_token(client) -> str:
    r = await client.post("/auth/register/recruiter", json={
        "email": "rec_jobs@example.com",
        "password": "password1",
        "org_name": "Jobs Test Org",
    })
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_create_job(client):
    token = await _recruiter_token(client)
    r = await client.post(
        "/jobs",
        json={"title": "ML Engineer", "description": "pytorch nlp experience required"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    assert r.json()["title"] == "ML Engineer"
    assert "id" in r.json()


@pytest.mark.asyncio
async def test_list_jobs(client):
    token = await _recruiter_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/jobs", json={"title": "A", "description": "desc"}, headers=headers)
    await client.post("/jobs", json={"title": "B", "description": "desc"}, headers=headers)
    r = await client.get("/jobs", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2


@pytest.mark.asyncio
async def test_get_job(client):
    token = await _recruiter_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_r = await client.post(
        "/jobs", json={"title": "Get Me", "description": "desc"}, headers=headers
    )
    job_id = create_r.json()["id"]
    r = await client.get(f"/jobs/{job_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["description"] == "desc"


@pytest.mark.asyncio
async def test_candidate_cannot_create_job(client):
    r = await client.post("/auth/register/candidate", json={
        "email": "cand_jobs@example.com",
        "password": "password1",
    })
    token = r.json()["access_token"]
    r2 = await client.post(
        "/jobs",
        json={"title": "Hack", "description": "nope"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_rank_returns_empty_before_scoring(client):
    token = await _recruiter_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_r = await client.post(
        "/jobs", json={"title": "Rank Test", "description": "desc"}, headers=headers
    )
    job_id = create_r.json()["id"]
    r = await client.get(f"/jobs/{job_id}/rank", headers=headers)
    assert r.status_code == 200
    assert r.json() == []
