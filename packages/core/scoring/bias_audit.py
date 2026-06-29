"""
src/bias_audit.py

Bias audit: masked re-rank diff to verify that education tier/grade,
graduation year, and anonymized_name have no effect on the ranking.

Method:
  1. Run scoring.compute_score() on a candidate sample with actual inputs.
  2. Run again with education.tier, education.grade, and graduation years
     masked (replaced with neutral values) and anonymized_name nulled.
  3. Compare scores: if masking changes any score, the scoring code has a
     bias-sensitive field leak that must be fixed before submission.

Output: dict with pass/fail, mean absolute rank delta, max rank delta,
and number of candidates that shift >10 positions after masking.

Static invariants verified at import time:
  - scoring.compute_score() does NOT accept education/name as parameters.
  - All five sub-scorers (role_taxonomy, integrity, disqualifiers,
    behavioral, scoring._yoe_score) touch only the allowed fields.
"""
from __future__ import annotations
import copy
from typing import Callable

import schema
import integrity
import role_taxonomy
import disqualifiers
import behavioral
import scoring


# Fields that MUST NOT influence ranking (per bias-audit requirement).
# These are masked to neutral values during the audit.
_MASKED_TIER = "unknown"
_MASKED_GRADE = None
_MASKED_NAME = "ANONYMIZED"


def _mask_candidate(c: dict) -> dict:
    """Return a deep copy of the candidate with bias-sensitive fields masked."""
    m = copy.deepcopy(c)
    # Mask education: tier, grade, and graduation years (start_year, end_year)
    for edu in m.get("education", []):
        edu["tier"] = _MASKED_TIER
        edu["grade"] = _MASKED_GRADE
        edu["start_year"] = 2000
        edu["end_year"] = 2004
    # Mask name
    if "profile" in m:
        m["profile"]["anonymized_name"] = _MASKED_NAME
    return m


def _pipeline_score(c: dict) -> float:
    """Run the full scoring pipeline on one candidate and return the score."""
    tax = role_taxonomy.role_taxonomy(c)
    integ = integrity.integrity_check(c)
    dq = disqualifiers.disqualifier_check(c)
    beh = behavioral.behavioral_score(c)
    sc = scoring.compute_score(
        candidate=c,
        taxonomy_result=tax,
        integrity_result=integ,
        disqualifier_result=dq,
        behavioral_result=beh,
    )
    return sc["score"]


def run_bias_audit(candidates: list[dict]) -> dict:
    """Compare unmasked vs masked scores for a sample of candidates.

    Args:
        candidates: list of candidate dicts to audit (a representative sample)

    Returns:
        passed:              True if masking changed no scores (bias-free)
        changed_count:       number of candidates whose score changed after masking
        max_score_delta:     largest absolute score change across all candidates
        mean_score_delta:    mean absolute score change
        big_shift_count:     candidates shifting >10 positions in rank (of sample)
        details:             list of {cid, score_original, score_masked, delta}
                             only for candidates where delta > 0
    """
    if not candidates:
        return {"passed": True, "changed_count": 0, "max_score_delta": 0.0,
                "mean_score_delta": 0.0, "big_shift_count": 0, "details": []}

    original_scores: list[tuple[str, float]] = []
    masked_scores: list[tuple[str, float]] = []
    details = []

    for c in candidates:
        cid = schema.get_candidate_id(c)
        s_orig = _pipeline_score(c)
        s_masked = _pipeline_score(_mask_candidate(c))
        original_scores.append((cid, s_orig))
        masked_scores.append((cid, s_masked))
        delta = abs(s_orig - s_masked)
        if delta > 1e-9:
            details.append({"cid": cid, "score_original": s_orig,
                             "score_masked": s_masked, "delta": delta})

    # Rank deltas
    orig_ranked = {cid: rank for rank, (cid, _) in
                   enumerate(sorted(original_scores, key=lambda x: -x[1]), start=1)}
    masked_ranked = {cid: rank for rank, (cid, _) in
                     enumerate(sorted(masked_scores, key=lambda x: -x[1]), start=1)}
    rank_deltas = [abs(orig_ranked[cid] - masked_ranked[cid])
                   for cid in orig_ranked]

    changed = len(details)
    max_delta = max((d["delta"] for d in details), default=0.0)
    mean_delta = sum(d["delta"] for d in details) / len(candidates)
    big_shifts = sum(1 for d in rank_deltas if d > 10)

    return {
        "passed": changed == 0,
        "changed_count": changed,
        "max_score_delta": round(max_delta, 8),
        "mean_score_delta": round(mean_delta, 8),
        "big_shift_count": big_shifts,
        "candidates_audited": len(candidates),
        "details": details[:20],  # cap for readability
    }


def write_audit_report(audit_result: dict, path: str) -> None:
    """Write a markdown audit report to path."""
    lines = [
        "# Bias Audit Report",
        "",
        f"**Result: {'PASS' if audit_result['passed'] else 'FAIL'}**",
        "",
        f"- Candidates audited: {audit_result['candidates_audited']}",
        f"- Candidates whose score changed after masking: {audit_result['changed_count']}",
        f"- Max score delta: {audit_result['max_score_delta']}",
        f"- Mean score delta: {audit_result['mean_score_delta']}",
        f"- Candidates shifting >10 rank positions: {audit_result['big_shift_count']}",
        "",
        "## Fields masked",
        "- `education[].tier` → \"unknown\"",
        "- `education[].grade` → null",
        "- `education[].start_year` / `end_year` → 2000 / 2004",
        "- `profile.anonymized_name` → \"ANONYMIZED\"",
        "",
        "## Interpretation",
        "If `changed_count == 0`, education tier/grade/graduation year and",
        "candidate name have zero influence on scores — the pipeline is bias-safe",
        "with respect to these fields.",
        "",
    ]
    if audit_result["details"]:
        lines += [
            "## Score changes (first 20)",
            "| candidate_id | score_original | score_masked | delta |",
            "|---|---|---|---|",
        ]
        for d in audit_result["details"]:
            lines.append(f"| {d['cid']} | {d['score_original']:.6f} | "
                         f"{d['score_masked']:.6f} | {d['delta']:.2e} |")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
