"""
packages/core/analysis/ats_analyzer.py

Two analysis modes:
  1. analyze_resume(text, jd, metadata)  — resume vs job description (scored match)
  2. check_ats_only(text)                — standalone ATS audit (no JD required)

All scores are integers 0–100. Rule-based signals feed into every LLM prompt
so scores are grounded in objective evidence, not hallucination.
"""
from __future__ import annotations

import json
import logging
import os
import re
import textwrap
import unicodedata

import httpx

logger = logging.getLogger(__name__)

# ── Shared constants ──────────────────────────────────────────────────────────

_SECTION_MARKERS = [
    "experience", "work experience", "employment", "employment history",
    "professional experience", "career history",
    "education", "academic background", "academic history",
    "skills", "technical skills", "core competencies", "key skills",
    "projects", "personal projects", "portfolio", "side projects",
    "summary", "professional summary", "objective", "profile", "about me",
    "certifications", "certificates", "licenses", "credentials",
    "achievements", "awards", "honors", "publications",
    "volunteer", "volunteering", "community", "languages",
    "contact", "contact information",
]

_STRONG_VERBS = {
    "led", "built", "designed", "developed", "implemented", "launched",
    "managed", "delivered", "reduced", "increased", "improved", "created",
    "architected", "scaled", "optimized", "automated", "migrated",
    "established", "drove", "achieved", "spearheaded", "owned", "shipped",
    "deployed", "integrated", "mentored", "negotiated", "transformed",
    "generated", "exceeded", "streamlined", "pioneered", "accelerated",
    "founded", "directed", "coordinated", "facilitated", "supervised",
    "analyzed", "evaluated", "researched", "authored", "presented",
    "collaborated", "partnered", "advised", "consulted", "resolved",
    "troubleshot", "debugged", "refactored", "engineered", "modeled",
}

_SOFT_SKILL_BLOAT = {
    "hardworking", "passionate", "team player", "results-driven", "self-starter",
    "go-getter", "detail-oriented", "motivated", "enthusiastic", "dynamic",
    "synergy", "leverage", "utilize", "proactive",
}

# ATS-hostile patterns: fancy bullets/chars that confuse older parsers
_FANCY_CHARS = re.compile(r"[•‣◦⁃∙»«ﬁﬂ]")


# ── Rule-based signal extraction ─────────────────────────────────────────────

