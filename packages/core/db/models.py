"""
packages/core/db/models.py

SQLAlchemy 2.x ORM models for the two-sided platform.

Tables:
  recruiters      — org accounts with per-org API cost caps
  candidates      — job-seeker accounts
  jobs            — roles posted by recruiters
  resumes         — parsed resume blobs; expires_at = upload + 6 months (DPDP)
  scores          — one row per (resume, job) scoring event; keeps history
  resume_job_tags — many-to-many: a resume can be tagged to multiple roles
  audit_log       — immutable log of every score / model-switch event
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Enum as SAEnum,
    Float, ForeignKey, Integer, String, Text, UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


def _six_months_from_now() -> date:
    return (datetime.now(timezone.utc) + timedelta(days=183)).date()


class Base(DeclarativeBase):
    pass


# ── Recruiters ────────────────────────────────────────────────────────────────

class Recruiter(Base):
    __tablename__ = "recruiters"

    id            = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email         = Column(String(255), nullable=False, unique=True, index=True)
    org_name      = Column(String(255), nullable=False)
    hashed_pw     = Column(String(255), nullable=False)
    is_active     = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime(timezone=True), nullable=False, default=_now)

    # Profile fields
    name            = Column(String(255), nullable=True)
    company_website = Column(String(512), nullable=True)
    hiring_role     = Column(String(128), nullable=True)
    hiring_domains  = Column(JSONB, nullable=True)   # ["Engineering", "Product", ...]
    company_size    = Column(String(32), nullable=True)  # "1-10"|"11-50"|"51-200"|etc.
    onboarding_done = Column(Boolean, nullable=False, default=False)

    # Cost guardrail: cloud-model calls per org per day
    daily_cloud_cap   = Column(Integer, nullable=False, default=200)
    cloud_calls_today = Column(Integer, nullable=False, default=0)
    cap_reset_date    = Column(Date, nullable=True)

    jobs    = relationship("Job", back_populates="recruiter", cascade="all, delete-orphan")


# ── Candidates ────────────────────────────────────────────────────────────────

class Candidate(Base):
    __tablename__ = "candidates"

    id               = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email            = Column(String(255), nullable=False, unique=True, index=True)
    hashed_pw        = Column(String(255), nullable=False)
    is_active        = Column(Boolean, nullable=False, default=True)
    created_at       = Column(DateTime(timezone=True), nullable=False, default=_now)

    # Profile fields
    name             = Column(String(255), nullable=True)
    phone            = Column(String(32), nullable=True)
    location         = Column(String(255), nullable=True)
    target_roles     = Column(JSONB, nullable=True)      # ["Software Engineer", ...]
    experience_level = Column(String(32), nullable=True)  # entry|mid|senior|lead|exec
    job_type_pref    = Column(JSONB, nullable=True)      # ["full-time", "remote", ...]
    skills           = Column(JSONB, nullable=True)      # ["Python", "FastAPI", ...]
    visibility       = Column(Boolean, nullable=False, default=True)
    onboarding_done  = Column(Boolean, nullable=False, default=False)

    resumes = relationship("Resume", back_populates="candidate", cascade="all, delete-orphan")
    analyses = relationship("AnalysisHistory", back_populates="candidate", cascade="all, delete-orphan")


# ── Jobs ──────────────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    recruiter_id   = Column(UUID(as_uuid=False), ForeignKey("recruiters.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    title          = Column(String(255), nullable=False)
    description    = Column(Text, nullable=False)
    is_active      = Column(Boolean, nullable=False, default=True)
    created_at     = Column(DateTime(timezone=True), nullable=False, default=_now)

    recruiter      = relationship("Recruiter", back_populates="jobs")
    scores         = relationship("Score", back_populates="job")
    resume_tags    = relationship("ResumeJobTag", back_populates="job")


# ── Resumes ───────────────────────────────────────────────────────────────────

class Resume(Base):
    __tablename__ = "resumes"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    candidate_id   = Column(UUID(as_uuid=False), ForeignKey("candidates.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    # Original filename (display only; never used in scoring)
    original_name  = Column(String(512), nullable=True)
    # Normalized JSON blob (the shared schema) — bias fields stripped at ingest
    parsed_json    = Column(JSONB, nullable=False)
    # Full extracted text for router.score()
    text_content   = Column(Text, nullable=False)
    # OCR flag
    used_ocr       = Column(Boolean, nullable=False, default=False)

    # DPDP data-minimisation: auto-expire 6 months after upload
    uploaded_at    = Column(DateTime(timezone=True), nullable=False, default=_now)
    expires_at     = Column(Date, nullable=False, default=_six_months_from_now)
    is_expired     = Column(Boolean, nullable=False, default=False)

    candidate      = relationship("Candidate", back_populates="resumes")
    scores         = relationship("Score", back_populates="resume")
    job_tags       = relationship("ResumeJobTag", back_populates="resume")


# ── Scores ────────────────────────────────────────────────────────────────────

_ScoredBy = SAEnum("local", "claude", "groq", "fallback", name="scored_by_enum")
_Status   = SAEnum("provisional", "confirmed", "re_scored", name="status_enum")


class Score(Base):
    __tablename__ = "scores"

    id                  = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    resume_id           = Column(UUID(as_uuid=False), ForeignKey("resumes.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
    job_id              = Column(UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"),
                                 nullable=False, index=True)

    score               = Column(Float, nullable=False)
    local_score         = Column(Float, nullable=True)
    cloud_score         = Column(Float, nullable=True)
    justification       = Column(Text, nullable=True)

    scored_by           = Column(_ScoredBy, nullable=False)
    status              = Column(_Status, nullable=False, default="provisional")

    # Populated when a re-score changes the value
    previous_score      = Column(Float, nullable=True)

    needs_review        = Column(Boolean, nullable=False, default=False)
    disagreement_delta  = Column(Float, nullable=True)

    local_confidence    = Column(Float, nullable=True)
    latency_ms          = Column(Float, nullable=True)
    scored_at           = Column(DateTime(timezone=True), nullable=False, default=_now)

    resume = relationship("Resume", back_populates="scores")
    job    = relationship("Job",    back_populates="scores")

    __table_args__ = (
        UniqueConstraint("resume_id", "job_id", name="uq_score_resume_job"),
    )


# ── Resume ↔ Job tags (many-to-many) ─────────────────────────────────────────

class ResumeJobTag(Base):
    """Tags a resume to a specific job pool (for pool-scoped RAG retrieval)."""
    __tablename__ = "resume_job_tags"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    resume_id  = Column(UUID(as_uuid=False), ForeignKey("resumes.id", ondelete="CASCADE"),
                        nullable=False)
    job_id     = Column(UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"),
                        nullable=False)
    tagged_at  = Column(DateTime(timezone=True), nullable=False, default=_now)

    resume = relationship("Resume", back_populates="job_tags")
    job    = relationship("Job",    back_populates="resume_tags")

    __table_args__ = (
        UniqueConstraint("resume_id", "job_id", name="uq_tag_resume_job"),
    )


# ── Audit log (immutable) ─────────────────────────────────────────────────────

class AuditLog(Base):
    """Append-only log of every scoring event, model switch, and status change.

    Rows are never updated or deleted (enforced at DB level via a trigger
    — see alembic migration for the DDL).
    """
    __tablename__ = "audit_log"

    id           = Column(BigInteger, primary_key=True, autoincrement=True)
    event_type   = Column(String(64), nullable=False)   # e.g. "score.created", "score.re_scored"
    actor_id     = Column(UUID(as_uuid=False), nullable=True)   # recruiter or candidate UUID
    actor_role   = Column(String(32), nullable=True)            # "recruiter" | "candidate" | "system"
    entity_id    = Column(UUID(as_uuid=False), nullable=True)   # score / resume / job UUID
    entity_type  = Column(String(64), nullable=True)
    payload      = Column(JSONB, nullable=True)                 # arbitrary detail blob
    model_used   = Column(String(64), nullable=True)
    occurred_at  = Column(DateTime(timezone=True), nullable=False, default=_now)


# ── Analysis history (public /analyze endpoint, optional auth) ─────────────────

class AnalysisHistory(Base):
    """Stores results from the public /analyze endpoint when user is logged in."""
    __tablename__ = "analysis_history"

    id                  = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    candidate_id        = Column(UUID(as_uuid=False), ForeignKey("candidates.id", ondelete="CASCADE"),
                                 nullable=True, index=True)
    job_title           = Column(String(255), nullable=True)
    company             = Column(String(255), nullable=True)
    job_url             = Column(String(1024), nullable=True)
    overall_score       = Column(Integer, nullable=True)
    ats_score           = Column(Integer, nullable=True)
    keyword_match_score = Column(Integer, nullable=True)
    skills_match_score  = Column(Integer, nullable=True)
    experience_score    = Column(Integer, nullable=True)
    format_score        = Column(Integer, nullable=True)
    matched_keywords    = Column(JSONB, nullable=True)
    missing_keywords    = Column(JSONB, nullable=True)
    improvements        = Column(JSONB, nullable=True)
    summary             = Column(Text, nullable=True)
    analyzed_at         = Column(DateTime(timezone=True), nullable=False, default=_now)

    candidate = relationship("Candidate", back_populates="analyses")


# ── Guard: prevent accidental AuditLog updates via ORM ───────────────────────

@event.listens_for(AuditLog, "before_update")
def _block_audit_update(mapper, connection, target):
    raise RuntimeError("audit_log rows are immutable — never call session.merge() on them")
