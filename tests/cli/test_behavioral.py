"""tests/cli/test_behavioral.py — availability modifier unit tests."""
import pytest
from packages.core.scoring.behavioral import behavioral_score, _MODIFIER_FLOOR, _MODIFIER_CEIL


def _candidate_with_signals(**kwargs):
    defaults = {
        "open_to_work_flag": True,
        "recruiter_response_rate": 0.8,
        "interview_completion_rate": 0.9,
        "last_active_date": "2026-05-01",
        "avg_response_time_hours": 12.0,
        "signup_date": "2023-01-01",
        "profile_views_received_30d": 10,
        "applications_submitted_30d": 2,
        "skill_assessment_scores": {},
        "connection_count": 300,
        "endorsements_received": 50,
        "notice_period_days": 30,
        "expected_salary_range_inr_lpa": {"min": 20, "max": 40},
        "preferred_work_mode": "hybrid",
        "willing_to_relocate": True,
        "github_activity_score": 50,
        "search_appearance_30d": 20,
        "saved_by_recruiters_30d": 5,
        "offer_acceptance_rate": 0.8,
        "verified_email": True,
        "verified_phone": True,
        "linkedin_connected": True,
    }
    defaults.update(kwargs)
    return {
        "candidate_id": "CAND_0000001",
        "profile": {
            "anonymized_name": "Test", "headline": "", "summary": "",
            "location": "Bangalore", "country": "India",
            "years_of_experience": 5.0, "current_title": "ML Engineer",
            "current_company": "Swiggy", "current_company_size": "1001-5000",
            "current_industry": "Technology",
        },
        "career_history": [{
            "company": "Swiggy", "title": "ML Engineer",
            "start_date": "2023-01-01", "end_date": None,
            "duration_months": 41, "is_current": True,
            "industry": "Technology", "company_size": "1001-5000", "description": "ML work.",
        }],
        "education": [], "skills": [],
        "redrob_signals": defaults,
    }


def test_high_availability_candidate_scores_near_1():
    c = _candidate_with_signals(
        open_to_work_flag=True,
        recruiter_response_rate=0.95,
        interview_completion_rate=1.0,
        last_active_date="2026-05-27",
        avg_response_time_hours=2.1,
    )
    result = behavioral_score(c)
    assert result["availability_modifier"] > 0.85


def test_fully_unavailable_candidate_hits_floor():
    c = _candidate_with_signals(
        open_to_work_flag=False,
        recruiter_response_rate=0.02,
        interview_completion_rate=0.30,
        last_active_date="2025-09-30",
        avg_response_time_hours=280.0,
    )
    result = behavioral_score(c)
    assert result["availability_modifier"] == pytest.approx(_MODIFIER_FLOOR, abs=0.05)


def test_open_to_work_true_vs_false():
    base = dict(
        recruiter_response_rate=0.5,
        interview_completion_rate=0.6,
        last_active_date="2026-04-01",
        avg_response_time_hours=100.0,
    )
    c_yes = _candidate_with_signals(open_to_work_flag=True, **base)
    c_no = _candidate_with_signals(open_to_work_flag=False, **base)
    r_yes = behavioral_score(c_yes)["availability_modifier"]
    r_no = behavioral_score(c_no)["availability_modifier"]
    assert r_yes > r_no


def test_faster_response_time_gives_higher_score():
    c_fast = _candidate_with_signals(avg_response_time_hours=5.0)
    c_slow = _candidate_with_signals(avg_response_time_hours=250.0)
    assert behavioral_score(c_fast)["availability_modifier"] > behavioral_score(c_slow)["availability_modifier"]


def test_recent_activity_gives_higher_score():
    c_recent = _candidate_with_signals(last_active_date="2026-05-27")
    c_stale = _candidate_with_signals(last_active_date="2025-10-01")
    assert behavioral_score(c_recent)["availability_modifier"] > behavioral_score(c_stale)["availability_modifier"]


def test_modifier_always_within_bounds():
    for signal_dict in [
        {"open_to_work_flag": True, "recruiter_response_rate": 1.0,
         "interview_completion_rate": 1.0, "last_active_date": "2026-05-27",
         "avg_response_time_hours": 2.1},
        {"open_to_work_flag": False, "recruiter_response_rate": 0.0,
         "interview_completion_rate": 0.30, "last_active_date": "2025-09-30",
         "avg_response_time_hours": 280.0},
    ]:
        c = _candidate_with_signals(**signal_dict)
        r = behavioral_score(c)["availability_modifier"]
        assert _MODIFIER_FLOOR <= r <= _MODIFIER_CEIL


def test_output_keys_present():
    c = _candidate_with_signals()
    result = behavioral_score(c)
    assert "availability_modifier" in result
    assert "component_scores" in result
    expected_keys = {"open_to_work", "recruiter_response", "interview_completion",
                     "recency", "response_speed"}
    assert set(result["component_scores"].keys()) == expected_keys


def test_component_scores_bounded():
    c = _candidate_with_signals()
    result = behavioral_score(c)
    for k, v in result["component_scores"].items():
        assert 0.0 <= v <= 1.0, f"component {k}={v} out of bounds"


def test_missing_signals_dont_raise():
    c = {
        "candidate_id": "CAND_0000001",
        "profile": {
            "anonymized_name": "Test", "headline": "", "summary": "",
            "location": "Bangalore", "country": "India",
            "years_of_experience": 3.0, "current_title": "ML Engineer",
            "current_company": "Corp", "current_company_size": "51-200",
            "current_industry": "Technology",
        },
        "career_history": [],
        "education": [], "skills": [],
        "redrob_signals": {},
    }
    result = behavioral_score(c)
    assert "availability_modifier" in result
    assert _MODIFIER_FLOOR <= result["availability_modifier"] <= _MODIFIER_CEIL


def test_weights_sum_to_one():
    from packages.core.scoring.behavioral import _WEIGHTS
    assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9
