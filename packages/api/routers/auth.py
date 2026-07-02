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
    email:          EmailStr
    password:       str
    org_name:       str
    name:           str | None = None
    company_website: str | None = None
    hiring_role:    str | None = None
    hiring_domains: list[str] | None = None
    company_size:   str | None = None

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
    email:           EmailStr
    password:        str
    name:            str | None = None
    phone:           str | None = None
    location:        str | None = None
    target_roles:    list[str] | None = None
    experience_level: str | None = None
    job_type_pref:   list[str] | None = None
    skills:          list[str] | None = None

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
    access_token:    str
    token_type:      str = "bearer"
    role:            str
    user_id:         str
    email:           str
    name:            str | None = None
    onboarding_done: bool = False


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
        name=body.name,
        company_website=body.company_website,
        hiring_role=body.hiring_role,
        hiring_domains=body.hiring_domains,
        company_size=body.company_size,
        onboarding_done=bool(body.name and body.hiring_role),
    )
    db.add(rec)
    await db.flush()
    return TokenResponse(
        access_token=_make_token(str(rec.id), "recruiter"),
        role="recruiter",
        user_id=str(rec.id),
        email=rec.email,
        name=rec.name,
        onboarding_done=rec.onboarding_done,
    )


@router.post("/register/candidate", response_model=TokenResponse, status_code=201)
@_limiter.limit("10/minute")
async def register_candidate(request: Request, body: CandidateRegister, db: DbSession):
    existing = await db.scalar(select(Candidate).where(Candidate.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    cand = Candidate(
        email=body.email,
        hashed_pw=_hash(body.password),
        name=body.name,
        phone=body.phone,
        location=body.location,
        target_roles=body.target_roles,
        experience_level=body.experience_level,
        job_type_pref=body.job_type_pref,
        skills=body.skills,
        onboarding_done=bool(body.name and body.skills),
    )
    db.add(cand)
    await db.flush()
    return TokenResponse(
        access_token=_make_token(str(cand.id), "candidate"),
        role="candidate",
        user_id=str(cand.id),
        email=cand.email,
        name=cand.name,
        onboarding_done=cand.onboarding_done,
    )


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
        user_id=str(user.id),
        email=user.email,
        name=getattr(user, "name", None),
        onboarding_done=getattr(user, "onboarding_done", False),
    )


@router.post("/forgot-password")
async def forgot_password(email: str, db: DbSession):
    """Placeholder for email verification flow — structure ready for SMTP integration."""
    return {"message": "If that email exists, a reset link has been sent."}
