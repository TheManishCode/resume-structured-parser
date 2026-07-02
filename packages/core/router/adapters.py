"""
packages/core/router/adapters.py

Concrete implementations of LocalModel and CloudModel.

OllamaAdapter  — local OSS model via Ollama REST API (localhost:11434)
ClaudeAdapter  — Anthropic claude-sonnet-4-6 (primary cloud reasoning)
GroqAdapter    — Groq-hosted Llama/Mixtral (rate-limit / error fallback)

All adapters are injected into ModelRouter; none are called directly
by business logic.
"""
from __future__ import annotations

import json
import logging
import os
import textwrap
from typing import Optional

import httpx

from .router import CloudModel, LocalModel

logger = logging.getLogger(__name__)


# ── Prompt shared by all cloud adapters ──────────────────────────────────────

def _build_prompt(resume_text: str, jd: str, local_result: dict | None = None) -> str:
    local_hint = ""
    if local_result and local_result.get("score") is not None:
        local_hint = (
            f"\n\n[Local pre-screen signal: score={local_result['score']:.2f}, "
            f"confidence={local_result.get('confidence', '?'):.2f}]"
        )
    return textwrap.dedent(f"""
        You are an expert technical recruiter evaluating a candidate for the
        following role. Score the resume on a 0.0–1.0 scale (1.0 = ideal match).

        ## Job Description
        {jd}

        ## Resume
        {resume_text}{local_hint}

        ## Your task
        Return a JSON object with exactly two keys:
        - "score": float between 0.0 and 1.0
        - "justification": 2-3 sentence explanation of the score

        Focus on: depth of relevant experience, technical skills match,
        seniority indicators, and red flags (consulting-only, title inflation,
        research-only background for a product role, etc.).

        Ignore: candidate name, gender markers, university prestige tier,
        graduation year, or any demographic proxy.

        Respond with ONLY the JSON object, no markdown fences.
    """).strip()


# ── Ollama (local OSS) ────────────────────────────────────────────────────────

class OllamaAdapter(LocalModel):
    """Calls a locally running Ollama server for bulk first-pass scoring.

    The local model does structured field extraction + keyword matching,
    not open-ended reasoning — it's fast and free, and sets the confidence
    threshold that determines whether cloud escalation is needed.
    """

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL    = "llama3.2"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = (base_url or os.getenv("OLLAMA_BASE_URL", self.DEFAULT_BASE_URL)).rstrip("/")
        self._model    = model or os.getenv("OLLAMA_MODEL", self.DEFAULT_MODEL)
        self._timeout  = timeout
        self._client   = httpx.AsyncClient(timeout=timeout)

    def is_available(self) -> bool:
        try:
            import httpx as _h
            r = _h.get(f"{self._base_url}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    async def score(self, resume_text: str, job_description: str) -> dict:
        prompt = _build_prompt(resume_text, job_description)
        payload = {
            "model":  self._model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        resp = await self._client.post(f"{self._base_url}/api/generate", json=payload)
        resp.raise_for_status()
        raw = resp.json().get("response", "{}")
        parsed = json.loads(raw)
        score         = float(parsed.get("score", 0.5))
        justification = str(parsed.get("justification", ""))
        # Local model confidence heuristic: how far from the uncertain midpoint
        # A score near 0.5 with a short justification → low confidence.
        word_count  = len(justification.split())
        confidence  = min(1.0, abs(score - 0.5) * 2 + min(word_count / 40, 0.4))
        return {"score": score, "confidence": round(confidence, 3), "justification": justification}


# ── Claude (primary cloud) ────────────────────────────────────────────────────

class ClaudeAdapter(CloudModel):
    """Anthropic Claude — primary cloud reasoning tier."""

    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._model   = model or os.getenv("CLAUDE_MODEL", self.DEFAULT_MODEL)
        if not self._api_key:
            logger.warning("ANTHROPIC_API_KEY not set — ClaudeAdapter will fail at runtime")
        self._client  = httpx.AsyncClient(timeout=30.0)

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def score(
        self, resume_text: str, job_description: str, local_result: dict | None = None
    ) -> dict:
        prompt = _build_prompt(resume_text, job_description, local_result)
        headers = {
            "x-api-key":         self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = await self._client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers, json=payload,
        )
        resp.raise_for_status()
        text   = resp.json()["content"][0]["text"].strip()
        parsed = json.loads(text)
        return {
            "score":         float(parsed["score"]),
            "justification": str(parsed["justification"]),
        }


# ── Groq (fallback) ───────────────────────────────────────────────────────────

class GroqAdapter(CloudModel):
    """Groq-hosted Llama/Mixtral — rate-limit / error fallback tier.

    Groq's free tier has generous RPM limits; this adapter is intentionally
    kept lightweight so it degrades gracefully under load.
    """

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self._model   = model or os.getenv("GROQ_MODEL", self.DEFAULT_MODEL)
        if not self._api_key:
            logger.warning("GROQ_API_KEY not set — GroqAdapter will fail at runtime")
        self._client  = httpx.AsyncClient(timeout=20.0)

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def score(
        self, resume_text: str, job_description: str, local_result: dict | None = None
    ) -> dict:
        prompt = _build_prompt(resume_text, job_description, local_result)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You are a technical recruiter. Respond with JSON only."},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens":  512,
            "response_format": {"type": "json_object"},
        }
        resp = await self._client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=payload,
        )
        resp.raise_for_status()
        text   = resp.json()["choices"][0]["message"]["content"].strip()
        parsed = json.loads(text)
        return {
            "score":         float(parsed["score"]),
            "justification": str(parsed["justification"]),
        }


