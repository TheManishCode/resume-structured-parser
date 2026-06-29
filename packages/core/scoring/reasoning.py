"""
packages/core/scoring/reasoning.py

Grounded reasoning string generator — recruiter-voice, per-candidate.

v2: mentions current company, uses action verbs, 6 score-tier variants,
concern phrases are company-specific. No PII (name/education never read).
All 11 test contracts preserved.
"""
from __future__ import annotations
from . import schema

_TERM_PHRASES: dict[str, str] = {
    "pytorch":        "PyTorch model training",
    "gradient":       "gradient-based optimisation",
    "fine-tun":       "model fine-tuning",
    "nlp":            "NLP systems",
    "ranking":        "ranking/retrieval systems",
    "feature store":  "feature store pipelines",
    "recommendation": "recommendation engines",
    "inference":      "production model inference",
    "bert":           "BERT/transformer models",
    "embedding":      "embedding-based retrieval",
    "transformers":   "transformer architectures",
    "faiss":          "FAISS vector search",
    "retrieval":      "retrieval-augmented systems",
    "mlflow":         "MLflow experiment tracking",
    "pinecone":       "Pinecone vector database",
    "gpt":            "LLM/GPT integration",
    "openai":         "OpenAI API workflows",
    "elasticsearch":  "Elasticsearch-backed search",
}

# Legacy alias
_TERM_LABELS = _TERM_PHRASES


def _disqualifier_concern(flags: list[str], candidate: dict) -> str | None:
    if not flags:
        return None
    flag = flags[0]
    if flag == "consulting_only_no_product":
        companies = list({
            (r.get("company") or "").strip()
            for r in schema.get_career_history(candidate)
            if (r.get("company") or "").strip()
        })
        company_str = ", ".join(companies[:3]) if companies else "IT-services firms"
        return f"entire career at {company_str} — consulting/services background with no product ML evidence"
    return {
        "pure_research_only":            "all roles are research-track; no production deployment evidence in descriptions",
        "recent_langchain_wrapper_only": "recent work is LLM-wrapper/prompt-engineering rather than ML systems engineering",
        "cv_speech_robotics_without_nlp": "domain is CV/speech/robotics — limited NLP or search/ranking background",
        "title_chaser":                  "pattern of very short tenures (4+ stints under 12 months) across many employers",
    }.get(flag)


def _availability_concern(availability: float) -> str | None:
    if availability >= 0.5:
        return None
    if availability < 0.30:
        return "low platform engagement: slow response time, rarely active on platform"
    return "below-average availability signals on platform"


def _top_terms(matched: list[str], exclude: list[str], n: int = 2) -> list[str]:
    return [_TERM_PHRASES[t] for t in matched if t in _TERM_PHRASES
            and _TERM_PHRASES[t] not in exclude][:n]


def generate_reasoning(
    candidate: dict,
    taxonomy_result: dict,
    disqualifier_result: dict,
    behavioral_result: dict,
    score_result: dict,
) -> str:
    title    = schema.get_current_title(candidate)
    years    = schema.get_years_experience(candidate)
    company  = schema.get_current_company(candidate)
    role_rel = taxonomy_result.get("role_relevance", 0.0)
    matched  = taxonomy_result.get("matched_terms", [])
    dq_flags = disqualifier_result.get("disqualified_flags", [])
    avail    = behavioral_result.get("availability_modifier", 1.0)

    yr = f"{years:.0f}" if years == int(years) else f"{years:.1f}"
    company_tag = f" at {company}" if company else ""
    terms1 = _top_terms(matched, [], n=2)
    terms_str = " and ".join(terms1) if terms1 else ""

    if role_rel >= 0.85 and terms_str:
        sent1 = (
            f"{yr}-year {title}{company_tag}: strong production ML fit "
            f"with hands-on {terms_str}."
        )
    elif role_rel >= 0.70 and terms_str:
        sent1 = (
            f"{title}{company_tag} ({yr}yr) — {terms_str} present in role descriptions, "
            f"aligns well with Senior AI Engineer requirements."
        )
    elif role_rel >= 0.55 and terms_str:
        sent1 = (
            f"{yr}-year {title}{company_tag}; "
            f"ML relevance supported by {terms_str}."
        )
    elif role_rel >= 0.85:
        sent1 = (
            f"{yr}-year {title}{company_tag}: title strongly matches "
            f"Senior AI Engineer JD target role."
        )
    elif role_rel >= 0.50:
        sent1 = (
            f"{yr}-year {title}{company_tag}; "
            f"moderate match to Senior AI Engineer JD profile."
        )
    else:
        sent1 = (
            f"{yr}-year {title}{company_tag}; "
            f"limited overlap with Senior AI Engineer JD requirements."
        )

    concern = (
        _disqualifier_concern(dq_flags, candidate)
        or _availability_concern(avail)
    )

    if concern:
        sent2 = f"Concern: {concern}."
    elif avail >= 0.80 and not dq_flags:
        sent2 = "Strong platform engagement: high recruiter responsiveness and recent activity."
    else:
        extras = _top_terms(matched, terms1, n=1)
        if extras:
            sent2 = f"Additional JD signal: {extras[0]}."
        elif role_rel >= 0.70:
            sent2 = "Career descriptions align with JD production ML requirements."
        else:
            sent2 = ""

    return (sent1 + (" " + sent2 if sent2 else "")).strip()
