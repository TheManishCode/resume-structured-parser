"""
packages/core/scraper/job_scraper.py

Multi-strategy job description scraper.

Priority chain per URL:
  1. Platform-specific lightweight extractor (Greenhouse, Lever, Ashby — simple HTML, no JS)
  2. Jina AI Reader  (https://r.jina.ai/{url}) — cloud-rendered, handles LinkedIn/Indeed/JS sites
  3. Direct httpx + BeautifulSoup fallback

Jina is the workhorse for gated sites (LinkedIn, Indeed, Glassdoor).
It renders JavaScript, bypasses most anti-bot measures, and returns clean markdown.
No API key required for public usage.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Chrome 120 headers — realistic enough for most scrapers
_CHROME = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "max-age=0",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

_JINA_TIMEOUT  = 30.0
_DIRECT_TIMEOUT = 18.0


class ScrapeError(Exception):
    pass


# ── Public entry point ────────────────────────────────────────────────────────

async def scrape_job(url: str) -> dict:
    """
    Scrape a job posting from any URL.

    Returns: {title, company, description, source}
    Raises ScrapeError if all strategies fail.
    """
    url = url.strip()
    domain = urlparse(url).netloc.lower()

    # Greenhouse and Lever: lightweight, public, no JS needed
    if "greenhouse.io" in domain or "boards.greenhouse" in domain:
        try:
            return await _greenhouse(url)
        except Exception as exc:
            logger.info("Greenhouse direct failed, trying Jina: %s", exc)

    if "lever.co" in domain:
        try:
            return await _lever(url)
        except Exception as exc:
            logger.info("Lever direct failed, trying Jina: %s", exc)

    if "ashbyhq.com" in domain:
        try:
            return await _ashby(url)
        except Exception as exc:
            logger.info("Ashby direct failed, trying Jina: %s", exc)

    # For LinkedIn, Indeed, Glassdoor, Workday, and everything else — Jina first
    try:
        return await _jina_scrape(url, domain)
    except ScrapeError:
        pass  # fall through to direct

    # Last resort: direct HTTP + BeautifulSoup
    source = _detect_source(domain)
    try:
        return await _direct_scrape(url, source)
    except Exception as exc:
        raise ScrapeError(
            f"Could not fetch the job description from that URL. "
            f"The page may require a login or be behind a CAPTCHA. "
            f"Please paste the job description text directly. (Detail: {exc})"
        )


# ── Strategy 1: Jina AI Reader ────────────────────────────────────────────────

async def _jina_scrape(url: str, domain: str) -> dict:
    """
    Use Jina AI Reader (https://r.jina.ai/) to fetch any page as clean markdown.
    Free, no API key, handles JS-rendered pages and most anti-bot measures.
    """
    jina_url = f"https://r.jina.ai/{url}"
    try:
        async with httpx.AsyncClient(timeout=_JINA_TIMEOUT, follow_redirects=True) as c:
            resp = await c.get(
                jina_url,
                headers={
                    "Accept": "text/plain, text/markdown, */*",
                    "X-Return-Format": "markdown",
                    "X-No-Cache": "true",
                },
            )
            resp.raise_for_status()
            markdown = resp.text.strip()
    except httpx.HTTPStatusError as exc:
        raise ScrapeError(f"Jina reader returned {exc.response.status_code}")
    except Exception as exc:
        raise ScrapeError(f"Jina reader failed: {exc}")

    if not markdown or len(markdown) < 200:
        raise ScrapeError("Jina reader returned empty content")

    title, company = _parse_jina_meta(markdown, url)
    description    = _extract_jd_from_markdown(markdown)

    if not description or len(description) < 150:
        raise ScrapeError("Jina reader content too short after cleanup")

    source = _detect_source(domain)
    logger.info("Jina scraped %s chars from %s", len(description), source)
    return _job(title, company, description, source)


def _parse_jina_meta(markdown: str, url: str) -> tuple[str | None, str | None]:
    """Extract title and company from Jina markdown output."""
    title = company = None

    # Jina usually emits "Title: ..." and "URL Source: ..." in the first few lines
    for line in markdown.splitlines()[:30]:
        if line.lower().startswith("title:"):
            raw = line.split(":", 1)[1].strip()
            # "Senior Engineer at Acme | LinkedIn" → title + company
            if " at " in raw.lower():
                parts = re.split(r"\s+at\s+", raw, maxsplit=1, flags=re.IGNORECASE)
                title   = parts[0].strip()
                company = parts[1].split("|")[0].split("·")[0].split("-")[0].strip()
            elif " - " in raw or " | " in raw:
                parts  = re.split(r"\s*[-|]\s*", raw, maxsplit=1)
                title  = parts[0].strip()
            else:
                title = raw.split("|")[0].strip()
            break

    # Fallback: first H1 or H2
    if not title:
        h = re.search(r"^#{1,2}\s+(.+)$", markdown, re.MULTILINE)
        if h:
            title = h.group(1).strip()

    # Company from LinkedIn-style "Company · Location · Job type"
    if not company:
        m = re.search(r"\n([A-Z][^\n·|]{2,50})\s+·\s+", markdown)
        if m:
            company = m.group(1).strip()

    return title, company


def _extract_jd_from_markdown(markdown: str) -> str:
    """
    Extract the actual job description from Jina markdown output.
    Strips Jina metadata lines, nav menus, cookie banners, etc.
    """
    lines = markdown.splitlines()
    clean = []
    in_jd = False
    skip_patterns = re.compile(
        r"^(Title:|URL Source:|Published Time:|Markdown Content:|Warning:|"
        r"Sign in|Log in|Cookie|Accept all|Dismiss|Privacy|Skip to|"
        r"Toggle navigation|Back to search|\[.*\]\(http)",
        re.IGNORECASE,
    )

    # JD usually starts around a known heading
    jd_triggers = re.compile(
        r"about\s+the\s+(role|job|position|opportunity)|"
        r"job\s+description|overview|responsibilities|what\s+you.ll\s+do|"
        r"about\s+us|who\s+we\s+are|the\s+role|your\s+role|position\s+overview",
        re.IGNORECASE,
    )

    for line in lines:
        stripped = line.strip()
        if skip_patterns.match(stripped):
            continue
        if not in_jd and jd_triggers.search(stripped):
            in_jd = True
        if in_jd or len(clean) > 30:  # collect everything after enough context
            clean.append(line)

    if not clean:
        # No JD trigger found — just return content minus the first 5 metadata lines
        clean = lines[5:]

    text = "\n".join(clean).strip()

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove markdown image syntax
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # Limit to 8000 chars (more than enough for any JD)
    return text[:8000].strip()


# ── Strategy 2: Direct Greenhouse ────────────────────────────────────────────

async def _greenhouse(url: str) -> dict:
    html  = await _fetch(url, _DIRECT_TIMEOUT)
    soup  = BeautifulSoup(html, "lxml")
    title   = _text(soup.select_one("h1.app-title, h1"))
    company = _text(soup.select_one(".company-name, header h2, .company"))
    desc    = _text(soup.select_one("#content, .job-post-content, .section-wrapper"))
    if not desc or len(desc) < 150:
        desc = _largest_block(soup)
    _assert_desc(desc, "Greenhouse")
    return _job(title, company, desc, "greenhouse")


# ── Strategy 3: Direct Lever ─────────────────────────────────────────────────

async def _lever(url: str) -> dict:
    html = await _fetch(url, _DIRECT_TIMEOUT)
    soup = BeautifulSoup(html, "lxml")
    title   = _text(soup.select_one(".posting-headline h2, h2, h1"))
    host    = urlparse(url).hostname or ""
    company = _text(soup.select_one(".main-header-logo img")) or host.split(".")[0].title()
    desc    = _text(soup.select_one(".posting-description, #content, .section"))
    if not desc or len(desc) < 150:
        desc = _largest_block(soup)
    _assert_desc(desc, "Lever")
    return _job(title, company, desc, "lever")


# ── Strategy 4: Direct Ashby ─────────────────────────────────────────────────

async def _ashby(url: str) -> dict:
    html  = await _fetch(url, _DIRECT_TIMEOUT)
    soup  = BeautifulSoup(html, "lxml")
    title   = _text(soup.select_one("h1"))
    company = _text(soup.select_one("[class*='company'], [class*='org']"))
    desc    = _text(soup.select_one("[class*='description'], [class*='content'], main"))
    if not desc or len(desc) < 150:
        desc = _largest_block(soup)
    _assert_desc(desc, "Ashby")
    return _job(title, company, desc, "ashby")


# ── Strategy 5: Direct generic ────────────────────────────────────────────────

async def _direct_scrape(url: str, source: str = "generic") -> dict:
    html = await _fetch(url, _DIRECT_TIMEOUT)
    soup = BeautifulSoup(html, "lxml")

    for noise in soup.select("nav, header, footer, script, style, noscript, aside, iframe"):
        noise.decompose()

    title   = _text(soup.select_one("h1"))
    company = None

    desc = None
    for sel in [
        ".job-description", "#job-description", "[class*='jobDesc']",
        "[class*='job-desc']", ".job-details", "#job-details",
        "[class*='description']", "#description", ".description",
        ".posting-body", "[class*='posting']", "[class*='position-desc']",
        "main article", "article", "main", "#content", ".content",
    ]:
        el = soup.select_one(sel)
        if el:
            candidate = el.get_text(separator="\n", strip=True)
            if len(candidate) > 300:
                desc = candidate
                break

    if not desc or len(desc) < 200:
        desc = _largest_block(soup)

    _assert_desc(desc, "generic")
    return _job(title, company, desc, source)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fetch(url: str, timeout: float) -> str:
    async with httpx.AsyncClient(
        headers=_CHROME,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


def _text(el) -> str | None:
    if el is None:
        return None
    t = el.get_text(separator=" ", strip=True)
    return t.strip() if t.strip() else None


def _largest_block(soup: BeautifulSoup) -> str:
    """Return the largest contiguous text block on the page (usually the JD)."""
    best, best_len = "", 0
    for el in soup.find_all(["div", "section", "article"]):
        t = el.get_text(separator="\n", strip=True)
        if best_len < len(t) < 30_000:
            best, best_len = t, len(t)
    return best


def _assert_desc(desc: str | None, source: str) -> None:
    if not desc or len(desc.strip()) < 150:
        raise ScrapeError(f"{source}: job description too short or not found")


def _detect_source(domain: str) -> str:
    for kw in ("linkedin", "indeed", "glassdoor", "workday", "lever",
               "greenhouse", "ashby", "wellfound", "angel", "smartrecruiters",
               "jobvite", "icims", "taleo", "bamboohr"):
        if kw in domain:
            return kw
    return "generic"


def _job(title: str | None, company: str | None, description: str, source: str) -> dict:
    # Normalize unicode (remove zero-width spaces, etc.)
    desc = unicodedata.normalize("NFKC", description or "").strip()
    return {
        "title":       (title or "").strip() or None,
        "company":     (company or "").strip() or None,
        "description": desc,
        "source":      source,
    }
