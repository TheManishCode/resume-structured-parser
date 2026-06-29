"""
packages/api/main.py

FastAPI application entry point.

Run:
    uvicorn packages.api.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, jobs, resumes, scores, candidates

logging.basicConfig(level=logging.INFO)

_retry_queue: asyncio.Queue = asyncio.Queue()

_EXPIRY_INTERVAL_SECONDS = int(os.getenv("EXPIRY_CHECK_INTERVAL_SECONDS", "3600"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(_retry_worker()),
        asyncio.create_task(_expiry_worker()),
    ]
    yield
    for t in tasks:
        t.cancel()


async def _retry_worker():
    from packages.core.router.adapters import build_router
    try:
        router = build_router(retry_queue=_retry_queue)
    except ValueError as exc:
        logging.warning("Retry worker disabled: %s", exc)
        return

    while True:
        job = await _retry_queue.get()
        try:
            result = await router.retry_with_primary(
                resume_text=job["resume_text"],
                job_description=job["jd"],
                previous_score=job["fallback_score"],
                candidate_id=job.get("candidate_id"),
            )
            logging.info(
                "Retry complete for %s: status=%s score=%.3f",
                job.get("candidate_id"), result.status, result.score
            )
        except Exception as exc:
            logging.error("Retry worker error: %s", exc)
        finally:
            _retry_queue.task_done()


async def _expiry_worker():
    """Mark resumes as expired once their expires_at date has passed."""
    from sqlalchemy import update
    from packages.core.db.session import AsyncSessionLocal
    from packages.core.db.models import Resume

    while True:
        try:
            async with AsyncSessionLocal() as session:
                today = date.today()
                await session.execute(
                    update(Resume)
                    .where(Resume.is_expired == False, Resume.expires_at < today)
                    .values(is_expired=True)
                )
                await session.commit()
        except Exception as exc:
            logging.error("Expiry worker error: %s", exc)
        await asyncio.sleep(_EXPIRY_INTERVAL_SECONDS)


app = FastAPI(
    title="AI Talent Platform",
    version="0.1.0",
    description="Two-sided resume screening platform — Recruiters + Candidates",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,       prefix="/auth",       tags=["auth"])
app.include_router(jobs.router,       prefix="/jobs",       tags=["jobs"])
app.include_router(resumes.router,    prefix="/resumes",    tags=["resumes"])
app.include_router(scores.router,     prefix="/scores",     tags=["scores"])
app.include_router(candidates.router, prefix="/candidates", tags=["candidates"])


@app.get("/health")
async def health():
    return {"status": "ok"}