# ── ApeKey.ai (unified AI gateway) ───────────────────────────────────────────

class ApeKeyAdapter(CloudModel):
    """ApeKey.ai unified AI API gateway — OpenAI-compatible endpoint.

    Provides access to multiple LLM providers through a single API key.
    Acts as primary cloud tier when APEKEY_AI_API_KEY is set.
    """

    DEFAULT_BASE_URL = "https://api.apekey.ai/v1"
    DEFAULT_MODEL    = "gpt-4o"

    def __init__(
        self,
        api_key:  str | None = None,
        base_url: str | None = None,
        model:    str | None = None,
    ) -> None:
        self._api_key  = api_key  or os.getenv("APEKEY_AI_API_KEY", "")
        self._base_url = (base_url or os.getenv("APEKEY_AI_BASE_URL", self.DEFAULT_BASE_URL)).rstrip("/")
        self._model    = model    or os.getenv("APEKEY_AI_MODEL", self.DEFAULT_MODEL)
        if not self._api_key:
            logger.warning("APEKEY_AI_API_KEY not set — ApeKeyAdapter will fail at runtime")
        self._client = httpx.AsyncClient(timeout=30.0)

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def score(
        self, resume_text: str, job_description: str, local_result: dict | None = None
    ) -> dict:
        prompt = _build_prompt(resume_text, job_description, local_result)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role":    "system",
                    "content": "You are an expert technical recruiter. Respond with JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature":     0.1,
            "max_tokens":      512,
            "response_format": {"type": "json_object"},
        }
        resp = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        text   = resp.json()["choices"][0]["message"]["content"].strip()
        parsed = json.loads(text)
        return {
            "score":         float(parsed["score"]),
            "justification": str(parsed["justification"]),
        }


# ── Factory ───────────────────────────────────────────────────────────────────

def build_router(retry_queue=None):
    """Build a ModelRouter from environment variables.

    Priority:
      primary  — ApeKey.ai if key set, else Claude
      fallback — Groq

    Raises ValueError if no cloud tier is configured.
    """
    from .router import ModelRouter

    local = OllamaAdapter()

    apekey = ApeKeyAdapter()
    if apekey.is_available():
        primary = apekey
        logger.info("ModelRouter: ApeKey.ai selected as primary cloud tier")
    else:
        primary = ClaudeAdapter()
        logger.info("ModelRouter: Claude selected as primary cloud tier")

    fallback = GroqAdapter()

    if not primary.is_available() and not fallback.is_available():
        raise ValueError(
            "No cloud tier configured. Set APEKEY_AI_API_KEY, ANTHROPIC_API_KEY, "
            "or GROQ_API_KEY."
        )

    return ModelRouter(local=local, primary=primary, fallback=fallback,
                       background_retry_queue=retry_queue)
