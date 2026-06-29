"""
src/role_taxonomy.py

Role-relevance scorer for the Senior AI Engineer (Search/Ranking) JD.

Calibrated via probe_taxonomy.py against the full 100K candidates.jsonl:

Title distribution in dataset (current_title):
  ML Engineer: 167, AI Research Engineer: 153, Data Scientist: 145,
  Senior Software Engineer (ML): 142, Computer Vision Engineer: 132,
  Junior ML Engineer: 131, AI Specialist: 130, Machine Learning Engineer: 24,
  Applied ML Engineer: 23, Search Engineer: 23, AI Engineer: 21,
  Senior Data Scientist: 19 — total ~1,150 ML-adjacent candidates.

Description term analysis (ML-adjacent vs non-ML):
  Terms with near-0% false-positive rate in non-ML descriptions:
    gradient 54.6%, fine-tun 52.7%, pytorch 48.1%, nlp 48.1%,
    ranking 39.3%, feature store 34.0%, recommendation 33.0%,
    inference 27.8%, bert 25.9%, embedding 7.8%, transformers 4.8%,
    faiss 4.8%, retrieval 4.8%, elasticsearch 4.8%, pinecone 4.6%.
  Excluded from desc scoring:
    'rag' — 8.7% false-positive rate in non-ML descriptions (too ambiguous).
    'production', 'deploy', 'llm', 'scale' — appear in 87K/21K/50K/25K
    non-ML descriptions respectively — zero discriminating power.
    'vector', 'langchain', 'huggingface' — 0% everywhere in this dataset.

Design:
  Title is the primary gate — non-ML-titled candidates also have near-zero
  ML description signal, so the combination is nearly perfectly separating.
  Description terms differentiate within the ML pool (~1,150 candidates)
  to reward those who show real production ML work in their history vs.
  those who list ML titles but have thin descriptive evidence.
  Role_relevance = best_title_score * (0.5 + 0.5 * desc_score)
  so a Tier-1 title with no ML description evidence still gets 0.5,
  while a Tier-1 title with strong description evidence can reach 1.0.

NOT scored via skills[]: per JD's own warning, raw skill keywords are the
keyword-stuffer's primary tool. Signal lives in career history titles and
role descriptions, not the skills list.

Normalization calibration (probe_desc_calibrate.py, 2,556 ML roles):
  Per-role raw score p50=0.20, p70=0.43, p80–p100=0.52 (the ceiling).
  Descriptions contain a subset of high-signal terms; no realistic role
  description hits all 18. _MAX_DESC_RAW = 0.52 ensures the 0–1 range
  maps to real data rather than an unreachable theoretical maximum.
"""
from __future__ import annotations
import math
from datetime import date
import schema

# ── Title tiers derived directly from JD ideal-candidate profile ─────────────

TIER_1_TITLES = {
    # Direct JD targets
    "ML Engineer",
    "Machine Learning Engineer",
    "Applied ML Engineer",
    "Senior ML Engineer",
    "Principal ML Engineer",
    "Staff ML Engineer",
    "AI Engineer",
    "Senior AI Engineer",
    "Search Engineer",
    "Ranking Engineer",
    "Recommendation Systems Engineer",
    "NLP Engineer",
    "Applied Scientist",
}

TIER_2_TITLES = {
    # Strong signal but with caveats the disqualifiers module handles separately
    # (research-only, CV-without-NLP, junior experience level)
    "AI Research Engineer",
    "Data Scientist",
    "Senior Data Scientist",
    "Senior Software Engineer (ML)",
    "Computer Vision Engineer",
    "AI Specialist",
    "Junior ML Engineer",
    "Research Scientist",
}

_TIER_SCORES: dict[str, float] = {t: 1.0 for t in TIER_1_TITLES}
_TIER_SCORES.update({t: 0.75 for t in TIER_2_TITLES})

# ── Description term weights (all terms have lift > 200x in ML vs non-ML) ────

