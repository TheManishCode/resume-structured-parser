"""tests/cli/test_bias_audit.py — education/name masking and bias audit tests."""
import pytest
from packages.core.scoring.bias_audit import run_bias_audit, _mask_candidate
from packages.core.scoring.scoring import compute_score
from packages.core.scoring.role_taxonomy import role_taxonomy
from packages.core.scoring.integrity import integrity_check
from packages.core.scoring.disqualifiers import disqualifier_check
from packages.core.scoring.behavioral import behavioral_score


def _make_candidate(title="ML Engineer", edu_tier="tier_1", grade="9.5 CGPA",
                    name="Test Candidate", years=5.0):
    return {
        "candidate_id": "CAND_0000001",
        "profile": {
            "anonymized_name": name,
            "headline": "", "summary": "",
            "location": "Bangalore", "country": "India",
            "years_of_experience": years,
            "current_title": title,
            "current_company": "Swiggy", "current_company_size": "1001-5000",
            "current_industry": "Technology",
        },
        "career_history": [{
            "company": "Swiggy", "title": title,
            "start_date": "2022-01-01", "end_date": None,
            "duration_months": 54, "is_current": True,
            "industry": "Technology", "company_size": "1001-5000",
            "description": "pytorch nlp ranking fine-tuning bert gradient.",
        }],
        "education": [{
            "institution": "IIT Bombay",
            "degree": "B.Tech", "field_of_study": "Computer Science",
            "start_year": 2017, "end_year": 2021,
            "grade": grade, "tier": edu_tier,
        }],
        "skills": [],
        "redrob_signals": {
            "profile_completeness_score": 85, "signup_date": "2022-01-01",
            "last_active_date": "2026-05-01", "open_to_work_flag": True,
            "profile_views_received_30d": 20, "applications_submitted_30d": 3,
            "recruiter_response_rate": 0.80, "avg_response_time_hours": 10.0,
            "skill_assessment_scores": {}, "connection_count": 400,
            "endorsements_received": 80, "notice_period_days": 30,
            "expected_salary_range_inr_lpa": {"min": 25, "max": 50},
            "preferred_work_mode": "hybrid", "willing_to_relocate": True,
            "github_activity_score": 55, "search_appearance_30d": 30,
            "saved_by_recruiters_30d": 8, "interview_completion_rate": 0.90,
            "offer_acceptance_rate": 0.75, "verified_email": True,
            "verified_phone": True, "linkedin_connected": True,
        },
    }


def test_mask_replaces_tier():
    c = _make_candidate(edu_tier="tier_1")
    m = _mask_candidate(c)
    for edu in m["education"]:
        assert edu["tier"] == "unknown"
    for edu in c["education"]:
        assert edu["tier"] == "tier_1"


def test_mask_nulls_grade():
    c = _make_candidate(grade="9.5 CGPA")
    m = _mask_candidate(c)
    for edu in m["education"]:
        assert edu["grade"] is None


def test_mask_replaces_graduation_years():
    c = _make_candidate()
    m = _mask_candidate(c)
    for edu in m["education"]:
        assert edu["start_year"] == 2000
        assert edu["end_year"] == 2004


def test_mask_replaces_name():
    c = _make_candidate(name="Priya Sharma")
    m = _mask_candidate(c)
    assert m["profile"]["anonymized_name"] == "ANONYMIZED"
    assert c["profile"]["anonymized_name"] == "Priya Sharma"


def test_mask_does_not_change_title_or_career():
    c = _make_candidate(title="ML Engineer")
    m = _mask_candidate(c)
    assert m["profile"]["current_title"] == "ML Engineer"
    assert m["career_history"][0]["title"] == "ML Engineer"


def test_audit_passes_for_ml_candidate():
    c = _make_candidate(edu_tier="tier_1", grade="9.5 CGPA")
    result = run_bias_audit([c])
    assert result["passed"] is True, (
        f"Bias audit FAILED: {result['changed_count']} candidates changed. "
        f"Details: {result['details']}"
    )
    assert result["max_score_delta"] < 1e-9


def test_audit_passes_for_non_ml_candidate():
    c = _make_candidate(title="Business Analyst", edu_tier="tier_3", grade="6.0 CGPA")
    result = run_bias_audit([c])
    assert result["passed"] is True
    assert result["max_score_delta"] < 1e-9


def test_audit_tier1_vs_tier4_same_score():
    c1 = _make_candidate(edu_tier="tier_1")
    c4 = _make_candidate(edu_tier="tier_4")

    def _score(c):
        return compute_score(
            candidate=c,
            taxonomy_result=role_taxonomy(c),
            integrity_result=integrity_check(c),
            disqualifier_result=disqualifier_check(c),
            behavioral_result=behavioral_score(c),
        )["score"]

    s1 = _score(c1)
    s4 = _score(c4)
    assert s1 == pytest.approx(s4, abs=1e-9), (
        f"Education tier affects score: tier_1={s1:.6f}, tier_4={s4:.6f}"
    )


def test_audit_output_keys():
    c = _make_candidate()
    result = run_bias_audit([c])
    for key in ["passed", "changed_count", "max_score_delta", "mean_score_delta",
                 "big_shift_count", "candidates_audited", "details"]:
        assert key in result


def test_empty_sample_returns_pass():
    result = run_bias_audit([])
    assert result["passed"] is True
    assert result["changed_count"] == 0