def _extract_signals(text: str) -> dict:
    """Compute objective, rule-based signals from resume text."""
    text_low = text.lower()
    lines    = text.splitlines()

    # Sections present
    sections_found = sorted({s for s in _SECTION_MARKERS if s in text_low})

    # Bullet lines: lines starting with bullet char OR lines that are indented content points
    bullet_lines = [
        l.strip() for l in lines
        if l.strip() and (
            l.strip()[0] in "-•*·▪▸▹►–—◦◉○●"
            or re.match(r"^\s{2,}\S", l)
        )
    ]
    # Quantified: bullet with a number, percentage, dollar, multiplier
    quantified = sum(
        1 for l in bullet_lines
        if re.search(r"\d+\s*[%$kmMbB]?\b|\$\s*\d+|\d+x\b|\d+\+|\d{2,}%", l)
    )
    quant_ratio = round(quantified / len(bullet_lines), 3) if bullet_lines else 0.0

    # Action verbs
    words = set(text_low.split())
    action_count = len(words & _STRONG_VERBS)
    soft_bloat   = len(words & _SOFT_SKILL_BLOAT)

    # Length
    word_count = len(text.split())

    # Contact info
    has_email    = bool(re.search(r"[\w.+\-]+@[\w\-]+\.\w{2,}", text))
    has_phone    = bool(re.search(r"[\+\d][\d\s\-().]{7,18}\d", text))
    has_linkedin = "linkedin.com" in text_low
    has_github   = "github.com" in text_low
    has_location = bool(re.search(
        r"\b(San Francisco|New York|NYC|London|Berlin|Austin|Seattle|"
        r"Boston|Chicago|Remote|[A-Z][a-z]+,\s*[A-Z]{2})\b", text
    ))
    has_portfolio = bool(re.search(r"https?://(?!linkedin|github)", text_low))

    # Date pattern consistency check
    date_formats = re.findall(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
        r"|\b\d{1,2}/\d{4}\b|\b\d{4}\b",
        text, re.IGNORECASE
    )

    # Tables / columns heuristics (from text extraction artifacts)
    pipe_lines   = sum(1 for l in lines if l.count("|") >= 2)
    tab_lines    = sum(1 for l in lines if "\t" in l)

    # Fancy character ATS risk
    fancy_count = len(_FANCY_CHARS.findall(text))

    # All-caps lines (often headings — fine, but count for context)
    allcaps_lines = sum(1 for l in lines if l.strip().isupper() and len(l.strip()) > 2)

    return {
        "sections_found":   sections_found,
        "section_count":    len(sections_found),
        "bullet_count":     len(bullet_lines),
        "quantified":       quantified,
        "quant_ratio":      quant_ratio,
        "action_count":     action_count,
        "soft_bloat":       soft_bloat,
        "word_count":       word_count,
        "has_email":        has_email,
        "has_phone":        has_phone,
        "has_linkedin":     has_linkedin,
        "has_github":       has_github,
        "has_location":     has_location,
        "has_portfolio":    has_portfolio,
        "date_formats":     date_formats[:8],
        "pipe_lines":       pipe_lines,
        "tab_lines":        tab_lines,
        "fancy_count":      fancy_count,
        "allcaps_lines":    allcaps_lines,
    }


# ── ATS-only scoring ──────────────────────────────────────────────────────────

def _score_parsability(s: dict, text: str) -> tuple[int, list[dict]]:
    """Return (score 0-100, issues[])."""
    score  = 100
    issues = []

    if s["pipe_lines"] > 3:
        score -= 20
        issues.append({"severity": "high",
                        "message": f"Tables detected ({s['pipe_lines']} lines with | separators). "
                                    "Most ATS systems cannot parse table layouts — "
                                    "convert to plain bullet lists."})

    if s["tab_lines"] > 5:
        score -= 10
        issues.append({"severity": "medium",
                        "message": "Tab-indented layout suggests a multi-column structure. "
                                   "ATS parsers read left-to-right and can misorder tabbed text."})

    if s["fancy_count"] > 0:
        score -= min(10, s["fancy_count"] * 2)
        issues.append({"severity": "medium",
                        "message": f"{s['fancy_count']} special bullet character(s) found "
                                   "(•▸►). Replace with standard hyphens (-) or ASCII bullets "
                                   "for maximum ATS compatibility."})

    if s["word_count"] < 200:
        score -= 25
        issues.append({"severity": "high",
                        "message": f"Resume is very short ({s['word_count']} words). "
                                   "ATS systems may not extract enough signal. "
                                   "Aim for 400–800 words."})

    if s["section_count"] < 3:
        score -= 20
        issues.append({"severity": "high",
                        "message": f"Only {s['section_count']} standard section(s) detected. "
                                   "Missing clear section headers causes ATS mis-classification."})

    return max(0, score), issues


def _score_contact(s: dict) -> tuple[int, list[dict]]:
    score  = 0
    issues = []

    if s["has_email"]:   score += 35
    else: issues.append({"severity": "high",   "message": "No email address found. Every ATS requires it."})

    if s["has_phone"]:   score += 25
    else: issues.append({"severity": "high",   "message": "No phone number found."})

    if s["has_location"]: score += 15
    else: issues.append({"severity": "medium", "message": "No location found. Many ATS systems filter by location."})

    if s["has_linkedin"]: score += 15
    else: issues.append({"severity": "low",    "message": "No LinkedIn URL. Recruiters expect it for verification."})

    if s["has_github"] or s["has_portfolio"]: score += 10

    return min(100, score), issues


