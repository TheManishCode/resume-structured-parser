"""
src/schema.py

Safe field accessors for candidate records per candidate_schema.json.
Nothing outside this module should string-literal a JSON key for candidate data.
All accessors are tolerant of missing optional fields and return sane defaults
rather than raising, since 100K real-world-shaped records will have edge cases.
"""
from __future__ import annotations
from typing import Any
from datetime import datetime, date


def get_candidate_id(c: dict) -> str:
    return c.get("candidate_id", "")


def get_years_experience(c: dict) -> float:
    return float(c.get("profile", {}).get("years_of_experience", 0.0) or 0.0)


def get_current_title(c: dict) -> str:
    return c.get("profile", {}).get("current_title", "") or ""


def get_current_company(c: dict) -> str:
    return c.get("profile", {}).get("current_company", "") or ""


def get_current_industry(c: dict) -> str:
    return c.get("profile", {}).get("current_industry", "") or ""


def get_location(c: dict) -> str:
    return c.get("profile", {}).get("location", "") or ""


def get_country(c: dict) -> str:
    return c.get("profile", {}).get("country", "") or ""


def get_headline(c: dict) -> str:
    return c.get("profile", {}).get("headline", "") or ""


def get_summary(c: dict) -> str:
    return c.get("profile", {}).get("summary", "") or ""


def get_career_history(c: dict) -> list[dict]:
    return c.get("career_history", []) or []


def get_education(c: dict) -> list[dict]:
    return c.get("education", []) or []


def get_skills(c: dict) -> list[dict]:
    return c.get("skills", []) or []


def get_skill_names(c: dict) -> list[str]:
    return [s.get("name", "") for s in get_skills(c) if s.get("name")]


def get_redrob_signals(c: dict) -> dict:
    return c.get("redrob_signals", {}) or {}


def sum_career_duration_months(c: dict) -> int:
    total = 0
    for role in get_career_history(c):
        dm = role.get("duration_months")
        if isinstance(dm, (int, float)):
            total += int(dm)
    return total


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def all_career_text(c: dict) -> str:
    """Concatenate all free-text fields most likely to carry real signal:
    career_history descriptions + titles. Deliberately EXCLUDES `summary`,
    which sample inspection showed is a templated/mismatched field in this
    synthetic dataset (see HANDOFF_CONTEXT.md)."""
    parts = []
    parts.append(get_current_title(c))
    for role in get_career_history(c):
        parts.append(role.get("title", "") or "")
        parts.append(role.get("description", "") or "")
    return " | ".join(p for p in parts if p)


def all_titles(c: dict) -> list[str]:
    titles = [get_current_title(c)]
    for role in get_career_history(c):
        t = role.get("title", "")
        if t:
            titles.append(t)
    return titles
