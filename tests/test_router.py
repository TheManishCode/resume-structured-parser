"""tests/test_router.py — ModelRouter unit tests (no DB, no real models)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from packages.core.router.router import (
    ModelRouter, ScoredBy, Status, ScoringResult,
    LOCAL_CONFIDENCE_THRESHOLD, DISAGREEMENT_THRESHOLD,
)


def _make_router(local_score=0.8, local_confidence=0.9, cloud_score=0.82,
                 primary_fails=False, fallback_fails=False):
    local = MagicMock()
    local.score = AsyncMock(return_value={
        "score": local_score, "confidence": local_confidence,
        "justification": "local says ok",
    })

    primary = MagicMock()
    if primary_fails:
        primary.score = AsyncMock(side_effect=RuntimeError("primary down"))
    else:
        primary.score = AsyncMock(return_value={
            "score": cloud_score, "justification": "cloud says ok",
        })
    primary.is_available.return_value = True

    fallback = MagicMock()
    if fallback_fails:
        fallback.score = AsyncMock(side_effect=RuntimeError("fallback down"))
    else:
        fallback.score = AsyncMock(return_value={
            "score": cloud_score, "justification": "fallback says ok",
        })
    fallback.is_available.return_value = True

    queue = asyncio.Queue()
    return ModelRouter(local=local, primary=primary, fallback=fallback,
                       background_retry_queue=queue), queue


@pytest.mark.asyncio
async def test_high_confidence_local_no_escalation():
    router, _ = _make_router(local_confidence=0.95)
    result = await router.score("resume", "jd")
    assert result.scored_by == ScoredBy.local
    assert result.status == Status.confirmed
    # primary should not have been called
    assert not router._primary.score.called


@pytest.mark.asyncio
async def test_low_confidence_escalates_to_cloud():
    router, _ = _make_router(local_confidence=0.30, cloud_score=0.75)
    result = await router.score("resume", "jd")
    assert result.scored_by == ScoredBy.claude
    assert result.status == Status.confirmed


@pytest.mark.asyncio
async def test_force_cloud_always_escalates():
    router, _ = _make_router(local_confidence=0.99)
    result = await router.score("resume", "jd", force_cloud=True)
    assert result.scored_by == ScoredBy.claude


@pytest.mark.asyncio
async def test_disagreement_flagged():
    # local=0.3, cloud=0.9 → delta=0.6 > DISAGREEMENT_THRESHOLD
    router, _ = _make_router(local_score=0.3, local_confidence=0.2, cloud_score=0.9)
    result = await router.score("resume", "jd")
    assert result.needs_review is True
    assert result.disagreement_delta is not None


@pytest.mark.asyncio
async def test_no_disagreement_when_close():
    router, _ = _make_router(local_score=0.75, local_confidence=0.2, cloud_score=0.80)
    result = await router.score("resume", "jd")
    assert result.needs_review is False


@pytest.mark.asyncio
async def test_primary_failure_falls_back_to_groq():
    router, queue = _make_router(local_confidence=0.2, primary_fails=True, cloud_score=0.7)
    result = await router.score("resume", "jd", candidate_id="CAND_001")
    assert result.scored_by == ScoredBy.fallback
    assert result.status == Status.provisional
    assert not queue.empty()  # retry scheduled


@pytest.mark.asyncio
async def test_both_cloud_fail_returns_local():
    router, _ = _make_router(local_score=0.55, local_confidence=0.2,
                              primary_fails=True, fallback_fails=True)
    result = await router.score("resume", "jd")
    assert result.scored_by == ScoredBy.local


@pytest.mark.asyncio
async def test_retry_upgrades_provisional_to_confirmed():
    router, _ = _make_router(cloud_score=0.72)
    result = await router.retry_with_primary("resume", "jd", previous_score=0.70)
    assert result.status == Status.confirmed  # delta < DISAGREEMENT_THRESHOLD
    assert result.scored_by == ScoredBy.claude


@pytest.mark.asyncio
async def test_retry_marks_re_scored_on_divergence():
    router, _ = _make_router(cloud_score=0.90)
    result = await router.retry_with_primary("resume", "jd", previous_score=0.40)
    assert result.status == Status.re_scored
