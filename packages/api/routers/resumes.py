"""
packages/api/routers/resumes.py

/resumes/upload   — POST (candidate uploads PDF or ZIP)
/resumes/me       — GET (candidate views their own resume)
/resumes/{id}     — GET (recruiter views a specific resume — own-org only via row-level access)
"""
from __future__ import annotations

import io
import json
import zipfile
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select

from packages.api.deps import CandidateUser, DbSession, RecruiterUser
from packages.core.db.models import AuditLog, Resume
from packages.core.ingestion.pipeline import ingest_file

router = APIRouter()


@router.post("/upload", status_code=201)
async def upload_resume(
    user: CandidateUser,
    db:   DbSession,
    file: UploadFile = File(...),
):
    """Accept PDF, DOCX, or ZIP (multi-resume batch). Returns resume ID(s)."""
    raw = await file.read()
    filename = file.filename or "unknown"

    if filename.lower().endswith(".zip"):
        ids = []
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                if name.lower().endswith((".pdf", ".docx")):
                    data = zf.read(name)
                    ids.append(await _persist_resume(user["sub"], name, data, db))
        return {"resume_ids": ids}

    resume_id = await _persist_resume(user["sub"], filename, raw, db)
    return {"resume_id": resume_id}


async def _persist_resume(candidate_id: str, filename: str, raw: bytes, db) -> str:
    parsed, text, used_ocr = await ingest_file(filename, raw)

    resume = Resume(
        candidate_id=candidate_id,
        original_name=filename,
        parsed_json=parsed,
        text_content=text,
        used_ocr=used_ocr,
    )
    db.add(resume)
    await db.flush()

    db.add(AuditLog(
        event_type="resume.uploaded",
        actor_id=candidate_id,
        actor_role="candidate",
        entity_id=str(resume.id),
        entity_type="resume",
        payload={"filename": filename, "used_ocr": used_ocr},
    ))

    return str(resume.id)


@router.get("/me")
async def my_resume(user: CandidateUser, db: DbSession):
    rows = (await db.scalars(
        select(Resume).where(Resume.candidate_id == user["sub"], Resume.is_expired == False)
    )).all()
    return [_resume_summary(r) for r in rows]


@router.get("/{resume_id}")
async def get_resume(resume_id: UUID, user: RecruiterUser, db: DbSession):
    r = await db.get(Resume, str(resume_id))
    if not r or r.is_expired:
        raise HTTPException(status_code=404, detail="Resume not found or expired")
    return _resume_summary(r)


def _resume_summary(r: Resume) -> dict:
    return {
        "id":          str(r.id),
        "uploaded_at": r.uploaded_at.isoformat(),
        "expires_at":  r.expires_at.isoformat(),
        "used_ocr":    r.used_ocr,
        # Return parsed JSON but strip any bias fields before sending
        "parsed":      _strip_bias_fields(r.parsed_json or {}),
    }


def _strip_bias_fields(data: dict) -> dict:
    """Remove bias-sensitive fields before sending parsed resume to recruiter UI."""
    stripped = dict(data)
    stripped.pop("anonymized_name", None)
    if "education" in stripped:
        for edu in stripped["education"]:
            edu.pop("tier",         None)
            edu.pop("grade",        None)
            edu.pop("start_year",   None)
            edu.pop("end_year",     None)
            edu.pop("institution",  None)
    return stripped
