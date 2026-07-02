"""
packages/api/routers/candidate_dashboard.py

Candidate-facing dashboard and profile endpoints.

GET  /candidate/profile           — full profile
PATCH /candidate/profile          — update profile
GET  /candidate/dashboard         — dashboard summary
GET  /candidate/analytics         — detailed analytics
GET  /candidate/history           — analysis history
GET  /candidate/profile-completeness
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from packages.api.deps import CandidateUser, DbSession
from packages.core.db.models import AnalysisHistory, Candidate, Resume, Score

router = APIRouter()


# ── Profile ───────────────────────────────────────────────────────────────────

class CandidateProfileUpdate(BaseModel):
    name:             str | None = None
    phone:            str | None = None
    location:         str | None = None
    target_roles:     list[str] | None = None
    experience_level: str | None = None
    job_type_pref:    list[str] | None = None
    skills:           list[str] | None = None
    visibility:       bool | None = None


@router.get("/profile")
async def get_profile(user: CandidateUser, db: DbSession):
    cand = await db.get(Candidate, user["sub"])
    if not cand:
        raise HTTPException(404, "Candidate not found")
    return _profile_dict(cand)


@router.patch("/profile")
async def update_profile(user: CandidateUser, db: DbSession, body: CandidateProfileUpdate):
    cand = await db.get(Candidate, user["sub"])
    if not cand:
        raise HTTPException(404, "Candidate not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(cand, field, value)
    # Mark onboarding done if minimum fields are present
    if cand.name and cand.skills:
        cand.onboarding_done = True
    return _profile_dict(cand)


@router.get("/profile-completeness")
async def profile_completeness(user: CandidateUser, db: DbSession):
    cand = await db.get(Candidate, user["sub"])
    if not cand:
        raise HTTPException(404, "Candidate not found")
    return _completeness(cand)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard(user: CandidateUser, db: DbSession):
    cid = user["sub"]
    cand = await db.get(Candidate, cid)

    # Resume count
    resumes = (await db.scalars(
        select(Resume).where(Resume.candidate_id == cid, Resume.is_expired == False)
    )).all()

    # Analysis history
    analyses = (await db.scalars(
        select(AnalysisHistory)
        .where(AnalysisHistory.candidate_id == cid)
        .order_by(AnalysisHistory.analyzed_at.desc())
        .limit(10)
    )).all()

    # Score trend from scores table
    score_rows = (await db.scalars(
        select(Score)
        .join(Resume, Score.resume_id == Resume.id)
        .where(Resume.candidate_id == cid)
        .order_by(Score.scored_at.desc())
        .limit(10)
    )).all()

    recent_scores = [
        {"date": s.scored_at.strftime("%b %d"), "score": round(s.score * 100)}
        for s in reversed(score_rows)
    ]

    # Missing keywords frequency
    kw_freq: dict[str, int] = {}
    for a in analyses:
        for kw in (a.missing_keywords or []):
            kw_freq[kw] = kw_freq.get(kw, 0) + 1
    top_missing = sorted(kw_freq.items(), key=lambda x: -x[1])[:8]

    # Best matching roles from analyses
    best_roles = sorted(
        [a for a in analyses if a.overall_score and a.overall_score >= 65],
        key=lambda x: -(x.overall_score or 0),
    )[:5]

    return {
        "candidate":           _profile_dict(cand) if cand else None,
        "completeness":        _completeness(cand) if cand else None,
        "resume_count":        len(resumes),
        "total_analyses":      len(analyses),
        "recent_score_trend":  recent_scores,
        "top_missing_skills":  [{"skill": k, "count": v} for k, v in top_missing],
        "best_matching_roles": [
            {"job_title": a.job_title, "company": a.company, "score": a.overall_score}
            for a in best_roles
        ],
        "recent_analyses":     [_analysis_dict(a) for a in analyses[:5]],
    }


@router.get("/analytics")
async def analytics(user: CandidateUser, db: DbSession):
    cid = user["sub"]

    analyses = (await db.scalars(
        select(AnalysisHistory)
        .where(AnalysisHistory.candidate_id == cid)
        .order_by(AnalysisHistory.analyzed_at.asc())
    )).all()

    # Score trend over time
    score_trend = [
        {
            "date": a.analyzed_at.strftime("%b %d"),
            "overall": a.overall_score,
            "ats": a.ats_score,
            "keywords": a.keyword_match_score,
        }
        for a in analyses if a.overall_score
    ]

    # Skill gap frequency
    kw_freq: dict[str, int] = {}
    for a in analyses:
        for kw in (a.missing_keywords or []):
            kw_freq[kw] = kw_freq.get(kw, 0) + 1
    skill_gaps = [{"skill": k, "count": v} for k, v in
                  sorted(kw_freq.items(), key=lambda x: -x[1])[:15]]

    # Keyword coverage per job
    keyword_coverage = [
        {
            "job": f"{a.job_title or 'Unknown'} @ {a.company or '?'}",
            "matched": len(a.matched_keywords or []),
            "missing": len(a.missing_keywords or []),
        }
        for a in analyses[-8:]
    ]

    return {
        "total_analyses":    len(analyses),
        "avg_overall_score": int(sum(a.overall_score or 0 for a in analyses) / max(len(analyses), 1)),
        "avg_ats_score":     int(sum(a.ats_score or 0 for a in analyses) / max(len(analyses), 1)),
        "score_trend":       score_trend,
        "skill_gaps":        skill_gaps,
        "keyword_coverage":  keyword_coverage,
    }


@router.get("/history")
async def history(user: CandidateUser, db: DbSession, limit: int = 20, offset: int = 0):
    cid = user["sub"]
    rows = (await db.scalars(
        select(AnalysisHistory)
        .where(AnalysisHistory.candidate_id == cid)
        .order_by(AnalysisHistory.analyzed_at.desc())
        .limit(limit)
        .offset(offset)
    )).all()
    total = await db.scalar(
        select(func.count()).select_from(AnalysisHistory)
        .where(AnalysisHistory.candidate_id == cid)
    )
    return {"total": total, "items": [_analysis_dict(a) for a in rows]}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _profile_dict(c: Candidate) -> dict:
    return {
        "id":              str(c.id),
        "email":           c.email,
        "name":            c.name,
        "phone":           c.phone,
        "location":        c.location,
        "target_roles":    c.target_roles or [],
        "experience_level": c.experience_level,
        "job_type_pref":   c.job_type_pref or [],
        "skills":          c.skills or [],
        "visibility":      c.visibility,
        "onboarding_done": c.onboarding_done,
        "created_at":      c.created_at.isoformat(),
    }


def _completeness(c: Candidate) -> dict[str, Any]:
    fields = {
        "name":            bool(c.name),
        "phone":           bool(c.phone),
        "location":        bool(c.location),
        "target_roles":    bool(c.target_roles),
        "experience_level": bool(c.experience_level),
        "job_type_pref":   bool(c.job_type_pref),
        "skills":          bool(c.skills),
        "resume_uploaded": False,   # caller can override
    }
    score = int(sum(fields.values()) / len(fields) * 100)
    missing = [k.replace("_", " ").title() for k, v in fields.items() if not v]
    return {"score": score, "fields": fields, "missing": missing}


def _analysis_dict(a: AnalysisHistory) -> dict:
    return {
        "id":                  str(a.id),
        "job_title":           a.job_title,
        "company":             a.company,
        "job_url":             a.job_url,
        "overall_score":       a.overall_score,
        "ats_score":           a.ats_score,
        "keyword_match_score": a.keyword_match_score,
        "skills_match_score":  a.skills_match_score,
        "missing_keywords":    a.missing_keywords or [],
        "improvements":        a.improvements or [],
        "summary":             a.summary,
        "analyzed_at":         a.analyzed_at.isoformat(),
    }
