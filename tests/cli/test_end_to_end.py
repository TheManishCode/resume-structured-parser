"""tests/cli/test_end_to_end.py — pipeline integration and CSV validator tests."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
from packages.core.scoring import schema as _schema
from packages.core.scoring.behavioral import behavioral_score
from packages.core.scoring.disqualifiers import disqualifier_check
from packages.core.scoring.integrity import integrity_check
from packages.core.scoring.reasoning import generate_reasoning
from packages.core.scoring.role_taxonomy import role_taxonomy
from packages.core.scoring.scoring import compute_score

_VALIDATE = Path(__file__).parent.parent.parent / "validate_submission.py"
_OUT_CSV = Path(__file__).parent / "_test_output_sample.csv"


def _make_ml_candidate(cid: str, yoe: float = 5.0, desc: str = "") -> dict:
    return {
        "candidate_id": cid,
        "profile": {
            "anonymized_name": "ANON", "headline": "", "summary": "",
            "location": "Bangalore", "country": "India",
            "years_of_experience": yoe,
            "current_title": "ML Engineer",
            "current_company": "Swiggy", "current_company_size": "1001-5000",
            "current_industry": "Technology",
        },
        "career_history": [{
            "company": "Swiggy", "title": "ML Engineer",
            "start_date": "2021-01-01", "end_date": None,
            "duration_months": int(yoe * 12), "is_current": True,
            "industry": "Technology", "company_size": "1001-5000",
            "description": desc or "pytorch nlp ranking fine-tuning bert gradient inference.",
        }],
        "education": [],
        "skills": [],
        "redrob_signals": {
            "profile_completeness_score": 85, "signup_date": "2021-01-01",
            "last_active_date": "2026-05-27", "open_to_work_flag": True,
            "profile_views_received_30d": 15, "applications_submitted_30d": 2,
            "recruiter_response_rate": 0.80, "avg_response_time_hours": 10.0,
            "skill_assessment_scores": {}, "connection_count": 300,
            "endorsements_received": 60, "notice_period_days": 30,
            "expected_salary_range_inr_lpa": {"min": 25, "max": 50},
            "preferred_work_mode": "hybrid", "willing_to_relocate": True,
            "github_activity_score": 55, "search_appearance_30d": 30,
            "saved_by_recruiters_30d": 7, "interview_completion_rate": 0.90,
            "offer_acceptance_rate": 0.75, "verified_email": True,
            "verified_phone": True, "linkedin_connected": True,
        },
    }


def _make_non_ml_candidate(cid: str) -> dict:
    c = _make_ml_candidate(cid)
    c["profile"]["current_title"] = "Business Analyst"
    c["career_history"][0]["title"] = "Business Analyst"
    c["career_history"][0]["description"] = "Prepared reports and dashboards for stakeholders."
    return c


def _score_candidate(c: dict) -> dict:
    tax = role_taxonomy(c)
    integ = integrity_check(c)
    dq = disqualifier_check(c)
    beh = behavioral_score(c)
    sc = compute_score(candidate=c, taxonomy_result=tax, integrity_result=integ,
                       disqualifier_result=dq, behavioral_result=beh)
    rsn = generate_reasoning(candidate=c, taxonomy_result=tax, disqualifier_result=dq,
                              behavioral_result=beh, score_result=sc)
    return {"candidate_id": _schema.get_candidate_id(c), "score": sc["score"], "reasoning": rsn}


# Build synthetic corpus: 10 ML candidates + 10 non-ML
_CORPUS = (
    [_make_ml_candidate(f"CAND_{i:07d}", yoe=float(3 + i % 8)) for i in range(1, 11)]
    + [_make_non_ml_candidate(f"CAND_{i:07d}") for i in range(11, 21)]
)


def test_pipeline_runs_on_corpus():
    results = [_score_candidate(c) for c in _CORPUS]
    assert len(results) == 20
    for r in results:
        assert "candidate_id" in r
        assert 0.0 <= r["score"] <= 1.0
        assert isinstance(r["reasoning"], str) and len(r["reasoning"]) > 5


def test_scores_are_deterministic():
    r1 = [_score_candidate(c) for c in _CORPUS]
    r2 = [_score_candidate(c) for c in _CORPUS]
    for a, b in zip(r1, r2):
        assert a["score"] == b["score"]
        assert a["reasoning"] == b["reasoning"]


def test_ml_candidate_outranks_non_ml():
    results = [_score_candidate(c) for c in _CORPUS]
    ml_scores = [r["score"] for r in results[:10]]
    non_ml_scores = [r["score"] for r in results[10:]]
    assert min(ml_scores) > max(non_ml_scores), (
        f"Worst ML score {min(ml_scores):.4f} did not beat best non-ML score {max(non_ml_scores):.4f}"
    )


def test_reasoning_contains_title():
    results = [_score_candidate(c) for c in _CORPUS[:10]]
    for r, c in zip(results, _CORPUS[:10]):
        title = _schema.get_current_title(c)
        assert title in r["reasoning"], f"{r['candidate_id']}: '{title}' not in reasoning"


def test_csv_output_passes_validator():
    results = [_score_candidate(c) for c in _CORPUS]
    # Pad to 100 rows with synthetic IDs
    padded = list(results)
    counter = 9000000
    while len(padded) < 100:
        padded.append({
            "candidate_id": f"CAND_{counter:07d}",
            "score": 0.0001,
            "reasoning": "Not in scope.",
        })
        counter += 1

    padded.sort(key=lambda r: (-r["score"], r["candidate_id"]))
    padded = padded[:100]

    try:
        with open(_OUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["candidate_id", "rank", "score", "reasoning"])
            for rank, row in enumerate(padded, start=1):
                writer.writerow([row["candidate_id"], rank, f"{row['score']:.6f}", row["reasoning"]])

        result = subprocess.run(
            [sys.executable, str(_VALIDATE), str(_OUT_CSV)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Validation failed:\n{result.stdout}\n{result.stderr}"
        assert "valid" in result.stdout.lower()
    finally:
        if _OUT_CSV.exists():
            _OUT_CSV.unlink()
