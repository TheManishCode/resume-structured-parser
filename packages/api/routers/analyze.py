"""
packages/api/routers/analyze.py

POST /analyze
  — No authentication required (public consumer endpoint).
  — Accepts a resume file (PDF/DOCX) + a job posting URL (or pasted text).
  — Returns comprehensive ATS + AI analysis.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from packages.api.deps import DbSession
from packages.core.analysis.ats_analyzer import analyze_resume, check_ats_only
from packages.core.db.models import AnalysisHistory
from packages.core.ingestion.pipeline import ingest_file
from packages.core.scraper.job_scraper import ScrapeError, scrape_job

_bearer = HTTPBearer(auto_error=False)
JWT_SECRET    = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("")
async def analyze(
    db:       DbSession,
    file:     UploadFile = File(..., description="Resume — PDF or DOCX"),
    job_url:  str        = Form("",  description="URL of job posting"),
    job_text: str        = Form("",  description="Fallback: paste job description text"),
    creds:    HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """
    Analyze a resume against a job posting.

    Scrapes the job description from `job_url` (LinkedIn, Indeed, Glassdoor,
    company sites, Lever, Greenhouse, Workday, etc.). If scraping fails, falls
    back to the `job_text` field so the user can paste the JD manually.

    When called with a valid candidate JWT, saves result to AnalysisHistory.

    Returns a full ATS breakdown: scores, matched/missing keywords, strengths,
    actionable improvements, and an executive summary.
    """
    # ── 1. Parse resume ───────────────────────────────────────────────────────
    raw      = await file.read()
    filename = file.filename or "resume.pdf"
    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ("pdf", "doc", "docx"):
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Please upload a PDF or DOCX resume.",
        )

    try:
        _parsed, resume_text, _ocr = await ingest_file(filename, raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse resume: {exc}")

    if not resume_text or len(resume_text.strip()) < 50:
        raise HTTPException(
            status_code=422,
            detail="Resume appears empty or unreadable. Try a different file.",
        )

    # ── 2. Get job description ─────────────────────────────────────────────────
    job_metadata    = None
    job_description = ""
    scrape_failed   = False
    scrape_error    = ""

    if job_url.strip():
        try:
            job_metadata    = await scrape_job(job_url.strip())
            job_description = job_metadata.get("description", "")
            if len(job_description.strip()) < 100:
                raise ScrapeError("Scraped content too short — page may require login")
        except ScrapeError as exc:
            scrape_failed = True
            scrape_error  = str(exc)
            logger.warning("Job scrape failed for %s: %s", job_url, exc)

    if not job_description.strip() and job_text.strip():
        job_description = job_text.strip()

    if not job_description or len(job_description.strip()) < 50:
        if scrape_failed:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Could not fetch the job description from that URL "
                        "(it may require a login or be behind a CAPTCHA). "
                        "Please paste the job description text directly."
                    ),
                    "scrape_failed": True,
                    "scrape_error":  scrape_error,
                },
            )
        raise HTTPException(
            status_code=422,
            detail="Provide a job posting URL or paste the job description text.",
        )

    # ── 3. Run analysis ────────────────────────────────────────────────────────
    try:
        result = await analyze_resume(resume_text, job_description, job_metadata)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Analysis error")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    result["scrape_source"] = (job_metadata["source"] if job_metadata else "pasted")

    # ── 4. Persist to history if candidate is authenticated ────────────────────
    candidate_id = _extract_candidate_id(creds)
    if candidate_id:
        try:
            record = AnalysisHistory(
                candidate_id        = candidate_id,
                job_title           = result.get("job_title"),
                company             = result.get("company"),
                job_url             = job_url.strip() or None,
                overall_score       = result.get("overall_score"),
                ats_score           = result.get("ats_score"),
                keyword_match_score = result.get("keyword_match_score"),
                skills_match_score  = result.get("skills_match_score"),
                experience_score    = result.get("experience_score"),
                format_score        = result.get("format_score"),
                matched_keywords    = result.get("matched_keywords"),
                missing_keywords    = result.get("missing_keywords"),
                improvements        = result.get("improvements"),
                summary             = result.get("summary"),
            )
            db.add(record)
            await db.flush()
            result["history_id"] = str(record.id)
        except Exception as exc:
            logger.warning("Failed to save analysis history: %s", exc)

    return result


@router.post("/ats-check")
async def ats_check(
    file: UploadFile = File(..., description="Resume — PDF or DOCX"),
):
    """
    Standalone ATS audit — no job description required.

    Evaluates the resume itself for ATS compatibility, contact completeness,
    content quality, and formatting. Returns scores, flagged issues, extracted
    skills, and actionable improvement tips.
    """
    raw      = await file.read()
    filename = file.filename or "resume.pdf"
    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ("pdf", "doc", "docx"):
        raise HTTPException(status_code=415, detail="Unsupported file type. Upload a PDF or DOCX.")

    try:
        _parsed, resume_text, _ocr = await ingest_file(filename, raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse resume: {exc}")

    if not resume_text or len(resume_text.strip()) < 50:
        raise HTTPException(status_code=422, detail="Resume appears empty or unreadable.")

    try:
        result = await check_ats_only(resume_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("ATS check error")
        raise HTTPException(status_code=500, detail=f"ATS check failed: {exc}")

    return result


def _extract_candidate_id(creds: HTTPAuthorizationCredentials | None) -> str | None:
    if not creds:
        return None
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("role") == "candidate":
            return payload.get("sub")
    except JWTError:
        pass
    return None
