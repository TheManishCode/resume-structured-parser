"""tests/cli/test_role_taxonomy.py — role taxonomy unit tests."""
import math
import pytest
from packages.core.scoring.role_taxonomy import role_taxonomy, TIER_1_TITLES, TIER_2_TITLES, DESC_TERMS


def _make_candidate(current_title="", history=None, skills=None):
    history = history or []
    skills = skills or []
    return {
        "candidate_id": "CAND_0000001",
        "profile": {
            "anonymized_name": "Test User",
            "headline": "", "summary": "",
            "location": "Bangalore", "country": "India",
            "years_of_experience": 5.0,
            "current_title": current_title,
            "current_company": "Acme Corp",
            "current_company_size": "51-200",
            "current_industry": "Technology",
        },
        "career_history": history,
        "education": [],
        "skills": skills,
        "redrob_signals": {
            "profile_completeness_score": 80,
            "signup_date": "2023-01-01",
            "last_active_date": "2026-06-01",
            "open_to_work_flag": True,
            "profile_views_received_30d": 10,
            "applications_submitted_30d": 2,
            "recruiter_response_rate": 0.8,
            "avg_response_time_hours": 12,
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
            "interview_completion_rate": 0.9,
            "offer_acceptance_rate": 0.5,
            "verified_email": True,
            "verified_phone": True,
            "linkedin_connected": True,
        },
    }


def _role(title, desc="", is_current=False, end_date="2024-01-01", duration_months=24):
    return {
        "company": "Corp",
        "title": title,
        "start_date": "2022-01-01",
        "end_date": None if is_current else end_date,
        "duration_months": duration_months,
        "is_current": is_current,
        "industry": "Technology",
        "company_size": "51-200",
        "description": desc,
    }


def test_tier1_title_no_desc_gets_baseline():
    c = _make_candidate(
        current_title="ML Engineer",
        history=[_role("ML Engineer", desc="Managed teams and delivered projects.", is_current=True)],
    )
    result = role_taxonomy(c)
    assert result["title_score"] == 1.0
    assert result["role_relevance"] == pytest.approx(0.5, abs=0.01)


def test_tier1_title_with_strong_desc_approaches_1():
    ml_desc = (
        "Built pytorch-based NLP ranking system. Fine-tuning bert models for inference. "
        "Feature store integration. Gradient descent optimisation. Recommendation engine "
        "using faiss and embedding retrieval with mlflow tracking."
    )
    c = _make_candidate(
        current_title="ML Engineer",
        history=[_role("ML Engineer", desc=ml_desc, is_current=True)],
    )
    result = role_taxonomy(c)
    assert result["role_relevance"] > 0.7
    assert result["desc_term_score"] > 0.4
    assert "pytorch" in result["matched_terms"]
    assert "nlp" in result["matched_terms"]
    assert "fine-tun" in result["matched_terms"]


def test_tier2_title_scores_below_tier1():
    ml_desc = "pytorch fine-tuning nlp ranking bert gradient"
    c1 = _make_candidate(
        current_title="ML Engineer",
        history=[_role("ML Engineer", desc=ml_desc, is_current=True)],
    )
    c2 = _make_candidate(
        current_title="AI Research Engineer",
        history=[_role("AI Research Engineer", desc=ml_desc, is_current=True)],
    )
    r1 = role_taxonomy(c1)
    r2 = role_taxonomy(c2)
    assert r1["role_relevance"] > r2["role_relevance"]


def test_non_ml_title_gets_zero():
    c = _make_candidate(
        current_title="Business Analyst",
        history=[_role("Business Analyst", desc="Prepared reports and dashboards.", is_current=True)],
    )
    result = role_taxonomy(c)
    assert result["role_relevance"] == 0.0
    assert result["title_score"] == 0.0
    assert result["history_title_score"] == 0.0


def test_non_ml_title_with_ml_skills_still_zero():
    c = _make_candidate(
        current_title="HR Manager",
        history=[_role("HR Manager", desc="Recruitment, payroll, and compliance.", is_current=True)],
        skills=[{"name": "PyTorch", "proficiency": "expert", "endorsements": 50, "duration_months": 24}],
    )
    result = role_taxonomy(c)
    assert result["role_relevance"] == 0.0, "skills[] should never boost role_relevance"


def test_recent_ml_history_boosts_score():
    c = _make_candidate(
        current_title="Data Engineer",
        history=[
            _role("Data Engineer", desc="Built Spark pipelines.", is_current=True),
            _role("ML Engineer", desc="pytorch nlp ranking", end_date="2025-01-01"),
        ],
    )
    result = role_taxonomy(c)
    assert result["history_title_score"] > 0.7
    assert result["role_relevance"] > 0.0


def test_old_ml_history_decays_significantly():
    c = _make_candidate(
        current_title="Business Analyst",
        history=[
            _role("Business Analyst", desc="Reports.", is_current=True),
            _role("ML Engineer", desc="", end_date="2016-01-01"),
        ],
    )
    result = role_taxonomy(c)
    assert result["history_title_score"] < 0.2


def test_current_role_gets_no_decay():
    c = _make_candidate(
        current_title="ML Engineer",
        history=[_role("ML Engineer", desc="", is_current=True, end_date="2020-01-01")],
    )
    result = role_taxonomy(c)
    assert result["title_score"] == 1.0
    assert result["history_title_score"] == 1.0


def test_excluded_term_rag_not_scored():
    assert "rag" not in DESC_TERMS


def test_excluded_generic_terms():
    for term in ["production", "deploy", "llm", "scale"]:
        assert term not in DESC_TERMS, f"'{term}' is a false-positive term and must be excluded"


def test_desc_score_zero_for_empty_description():
    c = _make_candidate(current_title="ML Engineer", history=[])
    result = role_taxonomy(c)
    assert result["desc_term_score"] == 0.0
    assert result["matched_terms"] == []


def test_matched_terms_sorted():
    ml_desc = "pytorch nlp ranking faiss bert gradient"
    c = _make_candidate(
        current_title="ML Engineer",
        history=[_role("ML Engineer", desc=ml_desc, is_current=True)],
    )
    result = role_taxonomy(c)
    assert result["matched_terms"] == sorted(result["matched_terms"])


def test_all_tier1_titles_covered():
    expected = {
        "ML Engineer", "Search Engineer", "NLP Engineer",
        "Recommendation Systems Engineer", "Applied ML Engineer",
    }
    assert expected.issubset(TIER_1_TITLES)


def test_output_keys_present():
    c = _make_candidate(current_title="Business Analyst")
    result = role_taxonomy(c)
    for key in ["role_relevance", "title_score", "history_title_score", "desc_term_score", "matched_terms"]:
        assert key in result


def test_role_relevance_bounded():
    ml_desc = " ".join(
        ["pytorch fine-tuning nlp gradient ranking faiss bert embedding"] * 10
    )
    c = _make_candidate(
        current_title="ML Engineer",
        history=[_role("ML Engineer", desc=ml_desc, is_current=True)],
    )
    result = role_taxonomy(c)
    assert 0.0 <= result["role_relevance"] <= 1.0
