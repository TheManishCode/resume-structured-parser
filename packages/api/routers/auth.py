"""
packages/api/routers/auth.py

/auth/register  — POST (recruiter or candidate)
/auth/login     — POST → JWT
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from packages.api.deps import DbSession
from packages.core.db.models import Candidate, Recruiter

router = APIRouter()

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET    = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE  = int(os.getenv("JWT_EXPIRE_HOURS", "48"))


def _make_token(sub: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE)
    return jwt.encode({"sub": sub, "role": role, "exp": exp}, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ── Schemas ───────────────────────────────────────────────────────────────────

class RecruiterRegister(BaseModel):
    email:    EmailStr
    password: str
    org_name: str


class CandidateRegister(BaseModel):
    email:    EmailStr
    password: str


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str
    role:     str  # "recruiter" | "candidate"


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    role:         str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register/recruiter", response_model=TokenResponse, status_code=201)
async def register_recruiter(body: RecruiterRegister, db: DbSession):
    existing = await db.scalar(select(Recruiter).where(Recruiter.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    rec = Recruiter(
        email=body.email,
        org_name=body.org_name,
        hashed_pw=_pwd.hash(body.password),
    )
    db.add(rec)
    await db.flush()
    return TokenResponse(access_token=_make_token(str(rec.id), "recruiter"), role="recruiter")


@router.post("/register/candidate", response_model=TokenResponse, status_code=201)
async def register_candidate(body: CandidateRegister, db: DbSession):
    existing = await db.scalar(select(Candidate).where(Candidate.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    cand = Candidate(email=body.email, hashed_pw=_pwd.hash(body.password))
    db.add(cand)
    await db.flush()
    return TokenResponse(access_token=_make_token(str(cand.id), "candidate"), role="candidate")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DbSession):
    if body.role == "recruiter":
        user = await db.scalar(select(Recruiter).where(Recruiter.email == body.email))
    else:
        user = await db.scalar(select(Candidate).where(Candidate.email == body.email))

    if not user or not _pwd.verify(body.password, user.hashed_pw):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return TokenResponse(
        access_token=_make_token(str(user.id), body.role),
        role=body.role,
    )
