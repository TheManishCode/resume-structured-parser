"""tests/test_scoring.py — core scoring engine unit tests (no DB)."""
import pytest
from packages.core.scoring import score_candidate, generate_reasoning


def _make_candidate(yoe=5.0, title="ML Engineer", description="pytorch nlp bert"):
    return {
        "candidate_id": "CAND_TEST_001",
        "profile": {
            "anonymized_name": "Test",
            "headline": "",
            "summary": "",
            "location": "MH",
            "country": "India",
            "years_of_experience": yoe,
            "current_title": title,
            "current_company": "TestCo",
            "current_company_size": "51-200",
            "current_industry": "Tech",
        },
        "career_history": [{
            "company": "TestCo",
            "title": title,
            "start_date": "2019-01-01",
            "end_date": None,
            "duration_months": int(yoe * 12),
            "is_current": True,
            "industry": "Tech",
            "company_size": "51-200",
            "description": description,
        }],
        "education": [],
        "skills": [],
        "redrob_signals": {
            "profile_completeness_score": 80,
            "signup_date": "2022-01-01",
            "last_active_date": "2026-06-01",
            "open_to_work_flag": True,
            "profile_views_received_30d": 10,
            "applications_submitted_30d": 2,
            "recruiter_response_rate": 0.7,
            "avg_response_time_hours": 12.0,
            "skill_assessment_scores": {},
            "connection_count": 200,
            "endorsements_received": 30,
            "notice_period_days": 30,
            "expected_salary_range_inr_lpa": {"min": 20, "max": 40},
            "preferred_work_mode": "hybrid",
            "willing_to_relocate": True,
            "github_activity_score": 40,
            "search_appearance_30d": 20,
            "saved_by_recruiters_30d": 5,
            "interview_completion_rate": 0.8,
            "offer_acceptance_rate": 0.7,
            "verified_email": True,
            "verified_phone": True,
            "linkedin_connected": True,
        },
    }


def test_ml_candidate_scores_above_zero():
    c = _make_candidate(yoe=5.0, title="ML Engineer", description="pytorch nlp bert transformer")
    result = score_candidate(c)
    assert result["score"] > 0.0
    assert 0.0 <= result["score"] <= 1.0


def test_non_ml_candidate_scores_zero():
    c = _make_candidate(yoe=8.0, title="Sales Manager", description="b2b enterprise sales crm")
    result = score_candidate(c)
    assert result["score"] == 0.0


def test_honeypot_scores_near_zero():
    c = _make_candidate(yoe=0.3, title="ML Engineer", description="pytorch nlp")
    # Inject expert skill with tiny duration to trigger honeypot
    c["skills"] = [{"name": "Python", "proficiency": "expert", "duration_months": 3}]
    result = score_candidate(c)
    assert result["score"] < 0.1


def test_more_experience_scores_higher():
    low = score_candidate(_make_candidate(yoe=1.0))
    high = score_candidate(_make_candidate(yoe=8.0))
    assert high["score"] >= low["score"]


def test_score_is_deterministic():
    c = _make_candidate()
    assert score_candidate(c)["score"] == score_candidate(c)["score"]


def test_score_does_not_use_name():
    c1 = _make_candidate()
    c2 = _make_candidate()
    c2["profile"]["anonymized_name"] = "Completely Different Name"
    assert score_candidate(c1)["score"] == score_candidate(c2)["score"]


def test_generate_reasoning_returns_string():
    from packages.core.scoring.role_taxonomy import role_taxonomy
    from packages.core.scoring.integrity import integrity_check
    from packages.core.scoring.disqualifiers import disqualifier_check
    from packages.core.scoring.behavioral import behavioral_score
    c = _make_candidate()
    tax = role_taxonomy(c)
    dq = disqualifier_check(c)
    beh = behavioral_score(c)
    sc = score_candidate(c)
    reason = generate_reasoning(c, tax, dq, beh, sc)
    assert isinstance(reason, str)
    assert len(reason) > 10
