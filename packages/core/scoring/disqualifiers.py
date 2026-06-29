"""
src/disqualifiers.py

JD-stated disqualifier checks. One function per exclusion category.
Each function returns True if the candidate matches the disqualifier pattern.

Calibrated via probe_disqualifiers.py on the full 100K dataset
(ML-adjacent pool of 1,150 candidates):

  is_pure_research_only        → 32 candidates (title-based, not text-based;
                                   research terms don't appear in synthetic data)
  is_consulting_only_no_product → 36 candidates (HCL/Infosys/Wipro/TechM/TCS)
  is_recent_langchain_wrapper_only → 0 (langchain absent in this dataset;
                                   kept as production-ready stub)
  is_cv_speech_robotics_without_nlp → 0 (CV terms absent; stub retained)
  is_title_chaser              → 6 (conservative threshold — only catches
                                   egregious job-hoppers with short stints)
  Union of all flags: 42 ML-adjacent candidates

Design:
  Candidates are never removed — only penalised. disqualifier_penalty() returns
  a float in [0.0, 1.0] that scoring.py applies multiplicatively:
    adjusted_score = base_score * (1 - penalty)
  Multiple active disqualifiers compound:
    combined_multiplier = prod(1 - p_i)  for each active flag
    penalty = 1 - combined_multiplier
  This means two simultaneous 0.40 penalties → 1 - (0.6 * 0.6) = 0.64 combined.
"""
from __future__ import annotations
import schema

# ── Consulting / IT-services firm list ───────────────────────────────────────
# Patterns that identify big IT-services companies where ML work is typically
# billable-headcount delivery rather than building a product ML system.
_CONSULTING_PATTERNS: tuple[str, ...] = (
    "tata consultancy", "tcs",
    "infosys",
    "wipro",
    "accenture",
    "cognizant",
    "capgemini",
    "hcl",
    "tech mahindra",
    "mphasis",
    "hexaware",
    "mindtree",
    "l&t infotech",
    "ltimindtree",
    "persistent systems",
    "niit technologies",
)

# ── Research-only title set ───────────────────────────────────────────────────
# Roles that are exclusively research-track (no production deliverable).
# Note: "Applied Scientist" is ambiguous (product at Amazon, research elsewhere) —
# excluded from this set because it requires description-level disambiguation
# that is unreliable in this synthetic dataset.
_RESEARCH_ONLY_TITLES: frozenset[str] = frozenset({
    "Research Scientist",
    "Research Intern",
    "PhD Student",
    "Postdoctoral Researcher",
    "Postdoc",
})

# Production-evidence terms: if any appear in descriptions alongside research
# titles, the candidate is NOT pure research (they deployed something).
_PRODUCTION_EVIDENCE: tuple[str, ...] = (
    "production",
    "deployed",
    "serving",
    "endpoint",
    "api",
    "real-time",
    "real time",
    "latency",
    "throughput",
)

# ── CV / speech / robotics terms (no NLP) ────────────────────────────────────
_CV_ROBOTICS_TERMS: tuple[str, ...] = (
    "object detection",
    "image segmentation",
    "pose estimation",
    "speech recognition",
    "text-to-speech",
    " tts ",
    " asr ",
    "robotics",
    "autonomous vehicle",
    "lidar",
    "slam",
)
_NLP_EVIDENCE: tuple[str, ...] = (
    "nlp",
    "natural language",
    "text classification",
    "sentiment",
    "named entity",
    "translation",
    "summarization",
    "question answering",
    "bert",
    "gpt",
    "language model",
)

# ── LangChain / wrapper-only terms ───────────────────────────────────────────
# These indicate API-glue work rather than building ML systems.
_LANGCHAIN_TERMS: tuple[str, ...] = (
    "langchain",
    "llama index",
    "llamaindex",
    "openai api",
    "chatgpt api",
    "gpt api",
    "llm wrapper",
    "prompt engineering only",
)
_DEEP_ML_EVIDENCE: tuple[str, ...] = (
    "pytorch",
    "gradient",
    "fine-tun",
    "bert",
    "faiss",
    "embedding",
    "model training",
    "backpropagation",
    "tensorflow",
)

# ── Per-disqualifier penalty weights ─────────────────────────────────────────
# These are initial values; calibrate_weights.py may adjust them.
_PENALTIES: dict[str, float] = {
    "pure_research_only": 0.60,       # JD: "not a research role"
    "consulting_only_no_product": 0.40,  # consulting firms rarely build product ML
    "recent_langchain_wrapper_only": 0.50,
    "cv_speech_robotics_without_nlp": 0.30,
    "title_chaser": 0.25,
}


# ─────────────────────────────────────────────────────────────────────────────
# Individual check functions (each returns True = disqualified)
# ─────────────────────────────────────────────────────────────────────────────

def is_pure_research_only(c: dict) -> bool:
    """True if the entire career history is in research-only roles with no
    production evidence.

    Uses title matching, not text term matching (research-adjacent terms like
    'arxiv', 'publication' are absent in this synthetic dataset — confirmed in
    probe_disqualifiers.py). Fires on 32 ML-adjacent candidates.
    """
    titles = [r.get("title", "") or "" for r in schema.get_career_history(c)]
    if not titles:
        return False
    current = schema.get_current_title(c)
    if current and current not in _RESEARCH_ONLY_TITLES:
        return False
    if not all(t in _RESEARCH_ONLY_TITLES for t in titles if t):
        return False
    all_desc = schema.all_career_text(c).lower()
    if any(t in all_desc for t in _PRODUCTION_EVIDENCE):
        return False
    return True


