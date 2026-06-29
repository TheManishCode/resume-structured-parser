"""
packages/api/routers/auth.py

/auth/register/recruiter  — POST
/auth/register/candidate  — POST
/auth/login               — POST → JWT

Rate limits (per IP):
  register: 10/minute  — prevents account-farming
  login:    20/minute  — prevents credential stuffing
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from fastapi import APIRouter, HTTPException, Request, status
from jose import jwt
from pydantic import BaseModel, EmailStr, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select

from packages.api.deps import DbSession
from packages.core.db.models import Candidate, Recruiter

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)

JWT_SECRET    = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE  = int(os.getenv("JWT_EXPIRE_HOURS", "48"))

_MIN_PASSWORD_LEN = 8


def _hash(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt(rounds=12)).decode()


def _verify(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


def _make_token(sub: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE)
    return jwt.encode({"sub": sub, "role": role, "exp": exp}, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ── Schemas ───────────────────────────────────────────────────────────────────

class RecruiterRegister(BaseModel):
    email:    EmailStr
    password: str
    org_name: str

    @field_validator("password")
    @classmethod
    def _pw_length(cls, v: str) -> str:
        if len(v) < _MIN_PASSWORD_LEN:
            raise ValueError(f"Password must be at least {_MIN_PASSWORD_LEN} characters")
        return v

    @field_validator("org_name")
    @classmethod
    def _org_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("org_name cannot be blank")
        return v.strip()


class CandidateRegister(BaseModel):
    email:    EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _pw_length(cls, v: str) -> str:
        if len(v) < _MIN_PASSWORD_LEN:
            raise ValueError(f"Password must be at least {_MIN_PASSWORD_LEN} characters")
        return v


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str
    role:     str

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        if v not in ("recruiter", "candidate"):
            raise ValueError("role must be 'recruiter' or 'candidate'")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    role:         str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register/recruiter", response_model=TokenResponse, status_code=201)
@_limiter.limit("10/minute")
async def register_recruiter(request: Request, body: RecruiterRegister, db: DbSession):
    existing = await db.scalar(select(Recruiter).where(Recruiter.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    rec = Recruiter(
        email=body.email,
        org_name=body.org_name,
        hashed_pw=_hash(body.password),
    )
    db.add(rec)
    await db.flush()
    return TokenResponse(access_token=_make_token(str(rec.id), "recruiter"), role="recruiter")


@router.post("/register/candidate", response_model=TokenResponse, status_code=201)
@_limiter.limit("10/minute")
async def register_candidate(request: Request, body: CandidateRegister, db: DbSession):
    existing = await db.scalar(select(Candidate).where(Candidate.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    cand = Candidate(email=body.email, hashed_pw=_hash(body.password))
    db.add(cand)
    await db.flush()
    return TokenResponse(access_token=_make_token(str(cand.id), "candidate"), role="candidate")


@router.post("/login", response_model=TokenResponse)
@_limiter.limit("20/minute")
async def login(request: Request, body: LoginRequest, db: DbSession):
    if body.role == "recruiter":
        user = await db.scalar(select(Recruiter).where(Recruiter.email == body.email))
    else:
        user = await db.scalar(select(Candidate).where(Candidate.email == body.email))

    if not user or not _verify(body.password, user.hashed_pw):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return TokenResponse(
        access_token=_make_token(str(user.id), body.role),
        role=body.role,
    )