def _score_content(s: dict) -> tuple[int, list[dict]]:
    score  = 100
    issues = []

    # Word count
    wc = s["word_count"]
    if wc < 300:
        score -= 30
        issues.append({"severity": "high",   "message": f"Too short ({wc} words). Expand experience descriptions."})
    elif wc < 400:
        score -= 15
        issues.append({"severity": "medium", "message": f"Resume is concise ({wc} words). Consider adding more detail."})
    elif wc > 1400:
        score -= 10
        issues.append({"severity": "medium", "message": f"Resume is long ({wc} words). Trim to 2 pages max."})

    # Quantification
    if s["bullet_count"] > 5 and s["quant_ratio"] < 0.10:
        score -= 25
        issues.append({"severity": "high",
                        "message": f"Only {s['quantified']}/{s['bullet_count']} bullet points contain numbers. "
                                   "Quantify at least 40% of achievements (e.g. 'Reduced latency by 30%', "
                                   "'Managed team of 8')."})
    elif s["quant_ratio"] < 0.25 and s["bullet_count"] > 3:
        score -= 10
        issues.append({"severity": "medium",
                        "message": f"Quantification ratio is {s['quant_ratio']:.0%}. "
                                   "Aim to quantify at least 40% of bullet points."})

    # Action verbs
    if s["action_count"] < 5:
        score -= 20
        issues.append({"severity": "high",
                        "message": f"Only {s['action_count']} strong action verbs found. "
                                   "Start each bullet with a power verb: Led, Built, Reduced, Launched, etc."})
    elif s["action_count"] < 10:
        score -= 8
        issues.append({"severity": "medium",
                        "message": f"Consider more varied action verbs ({s['action_count']} found)."})

    # Soft skill bloat
    if s["soft_bloat"] >= 3:
        score -= 10
        issues.append({"severity": "medium",
                        "message": f"Buzzwords detected ('passionate', 'hardworking', 'results-driven'). "
                                   "Replace with specific achievements and data."})

    return max(0, score), issues


def _score_format(s: dict) -> tuple[int, list[dict]]:
    score  = 100
    issues = []

    # Key sections check
    has_exp  = any(x in s["sections_found"] for x in ["experience", "work experience", "employment", "employment history", "professional experience"])
    has_edu  = any(x in s["sections_found"] for x in ["education", "academic background"])
    has_sk   = any(x in s["sections_found"] for x in ["skills", "technical skills", "core competencies"])
    has_sum  = any(x in s["sections_found"] for x in ["summary", "professional summary", "objective", "profile"])

    if not has_exp:
        score -= 30
        issues.append({"severity": "high", "message": "No 'Experience' section detected. Add a clearly labeled Work Experience section."})
    if not has_edu:
        score -= 15
        issues.append({"severity": "high", "message": "No 'Education' section detected."})
    if not has_sk:
        score -= 15
        issues.append({"severity": "medium", "message": "No 'Skills' section detected. Add a dedicated Skills section with explicit keywords."})
    if not has_sum:
        score -= 5
        issues.append({"severity": "low", "message": "No summary/profile section. A 2-3 sentence professional summary improves ATS keyword matching."})

    # Date formats: should use consistent format
    if len(s["date_formats"]) < 2:
        score -= 8
        issues.append({"severity": "medium", "message": "No recognizable employment dates found. ATS systems use dates to compute tenure."})

    return max(0, score), issues


def _compute_ats_scores(s: dict, text: str) -> tuple[dict, list[dict]]:
    p_score, p_issues = _score_parsability(s, text)
    c_score, c_issues = _score_contact(s)
    ct_score, ct_issues = _score_content(s)
    f_score, f_issues = _score_format(s)
    all_issues = p_issues + c_issues + ct_issues + f_issues

    overall = int(0.30 * p_score + 0.25 * c_score + 0.25 * ct_score + 0.20 * f_score)

    return {
        "overall_ats_score":  max(0, min(100, overall)),
        "parsability_score":  p_score,
        "contact_score":      c_score,
        "content_score":      ct_score,
        "format_score":       f_score,
    }, all_issues


