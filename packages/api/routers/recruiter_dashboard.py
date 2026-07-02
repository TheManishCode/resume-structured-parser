"""
packages/api/routers/recruiter_dashboard.py

Recruiter-facing dashboard, analytics, and profile endpoints.

GET  /recruiter/profile
PATCH /recruiter/profile
GET  /recruiter/dashboard
GET  /recruiter/analytics
GET  /recruiter/jobs/:jobId/analytics
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from packages.api.deps import DbSession, RecruiterUser
from packages.core.db.models import AuditLog, Job, Recruiter, Resume, Score

router = APIRouter()


# ── Profile ───────────────────────────────────────────────────────────────────

class RecruiterProfileUpdate(BaseModel):
    name:            str | None = None
    org_name:        str | None = None
    company_website: str | None = None
    hiring_role:     str | None = None
    hiring_domains:  list[str] | None = None
    company_size:    str | None = None


@router.get("/profile")
async def get_profile(user: RecruiterUser, db: DbSession):
    rec = await db.get(Recruiter, user["sub"])
    if not rec:
        raise HTTPException(404, "Recruiter not found")
    return _profile_dict(rec)


@router.patch("/profile")
async def update_profile(user: RecruiterUser, db: DbSession, body: RecruiterProfileUpdate):
    rec = await db.get(Recruiter, user["sub"])
    if not rec:
        raise HTTPException(404, "Recruiter not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(rec, field, value)
    if rec.name and rec.hiring_role:
        rec.onboarding_done = True
    return _profile_dict(rec)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard(user: RecruiterUser, db: DbSession):
    rid = user["sub"]
    rec = await db.get(Recruiter, rid)

    # Jobs
    jobs = (await db.scalars(
        select(Job).where(Job.recruiter_id == rid)
    )).all()
    active_jobs = [j for j in jobs if j.is_active]

    # Scores for all jobs owned by this recruiter
    job_ids = [str(j.id) for j in jobs]
    scores: list[Score] = []
    if job_ids:
        scores = (await db.scalars(
            select(Score).where(Score.job_id.in_(job_ids))
        )).all()

    total_resumes = await db.scalar(select(func.count(Resume.id)))
    parsed_resumes = await db.scalar(
        select(func.count(Resume.id)).where(Resume.parsed_json.isnot(None))
    )

    # Hiring funnel
    statuses = {"provisional": 0, "confirmed": 0, "re_scored": 0}
    for s in scores:
        statuses[s.status] = statuses.get(s.status, 0) + 1

    shortlisted = sum(1 for s in scores if s.score and s.score >= 0.70)
    matched     = sum(1 for s in scores if s.score and s.score >= 0.50)

    # Average score per job
    job_perf = []
    for j in active_jobs[:8]:
        jscores = [s for s in scores if str(s.job_id) == str(j.id)]
        if jscores:
            avg = sum(s.score for s in jscores if s.score) / max(len(jscores), 1)
            top = max((s.score for s in jscores if s.score), default=0)
            job_perf.append({
                "job_id":    str(j.id),
                "title":     j.title,
                "candidates": len(jscores),
                "avg_score": round(avg * 100, 1),
                "top_score": round(top * 100, 1),
            })

    # Recent audit activity
    recent_events = (await db.scalars(
        select(AuditLog)
        .where(AuditLog.actor_id == rid)
        .order_by(AuditLog.occurred_at.desc())
        .limit(8)
    )).all()

    return {
        "recruiter":       _profile_dict(rec) if rec else None,
        "total_jobs":      len(jobs),
        "active_jobs":     len(active_jobs),
        "total_resumes":   total_resumes or 0,
        "parsed_resumes":  parsed_resumes or 0,
        "total_scored":    len(scores),
        "matched":         matched,
        "shortlisted":     shortlisted,
        "avg_score":       round(sum(s.score for s in scores if s.score) / max(len(scores), 1) * 100, 1) if scores else 0,
        "hiring_funnel": {
            "uploaded":    total_resumes or 0,
            "parsed":      parsed_resumes or 0,
            "scored":      len(scores),
            "matched":     matched,
            "shortlisted": shortlisted,
        },
        "job_performance":  job_perf,
        "recent_activity":  [
            {
                "event":      e.event_type,
                "entity":     e.entity_type,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in recent_events
        ],
    }


@router.get("/analytics")
async def analytics(user: RecruiterUser, db: DbSession):
    rid = user["sub"]
    job_ids = [str(j.id) for j in (await db.scalars(
        select(Job).where(Job.recruiter_id == rid)
    )).all()]

    scores: list[Score] = []
    if job_ids:
        scores = (await db.scalars(
            select(Score).where(Score.job_id.in_(job_ids))
        )).all()

    score_dist = {"0-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
    for s in scores:
        if s.score is None:
            continue
        pct = s.score * 100
        if pct < 40:   score_dist["0-40"]   += 1
        elif pct < 60: score_dist["40-60"]  += 1
        elif pct < 80: score_dist["60-80"]  += 1
        else:          score_dist["80-100"] += 1

    # Skills found across parsed resumes
    resumes = (await db.scalars(
        select(Resume).where(Resume.parsed_json.isnot(None), Resume.is_expired == False)
    )).all()
    skill_freq: dict[str, int] = {}
    for r in resumes:
        for sk in (r.parsed_json or {}).get("skills_raw", []):
            skill_freq[sk] = skill_freq.get(sk, 0) + 1
    top_skills = [{"skill": k, "count": v} for k, v in
                  sorted(skill_freq.items(), key=lambda x: -x[1])[:15]]

    return {
        "total_scored":  len(scores),
        "score_distribution": [{"range": k, "count": v} for k, v in score_dist.items()],
        "top_skills_in_pool": top_skills,
        "needs_review_count": sum(1 for s in scores if s.needs_review),
    }


@router.get("/jobs/{job_id}/analytics")
async def job_analytics(job_id: str, user: RecruiterUser, db: DbSession):
    job = await db.get(Job, job_id)
    if not job or str(job.recruiter_id) != user["sub"]:
        raise HTTPException(404, "Job not found")

    scores = (await db.scalars(
        select(Score).where(Score.job_id == job_id).order_by(Score.score.desc())
    )).all()

    avg = sum(s.score for s in scores if s.score) / max(len(scores), 1)
    top = max((s.score for s in scores if s.score), default=0)

    return {
        "job_id":        job_id,
        "title":         job.title,
        "total_scored":  len(scores),
        "avg_score":     round(avg * 100, 1),
        "top_score":     round(top * 100, 1),
        "shortlisted":   sum(1 for s in scores if s.score and s.score >= 0.70),
        "needs_review":  sum(1 for s in scores if s.needs_review),
        "score_list":    [
            {"resume_id": str(s.resume_id), "score": round(s.score * 100, 1),
             "status": s.status, "scored_by": s.scored_by}
            for s in scores[:20]
        ],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _profile_dict(r: Recruiter) -> dict:
    return {
        "id":              str(r.id),
        "email":           r.email,
        "name":            r.name,
        "org_name":        r.org_name,
        "company_website": r.company_website,
        "hiring_role":     r.hiring_role,
        "hiring_domains":  r.hiring_domains or [],
        "company_size":    r.company_size,
        "onboarding_done": r.onboarding_done,
        "created_at":      r.created_at.isoformat(),
    }
