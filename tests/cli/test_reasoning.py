"""tests/cli/test_reasoning.py — reasoning generator unit tests."""
import pytest
from packages.core.scoring.reasoning import generate_reasoning


def _make_inputs(
    title="ML Engineer",
    years=5.0,
    role_relevance=0.85,
    matched_terms=None,
    dq_flags=None,
    availability=0.75,
    score=0.70,
):
    candidate = {
        "candidate_id": "CAND_0000001",
        "profile": {
            "anonymized_name": "Test User",
            "years_of_experience": years,
            "current_title": title,
            "headline": "", "summary": "", "location": "Bangalore",
            "country": "India", "current_company": "Swiggy",
            "current_company_size": "51-200", "current_industry": "Technology",
        },
        "career_history": [], "education": [], "skills": [],
        "redrob_signals": {},
    }
    taxonomy = {
        "role_relevance": role_relevance,
        "title_score": 1.0, "history_title_score": 0.0,
        "desc_term_score": 0.5,
        "matched_terms": matched_terms or [],
    }
    dq = {
        "candidate_id": "CAND_0000001",
        "disqualified_flags": dq_flags or [],
        "disqualifier_penalty": 0.0 if not dq_flags else 0.40,
        "disqualifier_multiplier": 1.0 if not dq_flags else 0.60,
    }
    beh = {"availability_modifier": availability, "component_scores": {}}
    sc = {"candidate_id": "CAND_0000001", "score": score, "sub_scores": {}}
    return candidate, taxonomy, dq, beh, sc


def test_returns_non_empty_string():
    c, t, d, b, s = _make_inputs()
    result = generate_reasoning(c, t, d, b, s)
    assert isinstance(result, str)
    assert len(result) > 10


def test_contains_title_and_years():
    c, t, d, b, s = _make_inputs(title="Search Engineer", years=6.0)
    result = generate_reasoning(c, t, d, b, s)
    assert "Search Engineer" in result
    assert "6" in result


def test_mentions_matched_terms():
    c, t, d, b, s = _make_inputs(matched_terms=["pytorch", "nlp", "ranking"])
    result = generate_reasoning(c, t, d, b, s)
    assert any(label in result.lower() for label in ["pytorch", "nlp", "ranking"])


def test_consulting_concern_surfaces():
    c, t, d, b, s = _make_inputs(dq_flags=["consulting_only_no_product"])
    result = generate_reasoning(c, t, d, b, s)
    assert "consulting" in result.lower() or "it-services" in result.lower()


def test_research_concern_surfaces():
    c, t, d, b, s = _make_inputs(dq_flags=["pure_research_only"])
    result = generate_reasoning(c, t, d, b, s)
    assert "research" in result.lower()


def test_low_availability_concern_surfaces():
    c, t, d, b, s = _make_inputs(availability=0.25)
    result = generate_reasoning(c, t, d, b, s)
    assert "engagement" in result.lower() or "availability" in result.lower()


def test_high_availability_positive_note():
    c, t, d, b, s = _make_inputs(availability=0.90, dq_flags=[])
    result = generate_reasoning(c, t, d, b, s)
    assert "Concern" not in result


def test_no_name_in_output():
    c, t, d, b, s = _make_inputs()
    c["profile"]["anonymized_name"] = "Rahul Sharma"
    result = generate_reasoning(c, t, d, b, s)
    assert "Rahul" not in result
    assert "Sharma" not in result


def test_no_education_keywords_in_output():
    c, t, d, b, s = _make_inputs()
    result = generate_reasoning(c, t, d, b, s)
    forbidden = ["tier_1", "tier_2", "tier_3", "cgpa", "gpa", "iit", "nit", "graduation"]
    for word in forbidden:
        assert word.lower() not in result.lower()


def test_different_candidates_produce_different_strings():
    c1, t1, d1, b1, s1 = _make_inputs(title="ML Engineer", matched_terms=["pytorch", "nlp"])
    c2, t2, d2, b2, s2 = _make_inputs(title="Search Engineer", matched_terms=["ranking", "faiss"])
    r1 = generate_reasoning(c1, t1, d1, b1, s1)
    r2 = generate_reasoning(c2, t2, d2, b2, s2)
    assert r1 != r2


def test_fractional_years_displayed():
    c, t, d, b, s = _make_inputs(years=5.5)
    result = generate_reasoning(c, t, d, b, s)
    assert "5.5" in result
