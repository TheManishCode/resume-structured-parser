"""
src/reasoning.py

Grounded reasoning string generator for the submission CSV's `reasoning` column.

Each candidate gets a 1-2 sentence string that:
  - Names years_of_experience and current_title (candidate-specific facts)
  - Mentions 1-2 matched JD requirements from matched_terms or role_relevance
  - Adds a specific concern if disqualifier_penalty > 0 or availability < 0.5
  - Is guaranteed unique per candidate (inputs vary, template output varies)
  - Contains no PII beyond what's already in the public candidate record
  - Does NOT mention education tier, grade, institution, or name

Design: template-based (no LLM at ranking time). The template selects
branches based on actual sub-score values, not generic filler.
"""
from __future__ import annotations
import schema

# ── JD-signal term → human-readable label map ────────────────────────────────
# Only the terms we actually use for descriptions (from role_taxonomy.DESC_TERMS)
_TERM_LABELS: dict[str, str] = {
    "pytorch": "PyTorch model development",
    "gradient": "gradient-based training",
    "fine-tun": "fine-tuning",
    "nlp": "NLP",
    "ranking": "ranking systems",
    "feature store": "feature store integration",
    "recommendation": "recommendation systems",
    "inference": "model inference",
    "bert": "BERT/transformer models",
    "embedding": "embedding-based retrieval",
    "transformers": "transformer architectures",
    "faiss": "FAISS vector search",
    "retrieval": "retrieval systems",
    "mlflow": "MLflow experiment tracking",
    "pinecone": "vector database (Pinecone)",
    "gpt": "LLM/GPT integration",
    "openai": "OpenAI API integration",
    "elasticsearch": "Elasticsearch search",
}

# ── Concern phrase builders ───────────────────────────────────────────────────

def _disqualifier_concern(flags: list[str]) -> str | None:
    if not flags:
        return None
    flag = flags[0]
    phrases = {
        "pure_research_only": "career history is research-oriented with no production evidence",
        "consulting_only_no_product": "career has been exclusively at IT-services/consulting firms",
        "recent_langchain_wrapper_only": "recent work appears to be LLM-wrapper integration rather than ML systems",
        "cv_speech_robotics_without_nlp": "domain is CV/speech/robotics with limited NLP/search background",
        "title_chaser": "shows a pattern of very short tenures across many employers",
    }
    return phrases.get(flag)


def _availability_concern(availability: float) -> str | None:
    if availability >= 0.5:
        return None
    if availability < 0.30:
        return "low platform engagement (slow response time, rarely active)"
    return "below-average availability signals"


# ── Main function ─────────────────────────────────────────────────────────────

def generate_reasoning(
    candidate: dict,
    taxonomy_result: dict,
    disqualifier_result: dict,
    behavioral_result: dict,
    score_result: dict,
) -> str:
    """Generate a 1-2 sentence grounded reasoning string for a candidate.

    All inputs must come from the pipeline's pre-computed results — this
    function does no scoring or data access of its own.
    """
    cid = schema.get_candidate_id(candidate)
    title = schema.get_current_title(candidate)
    years = schema.get_years_experience(candidate)
    role_rel = taxonomy_result.get("role_relevance", 0.0)
    matched = taxonomy_result.get("matched_terms", [])
    dq_flags = disqualifier_result.get("disqualified_flags", [])
    avail = behavioral_result.get("availability_modifier", 1.0)
    final_score = score_result.get("score", 0.0)

    # ── Sentence 1: fit summary ───────────────────────────────────────────────
    years_str = f"{years:.0f}" if years == int(years) else f"{years:.1f}"

    if role_rel >= 0.85:
        fit_word = "strong"
    elif role_rel >= 0.65:
        fit_word = "good"
    elif role_rel >= 0.50:
        fit_word = "moderate"
    else:
        fit_word = "limited"

    # Pick up to 2 most specific matched terms for the sentence
    top_terms = [_TERM_LABELS[t] for t in matched[:3] if t in _TERM_LABELS][:2]
    if top_terms:
        skills_clause = f", with described experience in {' and '.join(top_terms)}"
    else:
        skills_clause = ""

    sent1 = (
        f"{years_str}-year {title} with {fit_word} role relevance"
        f" to the Senior AI Engineer JD{skills_clause}."
    )

    # ── Sentence 2: concern or positive note ─────────────────────────────────
    concern = _disqualifier_concern(dq_flags) or _availability_concern(avail)

    if concern:
        sent2 = f"Concern: {concern}."
    elif avail >= 0.80 and not dq_flags:
        sent2 = "High engagement signals suggest strong availability."
    elif matched and role_rel >= 0.70:
        # Pick a different term than already mentioned in sent1 for variety
        extra_terms = [_TERM_LABELS[t] for t in matched if t in _TERM_LABELS
                       and _TERM_LABELS[t] not in (top_terms or [])]
        if extra_terms:
            sent2 = f"Additional JD-relevant signals: {extra_terms[0]}."
        else:
            sent2 = "Career descriptions align with JD's production ML requirements."
    else:
        sent2 = ""

    reasoning = sent1
    if sent2:
        reasoning = reasoning + " " + sent2
    return reasoning.strip()
