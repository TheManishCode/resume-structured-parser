"""
packages/api/routers/scores.py

/scores/{score_id}     — GET: full score detail (recruiter)
/scores/candidate/me   — GET: candidate sees their own scores + improvement suggestions
"""
from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from packages.api.deps import CandidateUser, DbSession, RecruiterUser
from packages.core.db.models import Resume, Score

router = APIRouter()


@router.get("/candidate/me")
async def my_scores(user: CandidateUser, db: DbSession):
    """Candidate sees all their resume scores (for all roles they were evaluated against)."""
    rows = (await db.execute(
        select(Score, Resume)
        .join(Resume, Score.resume_id == Resume.id)
        .where(Resume.candidate_id == user["sub"])
        .order_by(Score.scored_at.desc())
    )).all()

    return [
        {
            **_full_score(s),
            "improvement_tip": _improvement_tip(s),
        }
        for s, _r in rows
    ]


def _full_score(s: Score) -> dict:
    return {
        "id":                str(s.id),
        "resume_id":         str(s.resume_id),
        "job_id":            str(s.job_id),
        "score":             s.score,
        "local_score":       s.local_score,
        "cloud_score":       s.cloud_score,
        "justification":     s.justification,
        "scored_by":         s.scored_by,
        "status":            s.status,
        "needs_review":      s.needs_review,
        "disagreement_delta": s.disagreement_delta,
        "previous_score":    s.previous_score,
        "local_confidence":  s.local_confidence,
        "scored_at":         s.scored_at.isoformat(),
    }


@router.get("/{score_id}")
async def get_score(score_id: UUID, user: RecruiterUser, db: DbSession):
    row = await db.get(Score, str(score_id))
    if not row:
        raise HTTPException(status_code=404, detail="Score not found")
    return _full_score(row)


def _improvement_tip(s: Score) -> str | None:
    if s.score is None:
        return None
    if s.score >= 0.80:
        return "Strong match. Ensure your resume highlights measurable outcomes."
    if s.score >= 0.60:
        return "Good match. Consider adding more specific technical depth to career descriptions."
    if s.score >= 0.40:
        return "Moderate match. Tailor your resume's skills section more closely to this role's JD."
    return "Low match for this role. The role likely requires experience this resume doesn't demonstrate."