DESC_TERMS: dict[str, float] = {
    # >40% of ML candidates have this term in descriptions
    "gradient": 0.15,
    "fine-tun": 0.15,      # matches fine-tuning, fine-tune, fine-tuned
    "pytorch": 0.15,
    "nlp": 0.12,
    "ranking": 0.12,
    # 20–40% of ML candidates
    "feature store": 0.12,
    "recommendation": 0.10,
    "inference": 0.10,
    "bert": 0.10,
    # 5–20% of ML candidates — specific frameworks/concepts
    "embedding": 0.08,
    "transformers": 0.08,  # HuggingFace or reference to transformer architecture
    "faiss": 0.08,
    "retrieval": 0.08,
    "mlflow": 0.08,
    "pinecone": 0.08,
    # <5% of ML candidates but high specificity
    "gpt": 0.06,
    "openai": 0.06,
    "elasticsearch": 0.05,  # lower weight — used beyond ML context
}

# Empirically calibrated: p95 of per-role raw scores across 2,556 ML-candidate
# roles (probe_desc_calibrate.py). Using the empirical maximum (not the theoretical
# sum of all weights = 1.76) ensures the 0–1 range is actually used. Descriptions
# matching the natural ML role template top out at 0.52; almost no description
# exceeds it because each role specialises in a subset of ML terms.
_MAX_DESC_RAW: float = 0.52

# ── Internal helpers ──────────────────────────────────────────────────────────

_TODAY = date(2026, 6, 29)


def _title_score(title: str) -> float:
    return _TIER_SCORES.get(title, 0.0)


def _history_title_score(c: dict) -> float:
    """Recency-weighted max title score over career history.

    Decay: score * exp(-0.2 * years_since_role_end).
    Current roles (is_current=True or null end_date) get full weight.
    """
    best = 0.0
    for role in schema.get_career_history(c):
        ts = _title_score(role.get("title", "") or "")
        if ts == 0.0:
            continue
        if role.get("is_current", False) or not role.get("end_date"):
            decay = 1.0
        else:
            ed = schema.parse_date(role.get("end_date"))
            if ed is None:
                decay = 1.0
            else:
                years_ago = max(0.0, (_TODAY - ed).days / 365.25)
                decay = math.exp(-0.2 * years_ago)
        best = max(best, ts * decay)
    return best


def _desc_term_score(c: dict) -> tuple[float, list[str]]:
    """Score career descriptions by ML-specific term presence.

    Per-role recency decay (same exp(-0.2*years) scheme) then weighted average.
    Returns (normalized_score 0–1, sorted list of matched term strings).
    """
    roles = schema.get_career_history(c)
    if not roles:
        return 0.0, []

    weighted_score_sum = 0.0
    weight_sum = 0.0
    all_matched: set[str] = set()

    for role in roles:
        if role.get("is_current", False) or not role.get("end_date"):
            w = 1.0
        else:
            ed = schema.parse_date(role.get("end_date"))
            if ed is None:
                w = 1.0
            else:
                years_ago = max(0.0, (_TODAY - ed).days / 365.25)
                w = math.exp(-0.2 * years_ago)

        desc = (role.get("description", "") or "").lower()
        raw = 0.0
        for term, weight in DESC_TERMS.items():
            if term in desc:
                raw += weight
                all_matched.add(term)

        # Cap per-role contribution at 1.0 before weighting
        weighted_score_sum += w * min(1.0, raw / _MAX_DESC_RAW)
        weight_sum += w

    if weight_sum == 0.0:
        return 0.0, []
    score = weighted_score_sum / weight_sum
    return min(1.0, score), sorted(all_matched)


# ── Public API ────────────────────────────────────────────────────────────────

def role_taxonomy(c: dict) -> dict:
    """Score a candidate's relevance to the Senior AI Engineer JD.

    Returns:
        role_relevance: float 0–1 (used in scoring.py composite)
        title_score:    raw current-title tier score
        history_title_score: best recency-weighted history title score
        desc_term_score: ML description term density score
        matched_terms:  list of JD-signal terms found in descriptions
    """
    title_s = _title_score(schema.get_current_title(c))
    hist_s = _history_title_score(c)
    desc_s, matched = _desc_term_score(c)

    best_title = max(title_s, hist_s)
    # Title is the gate; description differentiates within ML pool.
    # Formula: best_title * (0.5 + 0.5 * desc_score)
    # Range per tier: Tier-1 [0.5, 1.0], Tier-2 [0.375, 0.75]
    role_relevance = best_title * (0.5 + 0.5 * desc_s)

    return {
        "role_relevance": round(role_relevance, 4),
        "title_score": round(title_s, 4),
        "history_title_score": round(hist_s, 4),
        "desc_term_score": round(desc_s, 4),
        "matched_terms": matched,
    }