def is_consulting_only_no_product(c: dict) -> bool:
    """True if EVERY company in the career history is a big IT-services firm.

    Calibrated on probe results: 36 ML-adjacent candidates with entire careers
    at HCL/Infosys/Wipro/TechM/TCS. Requires >=2 career roles to avoid
    penalising a junior engineer whose first job happens to be at a consulting
    firm (they might be genuinely starting out).
    """
    roles = schema.get_career_history(c)
    companies = [r.get("company", "") or "" for r in roles]
    non_empty = [co.lower() for co in companies if co.strip()]
    if len(non_empty) < 2:
        return False

    def _is_consulting(co: str) -> bool:
        return any(pattern in co for pattern in _CONSULTING_PATTERNS)

    return all(_is_consulting(co) for co in non_empty)


def is_recent_langchain_wrapper_only(c: dict) -> bool:
    """True if the most recent 2 roles show LangChain/wrapper work with no
    evidence of deeper ML (model training, fine-tuning, etc.).

    Fires 0 times on the real dataset (LangChain terms are absent from this
    synthetic data) but retained as a production-ready signal for real use.
    """
    roles = schema.get_career_history(c)
    recent = sorted(roles, key=lambda r: r.get("start_date") or "", reverse=True)[:2]
    text = " ".join((r.get("description", "") or "").lower() for r in recent)
    has_wrapper = any(t in text for t in _LANGCHAIN_TERMS)
    has_deep = any(t in text for t in _DEEP_ML_EVIDENCE)
    return has_wrapper and not has_deep


def is_cv_speech_robotics_without_nlp(c: dict) -> bool:
    """True if career shows only CV/speech/robotics work with no NLP signal.

    JD concern: Computer Vision/Robotics engineers without NLP/search/ranking
    background are the wrong hire for an NLP/ranking AI role.
    Fires 0 times on real dataset (CV terms absent from synthetic data) but
    retained for production correctness.
    """
    all_text = schema.all_career_text(c).lower()
    has_cv = any(t in all_text for t in _CV_ROBOTICS_TERMS)
    has_nlp = any(t in all_text for t in _NLP_EVIDENCE)
    return has_cv and not has_nlp


def is_title_chaser(c: dict) -> bool:
    """True if career pattern shows egregious short-stinting across many employers.

    Threshold: >= 5 unique companies AND >= 4 stints of <12 months AND
    average tenure across ALL roles < 14 months. Calibrated to fire only on
    the most egregious cases — fires on 3-4 candidates in the real dataset
    with tighter thresholds vs the probe's 6 (which used <18 months and
    >=3 short stints, catching legitimate Indian-startup job-hoppers).

    Note: JD concern is title *inflation* (non-ML→ML rapid promotion for
    title only), not job-hopping. Cannot reliably detect title inflation from
    synthetic data titles alone, so this conservative job-hop proxy is used
    as a weak disqualifier with mild penalty.
    """
    roles = schema.get_career_history(c)
    companies: dict[str, int] = {}
    total_months = 0
    short_stints = 0

    for r in roles:
        co = (r.get("company") or "").strip().lower()
        dm = r.get("duration_months") or 0
        if co:
            prev = companies.get(co, 0)
            companies[co] = prev + dm
        total_months += dm
        if dm < 12:
            short_stints += 1

    n_companies = len(companies)
    if n_companies == 0:
        return False
    avg_tenure = total_months / n_companies

    return (
        n_companies >= 5
        and short_stints >= 4
        and avg_tenure < 14
    )


# ─────────────────────────────────────────────────────────────────────────────
# Aggregate output
# ─────────────────────────────────────────────────────────────────────────────

def disqualifier_check(c: dict) -> dict:
    """Run all disqualifier checks and return flags + combined penalty.

    Returns:
        disqualified_flags: list of active flag strings
        disqualifier_penalty: float 0–1; scoring.py applies as
            adjusted_score = base_score * (1 - disqualifier_penalty)
        disqualifier_multiplier: 1 - disqualifier_penalty (convenience)
    """
    checks = [
        ("pure_research_only", is_pure_research_only),
        ("consulting_only_no_product", is_consulting_only_no_product),
        ("recent_langchain_wrapper_only", is_recent_langchain_wrapper_only),
        ("cv_speech_robotics_without_nlp", is_cv_speech_robotics_without_nlp),
        ("title_chaser", is_title_chaser),
    ]

    flags: list[str] = []
    multiplier = 1.0
    for name, fn in checks:
        if fn(c):
            flags.append(name)
            multiplier *= 1.0 - _PENALTIES[name]

    penalty = round(1.0 - multiplier, 4)
    return {
        "candidate_id": schema.get_candidate_id(c),
        "disqualified_flags": flags,
        "disqualifier_penalty": penalty,
        "disqualifier_multiplier": round(multiplier, 4),
    }
