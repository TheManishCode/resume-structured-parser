"""
src/scoring.py

Composite score assembler for the redrob-ranker pipeline.

Pure function: takes pre-computed sub-scores (from all other modules) and
weights (loaded from config/weights.yaml) and returns a final score.
No I/O, no randomness — fully deterministic, required for reproducibility.

Bias-safety guarantees (static, enforced by the function signatures):
  - education.tier, education.grade, graduation years: NOT read by any
    sub-scorer called here. scoring.py receives only pre-computed dicts.
  - anonymized_name: NOT touched.
  - location: NOT used as a hard filter.
  These are verified dynamically in bias_audit.py (masked re-rank diff).

Formula:
  yoe_score  = piecewise function of years_of_experience
  base_fit   = w_role * role_relevance + w_yoe * yoe_score
  final_score = base_fit
               * integrity_score          # 0.05 if honeypot, 1.0 otherwise
               * disqualifier_multiplier  # compound penalty from disqualifiers
               * availability_modifier    # behavioral engagement signal
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml
from . import schema

_WEIGHTS_PATH = Path(__file__).parent / "weights.yaml"

# ── Weight loading (cached at import time) ────────────────────────────────────

def _load_weights(path: Path = _WEIGHTS_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


_WEIGHTS: dict = _load_weights()


def reload_weights(path: Path = _WEIGHTS_PATH) -> None:
    """Reload weights from disk (useful during calibration runs)."""
    global _WEIGHTS
    _WEIGHTS = _load_weights(path)


# ── YOE scoring ───────────────────────────────────────────────────────────────

def _yoe_score(years: float) -> float:
    """Piecewise linear YOE score from config/weights.yaml breakpoints.

    Calibrated against ML-adjacent pool (probe_yoe.py):
      p10=3.4yr, p50=5.1yr, p90=6.7yr — most ML candidates in 3-8yr range.
    JD targets 'Senior AI Engineer' → 5-8yr is the sweet spot (score 0.82-0.95).
    """
    breakpoints = _WEIGHTS.get("yoe_breakpoints", [])
    prev_max = 0.0
    prev_score = 0.0
    for bp in breakpoints:
        max_y: float = bp["max_years"]
        tgt_score: float = bp["score"]
        if years <= max_y:
            # Linearly interpolate between (prev_max, prev_score) and (max_y, tgt_score)
            if max_y == prev_max:
                return tgt_score
            frac = (years - prev_max) / (max_y - prev_max)
            return prev_score + frac * (tgt_score - prev_score)
        prev_max = max_y
        prev_score = tgt_score
    return prev_score  # at or beyond last breakpoint


# ── Main scoring function ─────────────────────────────────────────────────────

def compute_score(
    candidate: dict,
    taxonomy_result: dict,
    integrity_result: dict,
    disqualifier_result: dict,
    behavioral_result: dict,
) -> dict:
    """Compute composite score from all pre-computed sub-scores.

    Args:
        candidate:           raw candidate dict (for years_of_experience only)
        taxonomy_result:     output of role_taxonomy.role_taxonomy()
        integrity_result:    output of integrity.integrity_check()
        disqualifier_result: output of disqualifiers.disqualifier_check()
        behavioral_result:   output of behavioral.behavioral_score()

    Returns:
        score:        float [0, 1] — final composite score
        sub_scores:   dict of intermediate values for debugging and CSV audit trail
    """
    bf_weights = _WEIGHTS.get("base_fit", {})
    w_role: float = bf_weights.get("role_relevance", 0.70)
    w_yoe: float = bf_weights.get("yoe_score", 0.30)

    role_rel: float = taxonomy_result.get("role_relevance", 0.0)
    years: float = schema.get_years_experience(candidate)
    yoe_s: float = _yoe_score(years)

    integrity_s: float = integrity_result.get("integrity_score", 1.0)
    dq_multiplier: float = disqualifier_result.get("disqualifier_multiplier", 1.0)
    avail_mod: float = behavioral_result.get("availability_modifier", 1.0)

    # Hard gate: zero role relevance → no score, regardless of YOE or availability.
    # Without this, a Business Analyst with 15yr experience could outscore a
    # junior ML Engineer on the YOE component alone, which is wrong.
    if role_rel == 0.0:
        base_fit = 0.0
        final_score = 0.0
    else:
        base_fit = w_role * role_rel + w_yoe * yoe_s
        final_score = base_fit * integrity_s * dq_multiplier * avail_mod

    # Clamp to [0, 1] (should never exceed 1.0 given the formula, but be safe)
    final_score = max(0.0, min(1.0, final_score))

    return {
        "candidate_id": schema.get_candidate_id(candidate),
        "score": round(final_score, 6),
        "sub_scores": {
            "role_relevance": round(role_rel, 4),
            "yoe_score": round(yoe_s, 4),
            "years_of_experience": round(years, 1),
            "base_fit": round(base_fit, 4),
            "integrity_score": round(integrity_s, 4),
            "disqualifier_multiplier": round(dq_multiplier, 4),
            "availability_modifier": round(avail_mod, 4),
        },
    }


def score_candidate(candidate: dict) -> dict:
    """Convenience wrapper: run all sub-scorers and return composite score."""
    from . import integrity as _integ
    from . import role_taxonomy as _tax
    from . import disqualifiers as _dq
    from . import behavioral as _beh

    return compute_score(
        candidate=candidate,
        taxonomy_result=_tax.role_taxonomy(candidate),
        integrity_result=_integ.integrity_check(candidate),
        disqualifier_result=_dq.disqualifier_check(candidate),
        behavioral_result=_beh.behavioral_score(candidate),
    )
