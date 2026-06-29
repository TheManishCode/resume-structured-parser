"""
packages/core/router/router.py

Model Router — single entry point for ALL scoring.
No business logic calls a specific model directly; everything goes through here.

Fallback chain:
  Tier 0 — Local OSS (Ollama): bulk first-pass, always attempted
  Tier 1 — Claude:             primary cloud reasoning
  Tier 2 — Groq (Llama/Mixtral): fallback on rate-limit / timeout / error

Escalation policy:
  - Tier 0 runs on every resume (cheap, fast, deterministic).
  - Tier 1/2 escalate ONLY when:
      a) local_confidence < LOCAL_CONFIDENCE_THRESHOLD, OR
      b) candidate is in the top-N pool for a given job (controlled by caller)
  - When Tier 1 fails, save result as scored_by=fallback, status=provisional,
    schedule a background retry via BackgroundTasks.
  - If primary's re-score differs meaningfully from fallback's, status=re_scored.
  - If they match, status=confirmed. No user-facing errors.

Disagreement detection:
  - When local and cloud scores differ by > DISAGREEMENT_THRESHOLD,
    the result is flagged: needs_review=True.
  - This is the system's signature feature — we don't silently average.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ── Configuration (overridden via env vars) ───────────────────────────────────

LOCAL_CONFIDENCE_THRESHOLD = float(os.getenv("LOCAL_CONFIDENCE_THRESHOLD", "0.70"))
DISAGREEMENT_THRESHOLD     = float(os.getenv("DISAGREEMENT_THRESHOLD", "0.20"))
CLOUD_TIMEOUT_SECONDS      = float(os.getenv("CLOUD_TIMEOUT_SECONDS", "15.0"))
TOP_N_ESCALATE             = int(os.getenv("TOP_N_ESCALATE", "20"))


class ScoredBy(str, Enum):
    local    = "local"
    claude   = "claude"
    groq     = "groq"
    fallback = "fallback"  # groq used when claude failed; retry pending


class Status(str, Enum):
    provisional = "provisional"  # fallback result; primary retry scheduled
    confirmed   = "confirmed"    # primary re-scored; matched fallback
    re_scored   = "re_scored"    # primary re-scored; diverged from fallback


@dataclass
class ScoringResult:
    score:          float
    justification:  str
    scored_by:      ScoredBy
    status:         Status
    local_score:    Optional[float] = None
    local_confidence: Optional[float] = None
    cloud_score:    Optional[float] = None
    needs_review:   bool = False
    disagreement_delta: Optional[float] = None
    previous_score: Optional[float] = None    # populated on re-score
    latency_ms:     Optional[float] = None
    extra:          dict = field(default_factory=dict)


# ── Model backend stubs (replaced by real implementations in adapters/) ───────

class LocalModel:
    """Ollama-backed OSS model for bulk first-pass scoring."""

    async def score(self, resume_text: str, job_description: str) -> dict:
        """Returns {"score": float, "confidence": float, "justification": str}."""
        raise NotImplementedError

    def is_available(self) -> bool:
        raise NotImplementedError


class CloudModel:
    """Base class for Claude and Groq adapters."""

    async def score(self, resume_text: str, job_description: str,
                    local_result: dict | None = None) -> dict:
        """Returns {"score": float, "justification": str}."""
        raise NotImplementedError

    def is_available(self) -> bool:
        raise NotImplementedError


# ── Router ─────────────────────────────────────────────────────────────────────

class ModelRouter:
    """Single interface for all scoring.  No caller touches a model directly."""

    def __init__(
        self,
        local: LocalModel,
        primary: CloudModel,
        fallback: CloudModel,
        background_retry_queue=None,  # asyncio.Queue or celery task (injected)
    ) -> None:
        self._local    = local
        self._primary  = primary
        self._fallback = fallback
        self._retry_q  = background_retry_queue

    async def score(
        self,
        resume_text: str,
        job_description: str,
        force_cloud: bool = False,
        candidate_id: str | None = None,
    ) -> ScoringResult:
        """Score one resume against one JD.

        Args:
            resume_text:      Full extracted text of the resume.
            job_description:  JD text.
            force_cloud:      True for top-N candidates where cloud is always run.
            candidate_id:     Passed through to retry queue for bookkeeping.

        Returns:
            ScoringResult with score, justification, scored_by, status, and
            needs_review flag when local/cloud signals disagree.
        """
        t0 = time.monotonic()
        local_result = await self._run_local(resume_text, job_description)
        local_score      = local_result["score"]
        local_confidence = local_result["confidence"]

        escalate = force_cloud or (local_confidence < LOCAL_CONFIDENCE_THRESHOLD)

        if not escalate:
            return ScoringResult(
                score=local_score,
                justification=local_result.get("justification", ""),
                scored_by=ScoredBy.local,
                status=Status.confirmed,
                local_score=local_score,
                local_confidence=local_confidence,
                latency_ms=(time.monotonic() - t0) * 1000,
            )

        # ── Cloud escalation ─────────────────────────────────────────────────
        cloud_result = await self._run_cloud_with_fallback(
            resume_text, job_description, local_result, candidate_id
        )

        cloud_score = cloud_result["score"]
        scored_by   = cloud_result["scored_by"]
        status      = cloud_result["status"]

        # Disagreement detection
        delta        = abs(local_score - cloud_score)
        needs_review = delta > DISAGREEMENT_THRESHOLD

        if needs_review:
            logger.warning(
                "Disagreement: local=%.3f cloud=%.3f delta=%.3f candidate=%s",
                local_score, cloud_score, delta, candidate_id,
            )

        return ScoringResult(
            score=cloud_score,
            justification=cloud_result.get("justification", ""),
            scored_by=scored_by,
            status=status,
            local_score=local_score,
            local_confidence=local_confidence,
            cloud_score=cloud_score,
            needs_review=needs_review,
            disagreement_delta=round(delta, 4) if needs_review else None,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    async def retry_with_primary(
        self,
        resume_text: str,
        job_description: str,
        previous_score: float,
        candidate_id: str | None = None,
    ) -> ScoringResult:
        """Called by background retry job to upgrade provisional → confirmed/re_scored."""
        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self._primary.score(resume_text, job_description),
                timeout=CLOUD_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            logger.error("Primary retry failed for %s: %s", candidate_id, exc)
            return ScoringResult(
                score=previous_score,
                justification="",
                scored_by=ScoredBy.fallback,
                status=Status.provisional,
                previous_score=previous_score,
                latency_ms=(time.monotonic() - t0) * 1000,
            )

        new_score = result["score"]
        delta     = abs(new_score - previous_score)
        status    = Status.re_scored if delta > DISAGREEMENT_THRESHOLD else Status.confirmed

        return ScoringResult(
            score=new_score,
            justification=result.get("justification", ""),
            scored_by=ScoredBy.claude,
            status=status,
            previous_score=previous_score,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    async def _run_local(self, resume_text: str, jd: str) -> dict:
        try:
            return await self._local.score(resume_text, jd)
        except Exception as exc:
            logger.warning("Local model failed (%s); defaulting to low-confidence stub", exc)
            return {"score": 0.5, "confidence": 0.0, "justification": ""}

    async def _run_cloud_with_fallback(
        self,
        resume_text: str,
        jd: str,
        local_result: dict,
        candidate_id: str | None,
    ) -> dict:
        # Try primary (Claude)
        try:
            result = await asyncio.wait_for(
                self._primary.score(resume_text, jd, local_result),
                timeout=CLOUD_TIMEOUT_SECONDS,
            )
            return {**result, "scored_by": ScoredBy.claude, "status": Status.confirmed}
        except Exception as exc:
            logger.warning("Primary cloud failed (%s); using fallback", exc)

        # Try fallback (Groq)
        try:
            result = await asyncio.wait_for(
                self._fallback.score(resume_text, jd, local_result),
                timeout=CLOUD_TIMEOUT_SECONDS,
            )
            # Schedule primary retry
            if self._retry_q is not None:
                await self._retry_q.put({
                    "candidate_id": candidate_id,
                    "resume_text":  resume_text,
                    "jd":           jd,
                    "fallback_score": result["score"],
                })
            return {**result, "scored_by": ScoredBy.fallback, "status": Status.provisional}
        except Exception as exc:
            logger.error("Fallback cloud also failed (%s); returning local", exc)
            return {
                "score":         local_result["score"],
                "justification": local_result.get("justification", ""),
                "scored_by":     ScoredBy.local,
                "status":        Status.confirmed,
            }
