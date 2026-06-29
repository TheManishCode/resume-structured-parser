"""
src/behavioral.py

Candidate availability/engagement modifier from redrob_signals.

Output: availability_modifier float [0.0, 1.0] applied MULTIPLICATIVELY in
scoring.py (never additively — per JD framing and engineering spec).

Calibrated via probe_behavioral.py on the full 100K candidates.jsonl:
  recruiter_response_rate:   p10=0.14  p50=0.44  p90=0.73  (0-1 directly)
  interview_completion_rate: p10=0.38  p50=0.62  p90=0.85  (floor 0.30 in data)
  avg_response_time_hours:   p10=31.6  p50=129.9 p90=240.4 (lower = better)
  days_since_last_active:    p10=53    p50=138   p90=239   (lower = better)
                             floor=33, ceiling=273 (empirical range in dataset)
  open_to_work_flag:         35% True, 65% False (binary signal)

Sentinel values:
  offer_acceptance_rate = -1: not included in this module (no signal without
    offer history); github_activity_score = -1: no GitHub linked.
  Both are absent from the 5 specified behavioral components.

Components and normalisation:
  open_to_work:    True→1.0, False→0.4  (False is not disqualifying)
  response_rate:   recruiter_response_rate as-is (0–1)
  interview_rate:  (rate - 0.30) / 0.70  (rescales the [0.30, 1.0] empirical
                   range to [0, 1]; floor from dataset)
  recency:         (273 - days_since_active) / 240  (273=max, 33=min, 240=span)
  response_speed:  (280 - avg_hours) / 278          (280=max, 2=min, 278=span)
  All components clamped to [0.0, 1.0].

Weighted average then clamped to [0.2, 1.0] (floor prevents a single bad
signal from collapsing the multiplier entirely).
"""
from __future__ import annotations
from datetime import date

import schema

# ── Calibration constants (from probe_behavioral.py) ─────────────────────────

_DAYS_MIN: float = 33.0     # p0 of days_since_last_active
_DAYS_MAX: float = 273.0    # p100 of days_since_last_active

_HOURS_MIN: float = 2.0     # p0 of avg_response_time_hours
_HOURS_MAX: float = 280.0   # p100 of avg_response_time_hours

_ICR_FLOOR: float = 0.30    # empirical minimum of interview_completion_rate

# ── Component weights (sum = 1.0) ────────────────────────────────────────────

_WEIGHTS = {
    "open_to_work": 0.25,
    "recruiter_response": 0.25,
    "interview_completion": 0.20,
    "recency": 0.20,
    "response_speed": 0.10,
}

_MODIFIER_FLOOR = 0.2   # never collapse to zero for a bad-signal candidate
_MODIFIER_CEIL = 1.0    # no upward boost beyond fit score

_TODAY = date(2026, 6, 29)


def _open_to_work_score(sig: dict) -> float:
    return 1.0 if sig.get("open_to_work_flag", False) else 0.4


def _recruiter_response_score(sig: dict) -> float:
    return float(sig.get("recruiter_response_rate", 0.0) or 0.0)


def _interview_completion_score(sig: dict) -> float:
    rate = float(sig.get("interview_completion_rate", _ICR_FLOOR) or _ICR_FLOOR)
    return max(0.0, min(1.0, (rate - _ICR_FLOOR) / (1.0 - _ICR_FLOOR)))


def _recency_score(sig: dict) -> float:
    last = schema.parse_date(sig.get("last_active_date", ""))
    if last is None:
        return 0.5  # neutral when unknown
    days = (_TODAY - last).days
    span = _DAYS_MAX - _DAYS_MIN
    return max(0.0, min(1.0, (_DAYS_MAX - days) / span))


def _response_speed_score(sig: dict) -> float:
    hours = float(sig.get("avg_response_time_hours", _HOURS_MAX) or _HOURS_MAX)
    span = _HOURS_MAX - _HOURS_MIN
    return max(0.0, min(1.0, (_HOURS_MAX - hours) / span))


def behavioral_score(c: dict) -> dict:
    """Compute availability modifier from a candidate's redrob_signals.

    Returns:
        availability_modifier: float [0.2, 1.0] — multiply into final score
        component_scores:      dict of individual 0-1 sub-scores
    """
    sig = schema.get_redrob_signals(c)

    components = {
        "open_to_work": _open_to_work_score(sig),
        "recruiter_response": _recruiter_response_score(sig),
        "interview_completion": _interview_completion_score(sig),
        "recency": _recency_score(sig),
        "response_speed": _response_speed_score(sig),
    }

    modifier = sum(_WEIGHTS[k] * v for k, v in components.items())
    modifier = max(_MODIFIER_FLOOR, min(_MODIFIER_CEIL, modifier))

    return {
        "availability_modifier": round(modifier, 4),
        "component_scores": {k: round(v, 4) for k, v in components.items()},
    }
