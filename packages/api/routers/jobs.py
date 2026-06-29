"""
packages/api/routers/jobs.py

/jobs                   — POST (recruiter creates), GET (list own jobs)
/jobs/{id}              — GET
/jobs/{id}/score        — POST: score a specific resume against this job via model router
/jobs/{id}/rank         — GET: ranked shortlist for this job
/jobs/{id}/suggest      — GET: unscored resume suggestions
/jobs/{id}/bulk_rank    — POST: deterministic pre-filter all resumes, queue top-N for AI
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


# ── Bulk deterministic pre-rank + AI queue ───────────────────────────────────

@router.post("/{job_id}/bulk_rank")
async def bulk_rank(
    job_id:     UUID,
    user:       RecruiterUser,
    db:         DbSession,
    background: BackgroundTasks,
    top_n:      int = 20,
):
    """
    Two-phase ranking for a job:

    Phase 1 (sync, instant): Run the deterministic scoring engine on every
    non-expired resume in the DB that doesn't yet have a score for this job.
    Stores rule-based scores immediately so the recruiter sees ranked results.

    Phase 2 (async background): The top `top_n` deterministic-scored resumes
    are queued for AI scoring (Ollama → Claude → Groq). These upgrade the
    provisional local scores to cloud-confirmed scores as they complete.

    Returns the top-N with their deterministic scores and queued status.
    """
    job = await _get_own_job(str(job_id), user["sub"], db)

    from sqlalchemy import not_
    from packages.core import scoring as core_scoring

    already_scored = select(Score.resume_id).where(Score.job_id == str(job_id))
    unscored = (await db.scalars(
        select(Resume)
        .where(Resume.is_expired == False, not_(Resume.id.in_(already_scored)))
    )).all()

    if not unscored:
        return {"message": "No new resumes to rank", "ranked": 0, "queued_for_ai": 0}

    # Phase 1: deterministic scoring
    scored_rows = []
    for resume in unscored:
        if not resume.parsed_json:
            continue
        candidate = resume.parsed_json
        result = core_scoring.score_candidate(candidate)
        scored_rows.append((resume, result))

    scored_rows.sort(key=lambda x: -x[1]["score"])

    new_score_objs = []
    for resume, result in scored_rows:
        score_row = Score(
            resume_id          = str(resume.id),
            job_id             = str(job_id),
            score              = result["score"],
            local_score        = result["score"],
            cloud_score        = None,
            justification      = result.get("reasoning"),
            scored_by          = "local",
            status             = "provisional",
            needs_review       = False,
            local_confidence   = result["sub_scores"].get("role_relevance", 0.0),
        )
        db.add(score_row)
        new_score_objs.append(score_row)

    db.add(AuditLog(
        event_type  = "bulk_rank.local",
        actor_id    = user["sub"],
        actor_role  = "recruiter",
        entity_id   = str(job_id),
        entity_type = "job",
        model_used  = "local",
        payload     = {"scored": len(scored_rows), "top_n_queued": min(top_n, len(scored_rows))},
    ))
    await db.flush()

    # Phase 2: queue top-N for AI scoring in background
    top_for_ai = scored_rows[:top_n]

    async def _ai_upgrade():
        from packages.core.router.adapters import build_router as _build
        from packages.core.db.session import AsyncSessionLocal
        try:
            router_inst = _build()
        except ValueError:
            return
        async with AsyncSessionLocal() as bg_session:
            for resume, _ in top_for_ai:
                try:
                    ai_result = await router_inst.score(
                        resume_text=resume.text_content,
                        job_description=job.description,
                        candidate_id=str(resume.id),
                    )
                    existing = await bg_session.scalar(
                        select(Score).where(
                            Score.resume_id == str(resume.id),
                            Score.job_id == str(job_id),
                        )
                    )
                    if existing:
                        existing.score        = ai_result.score
                        existing.cloud_score  = ai_result.cloud_score
                        existing.justification = ai_result.justification
                        existing.scored_by    = ai_result.scored_by.value
                        existing.status       = "confirmed"
                        existing.needs_review = ai_result.needs_review
                except Exception as exc:
                    logging.warning("AI upgrade failed for %s: %s", resume.id, exc)
            await bg_session.commit()

    background.add_task(_ai_upgrade)

    top_results = [
        {
            "rank":       i + 1,
            "resume_id":  str(r.id),
            "score":      sc["score"],
            "scored_by":  "local",
            "status":     "provisional",
            "reasoning":  sc.get("reasoning", ""),
        }
        for i, (r, sc) in enumerate(scored_rows[:top_n])
    ]

    return {
        "ranked":         len(scored_rows),
        "queued_for_ai":  len(top_for_ai),
        "top": top_results,
    }


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