# ── LLM call chain ────────────────────────────────────────────────────────────

async def _call_llm(prompt: str, max_tokens: int = 1600) -> dict:
    """ApeKey → Claude → Groq priority chain."""
    errors = []

    if os.getenv("APEKEY_AI_API_KEY"):
        try:
            return await _call_apekey(prompt, max_tokens)
        except Exception as e:
            errors.append(f"ApeKey: {e}")
            logger.warning("ApeKey call failed: %s", e)

    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return await _call_claude(prompt, max_tokens)
        except Exception as e:
            errors.append(f"Claude: {e}")
            logger.warning("Claude call failed: %s", e)

    if os.getenv("GROQ_API_KEY"):
        try:
            return await _call_groq(prompt, max_tokens)
        except Exception as e:
            errors.append(f"Groq: {e}")
            logger.warning("Groq call failed: %s", e)

    raise RuntimeError(
        f"No LLM available. Set APEKEY_AI_API_KEY, ANTHROPIC_API_KEY, or GROQ_API_KEY. "
        f"Tried: {'; '.join(errors)}"
    )


async def _call_apekey(prompt: str, max_tokens: int) -> dict:
    key      = os.getenv("APEKEY_AI_API_KEY", "")
    base_url = os.getenv("APEKEY_AI_BASE_URL", "https://api.apekey.ai/v1").rstrip("/")
    model    = os.getenv("APEKEY_AI_MODEL", "gpt-4o")
    async with httpx.AsyncClient(timeout=55.0) as c:
        r = await c.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system",
                     "content": "You are an expert ATS analyst and resume coach. Respond with valid JSON only. No markdown fences."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.15,
                "max_tokens":  max_tokens,
                "response_format": {"type": "json_object"},
            },
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        return _parse_json(raw)


async def _call_claude(prompt: str, max_tokens: int) -> dict:
    key   = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")  # haiku: fast + cheap
    async with httpx.AsyncClient(timeout=55.0) as c:
        r = await c.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "system": "You are an expert ATS analyst and resume coach. Respond with valid JSON only. No markdown fences.",
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        raw = r.json()["content"][0]["text"].strip()
        return _parse_json(raw)


