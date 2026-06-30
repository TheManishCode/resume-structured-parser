"""tests/cli/test_disqualifiers.py — disqualifier unit tests."""
import pytest
from packages.core.scoring.disqualifiers import (
    is_pure_research_only,
    is_consulting_only_no_product,
    is_recent_langchain_wrapper_only,
    is_cv_speech_robotics_without_nlp,
    is_title_chaser,
    disqualifier_check,
)


def _base_signals():
    return {
        "profile_completeness_score": 80, "signup_date": "2023-01-01",
        "last_active_date": "2026-06-01", "open_to_work_flag": True,
        "profile_views_received_30d": 10, "applications_submitted_30d": 2,
        "recruiter_response_rate": 0.8, "avg_response_time_hours": 12,
        "skill_assessment_scores": {}, "connection_count": 300,
        "endorsements_received": 50, "notice_period_days": 30,
        "expected_salary_range_inr_lpa": {"min": 20, "max": 40},
        "preferred_work_mode": "hybrid", "willing_to_relocate": True,
        "github_activity_score": 50, "search_appearance_30d": 20,
        "saved_by_recruiters_30d": 5, "interview_completion_rate": 0.9,
        "offer_acceptance_rate": 0.5, "verified_email": True,
        "verified_phone": True, "linkedin_connected": True,
    }


def _candidate(title, history, signals=None):
    return {
        "candidate_id": "CAND_0000001",
        "profile": {
            "anonymized_name": "Test User", "headline": "", "summary": "",
            "location": "Bangalore", "country": "India",
            "years_of_experience": 5.0, "current_title": title,
            "current_company": "Corp", "current_company_size": "51-200",
            "current_industry": "Technology",
        },
        "career_history": history,
        "education": [],
        "skills": [],
        "redrob_signals": signals or _base_signals(),
    }


def _role(title, company, duration_months, desc="", is_current=False, start="2020-01-01", end="2022-01-01"):
    return {
        "company": company, "title": title,
        "start_date": start, "end_date": None if is_current else end,
        "duration_months": duration_months, "is_current": is_current,
        "industry": "Technology", "company_size": "51-200", "description": desc,
    }


def test_pure_research_only_triggers_for_all_research_career():
    c = _candidate(
        "Research Scientist",
        [
            _role("Research Scientist", "IIT Delhi", 36, "Published papers on transformer architectures."),
            _role("Research Intern", "DeepMind", 6, "Worked on research projects, conferences."),
        ]
    )
    assert is_pure_research_only(c) is True


def test_pure_research_only_not_triggered_with_production_evidence():
    c = _candidate(
        "Research Scientist",
        [
            _role("Research Scientist", "Google Brain", 36,
                  "Developed models deployed to production serving 1M users via API endpoint."),
        ]
    )
    assert is_pure_research_only(c) is False


def test_pure_research_only_not_triggered_for_ml_engineer():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "Swiggy", 30, "Built ranking models in production."),
            _role("Data Scientist", "Zomato", 24, "Developed recommendation systems."),
        ]
    )
    assert is_pure_research_only(c) is False


def test_pure_research_only_not_triggered_mixed_career():
    c = _candidate(
        "Research Scientist",
        [
            _role("Research Scientist", "TCS Research", 24, "Published papers."),
            _role("ML Engineer", "Flipkart", 18, "Deployed models."),
        ]
    )
    assert is_pure_research_only(c) is False


def test_consulting_only_triggers_for_all_consulting_firms():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "TCS", 30, "Delivered ML solutions for client."),
            _role("Data Scientist", "Infosys", 24, "Analytics projects for banking clients."),
            _role("Software Engineer", "Wipro", 18, "Development work."),
        ]
    )
    assert is_consulting_only_no_product(c) is True


def test_consulting_only_not_triggered_with_product_company():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "TCS", 24, "Consulting work."),
            _role("ML Engineer", "Swiggy", 30, "Built recommendation systems for Swiggy platform."),
        ]
    )
    assert is_consulting_only_no_product(c) is False


def test_consulting_only_not_triggered_single_role():
    c = _candidate(
        "ML Engineer",
        [_role("ML Engineer", "Infosys", 18, "Client work.")]
    )
    assert is_consulting_only_no_product(c) is False


def test_consulting_only_case_insensitive():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "INFOSYS", 24, ""),
            _role("Data Scientist", "Wipro Technologies", 24, ""),
        ]
    )
    assert is_consulting_only_no_product(c) is True


def test_consulting_only_partial_match():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "Tata Consultancy Services", 36, ""),
            _role("Software Engineer", "HCL Technologies", 24, ""),
        ]
    )
    assert is_consulting_only_no_product(c) is True


def test_langchain_wrapper_triggers():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "Startup", 12,
                  "Built chatbot using langchain and openai api. Prompt engineering and chain orchestration.",
                  is_current=True),
        ]
    )
    assert is_recent_langchain_wrapper_only(c) is True


