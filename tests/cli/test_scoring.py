"""tests/cli/test_scoring.py — composite scorer unit tests."""
import pytest
from packages.core.scoring.scoring import compute_score, score_candidate, _yoe_score


def test_yoe_very_junior_gets_low_score():
    assert _yoe_score(1.0) < 0.30


def test_yoe_senior_sweet_spot():
    assert _yoe_score(5.5) > 0.70
    assert _yoe_score(6.0) == pytest.approx(0.82, abs=0.01)
    assert _yoe_score(8.0) == pytest.approx(0.95, abs=0.01)


def test_yoe_expert_maxes_out():
    assert _yoe_score(10.0) == pytest.approx(1.0, abs=0.01)
    assert _yoe_score(15.0) == pytest.approx(1.0, abs=0.01)


def test_yoe_monotone():
    scores = [_yoe_score(y) for y in [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 15]]
    for i in range(len(scores) - 1):
        assert scores[i] <= scores[i + 1], f"Non-monotone at index {i}: {scores[i]} > {scores[i+1]}"


def _make_sub_scores(
    role_relevance=0.8,
    integrity_score=1.0,
    disqualifier_multiplier=1.0,
    availability_modifier=0.75,
    years=5.0,
):
    candidate = {
        "candidate_id": "CAND_0000001",
        "profile": {"years_of_experience": years, "current_title": "ML Engineer",
                    "anonymized_name": "X", "headline": "", "summary": "",
                    "location": "Bangalore", "country": "India",
                    "current_company": "Swiggy", "current_company_size": "51-200",
                    "current_industry": "Technology"},
        "career_history": [], "education": [], "skills": [],
        "redrob_signals": {},
    }
    tax = {"role_relevance": role_relevance, "title_score": 1.0,
           "history_title_score": 0.0, "desc_term_score": 0.5, "matched_terms": []}
    integ = {"candidate_id": "CAND_0000001", "is_honeypot": False,
             "integrity_score": integrity_score, "integrity_flags": []}
    dq = {"candidate_id": "CAND_0000001", "disqualified_flags": [],
          "disqualifier_penalty": round(1.0 - disqualifier_multiplier, 4),
          "disqualifier_multiplier": disqualifier_multiplier}
    beh = {"availability_modifier": availability_modifier, "component_scores": {}}
    return candidate, tax, integ, dq, beh


def test_score_is_deterministic():
    args = _make_sub_scores()
    r1 = compute_score(*args)
    r2 = compute_score(*args)
    assert r1["score"] == r2["score"]


def test_score_bounded():
    for role_rel in [0.0, 0.5, 1.0]:
        for integ in [0.05, 1.0]:
            for dq_mult in [0.24, 1.0]:
                for avail in [0.20, 1.0]:
                    c, t, i, d, b = _make_sub_scores(
                        role_relevance=role_rel, integrity_score=integ,
                        disqualifier_multiplier=dq_mult, availability_modifier=avail
                    )
                    r = compute_score(c, t, i, d, b)
                    assert 0.0 <= r["score"] <= 1.0


def test_honeypot_gets_near_zero_score():
    c, t, i, d, b = _make_sub_scores(role_relevance=1.0, integrity_score=0.05)
    result = compute_score(c, t, i, d, b)
    assert result["score"] < 0.10


def test_non_ml_title_gets_zero():
    c, t, i, d, b = _make_sub_scores(role_relevance=0.0)
    result = compute_score(c, t, i, d, b)
    assert result["score"] == pytest.approx(0.0, abs=1e-9)


def test_consulting_penalty_reduces_score():
    c_clean, t, i, d_clean, b = _make_sub_scores(disqualifier_multiplier=1.0)
    c_dq, _, _, d_dq, _ = _make_sub_scores(disqualifier_multiplier=0.60)
    r_clean = compute_score(c_clean, t, i, d_clean, b)
    r_dq = compute_score(c_dq, t, i, d_dq, b)
    assert r_clean["score"] > r_dq["score"]
    assert abs(r_dq["score"] / r_clean["score"] - 0.60) < 0.01


def test_better_fit_ranks_higher():
    c_high, t_high, i, d, b = _make_sub_scores(role_relevance=0.95)
    c_low, t_low, _, _, _ = _make_sub_scores(role_relevance=0.55)
    r_high = compute_score(c_high, t_high, i, d, b)
    r_low = compute_score(c_low, t_low, i, d, b)
    assert r_high["score"] > r_low["score"]


def test_output_keys():
    c, t, i, d, b = _make_sub_scores()
    result = compute_score(c, t, i, d, b)
    assert "score" in result
    assert "sub_scores" in result
    expected_sub = {"role_relevance", "yoe_score", "years_of_experience",
                    "base_fit", "integrity_score", "disqualifier_multiplier",
                    "availability_modifier"}
    assert expected_sub.issubset(set(result["sub_scores"].keys()))


def test_score_candidate_end_to_end():
    c = {
        "candidate_id": "CAND_0000001",
        "profile": {
            "anonymized_name": "Test", "headline": "", "summary": "",
            "location": "Bangalore", "country": "India",
            "years_of_experience": 5.0, "current_title": "ML Engineer",
            "current_company": "Swiggy", "current_company_size": "51-200",
            "current_industry": "Technology",
        },
        "career_history": [{
            "company": "Swiggy", "title": "ML Engineer",
            "start_date": "2023-01-01", "end_date": None,
            "duration_months": 41, "is_current": True,
            "industry": "Technology", "company_size": "1001-5000",
            "description": "pytorch nlp ranking fine-tuning bert gradient feature store.",
        }],
        "education": [], "skills": [],
        "redrob_signals": {
            "profile_completeness_score": 90, "signup_date": "2023-01-01",
            "last_active_date": "2026-05-27", "open_to_work_flag": True,
            "profile_views_received_30d": 20, "applications_submitted_30d": 3,
            "recruiter_response_rate": 0.85, "avg_response_time_hours": 8.0,
            "skill_assessment_scores": {}, "connection_count": 500,
            "endorsements_received": 100, "notice_period_days": 30,
            "expected_salary_range_inr_lpa": {"min": 30, "max": 60},
            "preferred_work_mode": "hybrid", "willing_to_relocate": True,
            "github_activity_score": 65, "search_appearance_30d": 50,
            "saved_by_recruiters_30d": 10, "interview_completion_rate": 0.95,
            "offer_acceptance_rate": 0.8, "verified_email": True,
            "verified_phone": True, "linkedin_connected": True,
        },
    }
    result = score_candidate(c)
    assert 0.0 <= result["score"] <= 1.0
    assert result["score"] > 0.5, "Strong ML candidate should score > 0.5"


def test_no_education_fields_in_sub_scores():
    c, t, i, d, b = _make_sub_scores()
    result = compute_score(c, t, i, d, b)
    for key in result["sub_scores"]:
        assert "tier" not in key.lower()
        assert "grade" not in key.lower()
        assert "institution" not in key.lower()
        assert "graduation" not in key.lower()