async def _call_groq(prompt: str, max_tokens: int) -> dict:
    key   = os.getenv("GROQ_API_KEY", "")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    async with httpx.AsyncClient(timeout=45.0) as c:
        r = await c.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system",
                     "content": "You are an expert ATS analyst and resume coach. Respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.15,
                "max_tokens":  max_tokens,
                "response_format": {"type": "json_object"},
            },
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    """Parse JSON, stripping markdown fences if present."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ── Mode 1: Job-match analysis ────────────────────────────────────────────────

def _match_prompt(resume_text: str, jd: str, signals: dict) -> str:
    return textwrap.dedent(f"""
        You are a senior ATS expert and executive resume coach.

        Analyze the resume against the job description and return a detailed JSON assessment.

        ── JOB DESCRIPTION ──────────────────────────────────────────────────────────
        {jd[:5000]}

        ── RESUME ───────────────────────────────────────────────────────────────────
        {resume_text[:4500]}

        ── PRE-COMPUTED SIGNALS (base your scores on these) ────────────────────────
        Sections detected:    {signals['sections_found']}
        Bullet points:        {signals['bullet_count']} total, {signals['quantified']} quantified ({signals['quant_ratio']:.0%})
        Action verbs found:   {signals['action_count']}
        Word count:           {signals['word_count']} (ideal 400–900)
        Contact: email={signals['has_email']} phone={signals['has_phone']} linkedin={signals['has_linkedin']}

        ── OUTPUT (JSON only, no markdown fences) ───────────────────────────────────
        {{
          "overall_score":       <int 0-100, weighted: 0.30*ats + 0.25*keyword + 0.25*skills + 0.10*exp + 0.10*format>,
          "ats_score":           <int 0-100, keyword density + critical terms + parsability>,
          "keyword_match_score": <int 0-100, strict — only count JD terms genuinely present verbatim>,
          "skills_match_score":  <int 0-100, required vs present skills>,
          "experience_score":    <int 0-100, seniority + relevance to JD>,
          "format_score":        <int 0-100, use pre-computed signals: sections, quant, word count>,
          "matched_keywords":    [<up to 20 JD keywords found in resume>],
          "missing_keywords":    [<up to 15 important JD keywords NOT in resume>],
          "strengths":           [<3-5 evidence-based strengths with specific resume quotes>],
          "improvements":        [<5-7 specific, actionable fixes: name the EXACT change and WHERE to make it>],
          "red_flags":           [<genuine dealbreakers, empty list [] if none>],
          "job_title":           "<inferred title from JD>",
          "company":             "<company from JD or null>",
          "seniority_match":     "<match|overqualified|underqualified>",
          "summary":             "<2-3 honest sentences. Lead with the most important finding.>"
        }}

        Rules:
        - improvements must be specific. Bad: "Add more keywords". Good: "Add 'TypeScript' to your Skills section — it appears 7 times in the JD and is absent from your resume."
        - format_score must reflect the pre-computed signals above
        - Never mention the candidate's name, school prestige, or graduation year
        - JSON only. No text outside the object.
    """).strip()


async def analyze_resume(
    resume_text: str,
    job_description: str,
    job_metadata: dict | None = None,
) -> dict:
    """Analyze resume against a job description. Returns structured dict."""
    signals = _extract_signals(resume_text)
    prompt  = _match_prompt(resume_text, job_description, signals)
    result  = await _call_llm(prompt, max_tokens=1800)

    # Defaults
    for k, v in [
        ("overall_score", 0), ("ats_score", 0), ("keyword_match_score", 0),
        ("skills_match_score", 0), ("experience_score", 0), ("format_score", 0),
        ("matched_keywords", []), ("missing_keywords", []),
        ("strengths", []), ("improvements", []), ("red_flags", []),
        ("job_title", None), ("company", None),
        ("seniority_match", "unknown"), ("summary", ""),
    ]:
        result.setdefault(k, v)

    # Clamp scores
    for k in ("overall_score", "ats_score", "keyword_match_score",
               "skills_match_score", "experience_score", "format_score"):
        result[k] = max(0, min(100, int(result.get(k) or 0)))

    # Patch metadata if LLM left blanks
    if job_metadata:
        if not result["job_title"] and job_metadata.get("title"):
            result["job_title"] = job_metadata["title"]
        if not result["company"] and job_metadata.get("company"):
            result["company"] = job_metadata["company"]

    # Augment with rule signals
    result["resume_word_count"] = signals["word_count"]
    result["sections_found"]    = signals["sections_found"]
    result["quant_ratio"]       = signals["quant_ratio"]
    result["has_contact_info"]  = signals["has_email"] and signals["has_phone"]

    return result


# ── Mode 2: Standalone ATS check ─────────────────────────────────────────────

def _ats_prompt(resume_text: str, signals: dict, issues: list[dict]) -> str:
    issue_summary = "; ".join(i["message"][:80] for i in issues[:5]) or "none"
    return textwrap.dedent(f"""
        You are an expert resume writer and ATS consultant.

        Audit this resume for ATS friendliness and overall quality WITHOUT a specific job description.
        The pre-computed rule engine has already flagged these issues: {issue_summary}

        ── RESUME ───────────────────────────────────────────────────────────────────
        {resume_text[:5000]}

        ── PRE-COMPUTED SIGNALS ─────────────────────────────────────────────────────
        Sections found:     {signals['sections_found']}
        Word count:         {signals['word_count']} words
        Bullets:            {signals['bullet_count']} total, {signals['quantified']} quantified ({signals['quant_ratio']:.0%})
        Action verbs:       {signals['action_count']} found
        Contact: email={signals['has_email']} phone={signals['has_phone']} linkedin={signals['has_linkedin']} location={signals['has_location']}
        Possible tables:    {signals['pipe_lines']} pipe-separator lines
        Fancy chars:        {signals['fancy_count']}

        ── OUTPUT (JSON only) ───────────────────────────────────────────────────────
        {{
          "strengths":           [<3-5 genuine strengths with specific evidence from the resume>],
          "improvements":        [<5-7 specific improvements — name the exact section and change>],
          "skills_extracted":    [<up to 20 actual skills and technologies found in the resume>],
          "suggested_keywords":  [<10-15 common keywords this resume is MISSING that candidates in this field typically include>],
          "career_level":        "<entry|mid|senior|lead|executive — inferred from experience>",
          "likely_roles":        [<3-5 job titles this resume is best suited for>],
          "summary":             "<2-3 sentence honest assessment of the resume's overall quality and readiness>"
        }}

        Rules:
        - Base your response on what you actually see in the resume, not generic advice
        - improvements must name the exact fix: "Add measurable outcomes to your TechCorp bullet points: specify the impact in % or $ terms"
        - Never mention name, school prestige, or demographic signals
        - JSON only.
    """).strip()


async def check_ats_only(resume_text: str) -> dict:
    """
    Standalone ATS audit without a job description.
    Returns ATS scores, issues, and qualitative LLM feedback.
    """
    signals  = _extract_signals(resume_text)
    scores, rule_issues = _compute_ats_scores(signals, resume_text)

    # Sort issues: high → medium → low
    _sev = {"high": 0, "medium": 1, "low": 2}
    rule_issues.sort(key=lambda x: _sev.get(x["severity"], 3))

    # LLM qualitative pass
    try:
        llm = await _call_llm(_ats_prompt(resume_text, signals, rule_issues), max_tokens=1400)
    except Exception as exc:
        logger.warning("ATS-only LLM call failed: %s", exc)
        llm = {}

    llm.setdefault("strengths",          [])
    llm.setdefault("improvements",       [])
    llm.setdefault("skills_extracted",   [])
    llm.setdefault("suggested_keywords", [])
    llm.setdefault("career_level",       "unknown")
    llm.setdefault("likely_roles",       [])
    llm.setdefault("summary",            "")

    # Contact completeness details
    contact_detail = {
        "has_email":     signals["has_email"],
        "has_phone":     signals["has_phone"],
        "has_linkedin":  signals["has_linkedin"],
        "has_github":    signals["has_github"],
        "has_location":  signals["has_location"],
        "has_portfolio": signals["has_portfolio"],
    }

    # Sections present/missing
    key_sections = {
        "contact":      any(x in signals["sections_found"] for x in ["contact", "contact information"]),
        "summary":      any(x in signals["sections_found"] for x in ["summary", "objective", "profile", "professional summary", "about me"]),
        "experience":   any(x in signals["sections_found"] for x in ["experience", "work experience", "employment", "professional experience"]),
        "education":    any(x in signals["sections_found"] for x in ["education", "academic background"]),
        "skills":       any(x in signals["sections_found"] for x in ["skills", "technical skills", "core competencies"]),
        "projects":     any(x in signals["sections_found"] for x in ["projects", "personal projects", "portfolio"]),
        "certifications": any(x in signals["sections_found"] for x in ["certifications", "certificates", "licenses"]),
    }

    return {
        **scores,
        "issues":           rule_issues,
        "contact_detail":   contact_detail,
        "key_sections":     key_sections,
        "word_count":       signals["word_count"],
        "bullet_count":     signals["bullet_count"],
        "quantified_count": signals["quantified"],
        "quant_ratio":      signals["quant_ratio"],
        "action_verbs":     signals["action_count"],
        **llm,
    }
