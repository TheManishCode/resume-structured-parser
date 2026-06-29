"""
packages/api/routers/candidates.py

/candidates/me  — GET (candidate profile)
"""
from fastapi import APIRouter
from packages.api.deps import CandidateUser, DbSession
from packages.core.db.models import Candidate
from sqlalchemy import select

router = APIRouter()


@router.get("/me")
async def my_profile(user: CandidateUser, db: DbSession):
    cand = await db.get(Candidate, user["sub"])
    if not cand:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"id": str(cand.id), "email": cand.email, "created_at": cand.created_at.isoformat()}