def test_langchain_wrapper_not_triggered_with_deep_ml():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "Startup", 24,
                  "Used langchain for orchestration but also trained pytorch models and fine-tuned bert.",
                  is_current=True),
        ]
    )
    assert is_recent_langchain_wrapper_only(c) is False


def test_langchain_wrapper_not_triggered_for_pure_ml():
    c = _candidate(
        "ML Engineer",
        [_role("ML Engineer", "Swiggy", 30, "pytorch ranking models fine-tuning gradient.", is_current=True)]
    )
    assert is_recent_langchain_wrapper_only(c) is False


def test_cv_robotics_triggers_for_cv_only():
    c = _candidate(
        "Computer Vision Engineer",
        [
            _role("Computer Vision Engineer", "AutoCo", 30,
                  "Built object detection and image segmentation pipelines for autonomous vehicle."),
        ]
    )
    assert is_cv_speech_robotics_without_nlp(c) is True


def test_cv_robotics_not_triggered_with_nlp():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "Corp", 30,
                  "object detection and natural language processing nlp sentiment analysis."),
        ]
    )
    assert is_cv_speech_robotics_without_nlp(c) is False


def test_cv_robotics_not_triggered_for_pure_nlp():
    c = _candidate(
        "NLP Engineer",
        [_role("NLP Engineer", "Corp", 30, "bert gpt text classification named entity recognition.")]
    )
    assert is_cv_speech_robotics_without_nlp(c) is False


def test_title_chaser_triggers_for_many_short_stints():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "Co1", 8, is_current=False, end="2026-01-01"),
            _role("Data Scientist", "Co2", 9, is_current=False, end="2025-04-01"),
            _role("AI Specialist", "Co3", 11, is_current=False, end="2024-07-01"),
            _role("ML Engineer", "Co4", 10, is_current=False, end="2023-08-01"),
            _role("Software Engineer", "Co5", 12, is_current=False, end="2022-10-01"),
        ]
    )
    assert is_title_chaser(c) is True


def test_title_chaser_not_triggered_for_stable_career():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "Swiggy", 36, is_current=True),
            _role("Data Scientist", "Zomato", 30),
            _role("Software Engineer", "Flipkart", 24),
        ]
    )
    assert is_title_chaser(c) is False


def test_title_chaser_not_triggered_for_few_companies():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "Co1", 8),
            _role("Data Scientist", "Co2", 9),
            _role("AI Specialist", "Co3", 11),
        ]
    )
    assert is_title_chaser(c) is False


def test_no_disqualifiers_for_strong_fit():
    c = _candidate(
        "ML Engineer",
        [
            _role("ML Engineer", "Swiggy", 36,
                  "pytorch fine-tuning bert nlp ranking production deployment api.",
                  is_current=True),
            _role("Data Scientist", "Zomato", 30, "ranking recommendation inference production."),
        ]
    )
    result = disqualifier_check(c)
    assert result["disqualified_flags"] == []
    assert result["disqualifier_penalty"] == 0.0
    assert result["disqualifier_multiplier"] == 1.0


def test_combined_penalty_compounds_multiplicatively():
    c = _candidate(
        "Research Scientist",
        [
            _role("Research Scientist", "TCS", 36, "Published papers, no deployment."),
            _role("Research Intern", "Infosys", 24, "Research project."),
        ]
    )
    result = disqualifier_check(c)
    assert "pure_research_only" in result["disqualified_flags"]
    assert "consulting_only_no_product" in result["disqualified_flags"]
    assert result["disqualifier_penalty"] == pytest.approx(0.76, abs=0.01)
    assert result["disqualifier_multiplier"] == pytest.approx(0.24, abs=0.01)


def test_output_keys_always_present():
    c = _candidate("Business Analyst", [_role("Business Analyst", "Corp", 24)])
    result = disqualifier_check(c)
    for k in ["candidate_id", "disqualified_flags", "disqualifier_penalty", "disqualifier_multiplier"]:
        assert k in result


def test_penalty_bounded():
    c = _candidate(
        "Research Scientist",
        [
            _role("Research Scientist", "TCS", 3,
                  "object detection robotics langchain openai api. No nlp work.",
                  is_current=False, end="2026-01-01"),
            _role("Research Intern", "Infosys", 3, "robot control.",
                  is_current=False, end="2025-09-01"),
            _role("Research Intern", "Wipro", 3, "cv work.",
                  is_current=False, end="2025-06-01"),
            _role("Research Intern", "HCL", 3, "image seg.",
                  is_current=False, end="2025-03-01"),
            _role("Research Intern", "Accenture", 3, "slam.",
                  is_current=False, end="2024-12-01"),
        ]
    )
    result = disqualifier_check(c)
    assert 0.0 <= result["disqualifier_penalty"] <= 1.0
    assert 0.0 <= result["disqualifier_multiplier"] <= 1.0
    assert abs(result["disqualifier_penalty"] + result["disqualifier_multiplier"] - 1.0) < 1e-6
