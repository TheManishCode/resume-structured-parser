"""
src/integrity.py

Honeypot / internal-consistency detection.

Calibrated against the real candidates.jsonl (100,000 rows) by probing
distributions before picking thresholds — see HANDOFF_CONTEXT.md / build log.

Two clean, well-separated signals found (no overlap between them):
  A) "expert" proficiency claimed on a skill used < 6 months
     -> 21 candidates in real data
  B) years_of_experience disagrees with summed career_history duration by
     more than 24 months (normal data noise tops out at ~3.4 months at p99,
     then there's a clean gap before a long tail starting at 24+ months)
     -> 48 candidates in real data
  Union: 69 candidates, close to the documented ~80 honeypots.

A third candidate pattern (skill duration_months exceeding total years of
experience) was tested and rejected — it fired on 9,231 candidates, clearly
just synthetic-data looseness, not a honeypot signal. Documented here so a
future maintainer doesn't re-add it without re-checking.

Design: candidates are never deleted, only scored. integrity_score is
continuous (1.0 = no issues found) and multiplies into the final composite
score in scoring.py, so the practical effect is honeypots sink to the
bottom of the ranking rather than being silently dropped.
"""
from __future__ import annotations
from datetime import date
from . import schema

EXPERT_MIN_MONTHS = 6
YOE_MISMATCH_THRESHOLD_MONTHS = 24


def check_expert_low_duration(c: dict) -> list[str]:
    flags = []
    for s in schema.get_skills(c):
        dm = s.get("duration_months")
        if (
            s.get("proficiency") == "expert"
            and isinstance(dm, (int, float))
            and dm < EXPERT_MIN_MONTHS
        ):
            flags.append(f"expert_proficiency_low_duration:{s.get('name')}:{dm}mo")
    return flags


def check_experience_mismatch(c: dict) -> list[str]:
    yoe = schema.get_years_experience(c)
    summed = schema.sum_career_duration_months(c)
    diff = abs(yoe * 12 - summed)
    if diff > YOE_MISMATCH_THRESHOLD_MONTHS:
        return [f"yoe_career_history_mismatch:{diff:.0f}mo_diff"]
    return []


def check_overlapping_roles(c: dict) -> list[str]:
    """Defensive check kept even though it fired 0 times on real data —
    cheap to compute, catches a plausible honeypot pattern not present in
    this particular dataset draw but worth keeping for robustness."""
    roles = schema.get_career_history(c)
    intervals = []
    for r in roles:
        sd = schema.parse_date(r.get("start_date"))
        ed = schema.parse_date(r.get("end_date")) or date(2026, 6, 29)
        if sd:
            intervals.append((sd, ed))
    intervals.sort()
    for i in range(len(intervals) - 1):
        if intervals[i][1] > intervals[i + 1][0]:
            return ["overlapping_career_dates"]
    return []


def integrity_check(c: dict) -> dict:
    flags = (
        check_expert_low_duration(c)
        + check_experience_mismatch(c)
        + check_overlapping_roles(c)
    )
    is_honeypot = len(flags) > 0
    # Continuous score: any flag drops score sharply but not to absolute zero,
    # so a borderline case isn't indistinguishable from a maximally-impossible one.
    integrity_score = 0.05 if is_honeypot else 1.0
    return {
        "candidate_id": schema.get_candidate_id(c),
        "is_honeypot": is_honeypot,
        "integrity_score": integrity_score,
        "integrity_flags": flags,
    }
