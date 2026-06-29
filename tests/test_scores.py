"""tests/test_scores.py — /scores route ordering and candidate endpoint."""
import pytest


async def _make_recruiter(client, email="rec_scores@example.com"):
    r = await client.post("/auth/register/recruiter", json={
        "email": email, "password": "password1", "org_name": "ScoreOrg",
    })
    return r.json()["access_token"]


async def _make_candidate(client, email="cand_scores@example.com"):
    r = await client.post("/auth/register/candidate", json={
        "email": email, "password": "password1",
    })
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_candidate_me_scores_empty(client):
    token = await _make_candidate(client)
    r = await client.get("/scores/candidate/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_get_score_not_found(client):
    token = await _make_recruiter(client)
    import uuid
    r = await client.get(
        f"/scores/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_suggest_returns_unscored_resumes(client):
    """suggest endpoint returns resumes not yet scored for a job."""
    rec_token = await _make_recruiter(client)
    rec_headers = {"Authorization": f"Bearer {rec_token}"}

    job_r = await client.post("/jobs", json={"title": "ML Eng", "description": "pytorch nlp"}, headers=rec_headers)
    job_id = job_r.json()["id"]

    r = await client.get(f"/jobs/{job_id}/suggest", headers=rec_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_candidate_scores_route_does_not_conflict_with_score_id(client):
    """GET /scores/candidate/me must resolve before /{score_id} path param."""
    token = await _make_candidate(client)
    r = await client.get("/scores/candidate/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
