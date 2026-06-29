"""
packages/api/routers/jobs.py

/jobs            — POST (recruiter creates), GET (list own jobs)
/jobs/{id}       — GET
/jobs/{id}/score — POST: score a specific resume against this job via the router
/jobs/{id}/rank  — GET: ranked shortlist for this job
/jobs/{id}/suggest — GET: RAG-backed talent suggestions
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func

from packages.api.deps import DbSession, RecruiterUser
from packages.core.db.models import AuditLog, Job, Resume, Score, ResumeJobTag
from packages.core.router.adapters import build_router
from packages.core.router.router import ScoredBy, Status

router = APIRouter()


class JobCreate(BaseModel):
    title:       str
    description: str


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_job(body: JobCreate, user: RecruiterUser, db: DbSession):
    job = Job(recruiter_id=user["sub"], title=body.title, description=body.description)
    db.add(job)
    await db.flush()
    return {"id": str(job.id), "title": job.title}


@router.get("")
async def list_jobs(user: RecruiterUser, db: DbSession):
    rows = (await db.scalars(
        select(Job).where(Job.recruiter_id == user["sub"], Job.is_active == True)
    )).all()
    return [{"id": str(j.id), "title": j.title, "created_at": j.created_at.isoformat()} for j in rows]


@router.get("/{job_id}")
async def get_job(job_id: UUID, user: RecruiterUser, db: DbSession):
    job = await _get_own_job(str(job_id), user["sub"], db)
    return {"id": str(job.id), "title": job.title, "description": job.description}


# ── Scoring ────────────────────────────────────────────────────────────────────

class ScoreRequest(BaseModel):
    resume_id:   str
    force_cloud: bool = False


@router.post("/{job_id}/score")
async def score_resume(
    job_id:     UUID,
    body:       ScoreRequest,
    user:       RecruiterUser,
    db:         DbSession,
    background: BackgroundTasks,
):
    """Score one resume against this job via the model router."""
    job = await _get_own_job(str(job_id), user["sub"], db)
    resume = await db.get(Resume, body.resume_id)
    if not resume or resume.is_expired:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Cost guardrail check
    await _enforce_cloud_cap(user["sub"], db)

    router_inst = build_router()
    result = await router_inst.score(
        resume_text=resume.text_content,
        job_description=job.description,
        force_cloud=body.force_cloud,
        candidate_id=body.resume_id,
    )

    # Upsert Score row
    existing = await db.scalar(
        select(Score).where(Score.resume_id == body.resume_id, Score.job_id == str(job_id))
    )
    if existing:
        previous = existing.score
        existing.score              = result.score
        existing.cloud_score        = result.cloud_score
        existing.local_score        = result.local_score
        existing.justification      = result.justification
        existing.scored_by          = result.scored_by.value
        existing.status             = result.status.value
        existing.previous_score     = previous if result.status == Status.re_scored else None
        existing.needs_review       = result.needs_review
        existing.disagreement_delta = result.disagreement_delta
        existing.local_confidence   = result.local_confidence
        existing.latency_ms         = result.latency_ms
        score_row = existing
    else:
        score_row = Score(
            resume_id           = body.resume_id,
            job_id              = str(job_id),
            score               = result.score,
            local_score         = result.local_score,
            cloud_score         = result.cloud_score,
            justification       = result.justification,
            scored_by           = result.scored_by.value,
            status              = result.status.value,
            needs_review        = result.needs_review,
            disagreement_delta  = result.disagreement_delta,
            local_confidence    = result.local_confidence,
            latency_ms          = result.latency_ms,
        )
        db.add(score_row)

    db.add(AuditLog(
        event_type  = "score.created" if not existing else "score.updated",
        actor_id    = user["sub"],
        actor_role  = "recruiter",
        entity_id   = body.resume_id,
        entity_type = "score",
        model_used  = result.scored_by.value,
        payload     = {
            "score":         result.score,
            "status":        result.status.value,
            "needs_review":  result.needs_review,
        },
    ))

    await db.flush()

    return {
        "score_id":          str(score_row.id),
        "score":             result.score,
        "scored_by":         result.scored_by.value,
        "status":            result.status.value,
        "needs_review":      result.needs_review,
        "disagreement_delta": result.disagreement_delta,
        "justification":     result.justification,
    }


# ── Ranked shortlist ──────────────────────────────────────────────────────────

@router.get("/{job_id}/rank")
async def ranked_shortlist(job_id: UUID, user: RecruiterUser, db: DbSession, limit: int = 20):
    await _get_own_job(str(job_id), user["sub"], db)
    rows = (await db.execute(
        select(Score, Resume)
        .join(Resume, Score.resume_id == Resume.id)
        .where(Score.job_id == str(job_id), Resume.is_expired == False)
        .order_by(Score.score.desc())
        .limit(limit)
    )).all()

    return [
        {
            "rank":             i + 1,
            "resume_id":        str(s.resume_id),
            "score":            s.score,
            "scored_by":        s.scored_by,
            "status":           s.status,
            "needs_review":     s.needs_review,
            "justification":    s.justification,
            "previous_score":   s.previous_score,
        }
        for i, (s, _r) in enumerate(rows)
    ]


# ── Talent suggestions (unscored candidates for this job) ────────────────────

@router.get("/{job_id}/suggest")
async def suggest_candidates(job_id: UUID, user: RecruiterUser, db: DbSession, limit: int = 10):
    """Return resumes not yet scored for this job — quick shortlist suggestions."""
    await _get_own_job(str(job_id), user["sub"], db)
    from sqlalchemy import not_

    already_scored = select(Score.resume_id).where(Score.job_id == str(job_id))
    rows = (await db.scalars(
        select(Resume)
        .where(
            Resume.is_expired == False,
            not_(Resume.id.in_(already_scored)),
        )
        .order_by(Resume.uploaded_at.desc())
        .limit(limit)
    )).all()

    return [
        {
            "resume_id":   str(r.id),
            "uploaded_at": r.uploaded_at.isoformat(),
            "expires_at":  r.expires_at.isoformat(),
        }
        for r in rows
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_own_job(job_id: str, recruiter_id: str, db) -> Job:
    job = await db.get(Job, job_id)
    if not job or job.recruiter_id != recruiter_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _enforce_cloud_cap(recruiter_id: str, db) -> None:
    from datetime import date as _date
    from packages.core.db.models import Recruiter
    rec = await db.get(Recruiter, recruiter_id)
    if not rec:
        return
    today = _date.today()
    if rec.cap_reset_date != today:
        rec.cloud_calls_today = 0
        rec.cap_reset_date = today
    if rec.cloud_calls_today >= rec.daily_cloud_cap:
        from fastapi import HTTPException
        raise HTTPException(status_code=429, detail="Daily cloud scoring cap reached")
    rec.cloud_calls_today += 1
