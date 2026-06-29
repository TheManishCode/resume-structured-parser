"""core.scoring — deterministic local scoring engine.

Exposed surface:
  score_candidate(candidate: dict) -> ScoringResult
  generate_reasoning(candidate, taxonomy_result, dq_result, beh_result, score_result) -> str
"""
from .scoring import score_candidate, compute_score
from .reasoning import generate_reasoning

__all__ = ["score_candidate", "compute_score", "generate_reasoning"]
