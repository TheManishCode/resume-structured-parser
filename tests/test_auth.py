"""tests/test_auth.py — /auth/register/* and /auth/login endpoints."""
import pytest


@pytest.mark.asyncio
async def test_register_recruiter(client):
    r = await client.post("/auth/register/recruiter", json={
        "email": "rec@example.com",
        "password": "secret123",
        "org_name": "Acme Corp",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["role"] == "recruiter"
    assert "access_token" in data


@pytest.mark.asyncio
async def test_register_candidate(client):
    r = await client.post("/auth/register/candidate", json={
        "email": "cand@example.com",
        "password": "secret123",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["role"] == "candidate"
    assert "access_token" in data


@pytest.mark.asyncio
async def test_duplicate_recruiter_rejected(client):
    payload = {"email": "dup@example.com", "password": "pw", "org_name": "X"}
    await client.post("/auth/register/recruiter", json=payload)
    r = await client.post("/auth/register/recruiter", json=payload)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_login_recruiter(client):
    await client.post("/auth/register/recruiter", json={
        "email": "login_rec@example.com",
        "password": "mypassword",
        "org_name": "TestOrg",
    })
    r = await client.post("/auth/login", json={
        "email": "login_rec@example.com",
        "password": "mypassword",
        "role": "recruiter",
    })
    assert r.status_code == 200
    assert r.json()["role"] == "recruiter"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/auth/register/candidate", json={
        "email": "wp@example.com",
        "password": "correct",
    })
    r = await client.post("/auth/login", json={
        "email": "wp@example.com",
        "password": "wrong",
        "role": "candidate",
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_route_rejected(client):
    r = await client.get("/jobs")
    assert r.status_code in (401, 403)
