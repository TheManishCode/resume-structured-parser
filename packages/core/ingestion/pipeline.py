"""
packages/core/ingestion/pipeline.py

Ingestion pipeline: raw file bytes → (parsed_json, text_content, used_ocr)

Strategy:
  1. Try direct PDF text extraction (pdfplumber).
  2. If text is too short (likely a scanned PDF), fall back to OCR (pytesseract).
  3. Normalize extracted text into the shared candidate JSON schema.
  4. Strip bias fields before storing.

Accepted formats: PDF, DOCX.
"""
from __future__ import annotations

import io
import json
import logging
import re

logger = logging.getLogger(__name__)

_MIN_TEXT_CHARS = 200  # below this → assume scanned, run OCR


async def ingest_file(filename: str, raw: bytes) -> tuple[dict, str, bool]:
    """Return (parsed_json, text_content, used_ocr)."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        text, used_ocr = _extract_pdf(raw)
    elif ext in ("doc", "docx"):
        text, used_ocr = _extract_docx(raw), False
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    parsed = _normalize(text)
    parsed = _strip_bias_fields(parsed)
    return parsed, text, used_ocr


def _extract_pdf(raw: bytes) -> tuple[str, bool]:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        text = "\n".join(pages).strip()
        if len(text) >= _MIN_TEXT_CHARS:
            return text, False
        logger.info("PDF text too short (%d chars); falling back to OCR", len(text))
    except Exception as exc:
        logger.warning("pdfplumber failed: %s; falling back to OCR", exc)

    return _ocr_pdf(raw), True


def _ocr_pdf(raw: bytes) -> str:
    try:
        import pdf2image
        import pytesseract
        images = pdf2image.convert_from_bytes(raw)
        return "\n".join(pytesseract.image_to_string(img) for img in images)
    except Exception as exc:
        logger.error("OCR failed: %s", exc)
        return ""


def _extract_docx(raw: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as exc:
        logger.error("DOCX extraction failed: %s", exc)
        return ""


def _normalize(text: str) -> dict:
    """Best-effort extraction of structured fields from free text.

    For production, replace with a proper NLP parser or a small local model
    prompt. This stub pulls the most reliably parseable fields.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return {
        "raw_text":        text,
        "email":           _find_email(text),
        "phone":           _find_phone(text),
        "years_estimated": _estimate_yoe(text),
        "skills_raw":      _find_skills(text),
        "sections":        _split_sections(lines),
    }


def _find_email(text: str) -> str | None:
    m = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    return m.group(0) if m else None


def _find_phone(text: str) -> str | None:
    m = re.search(r"[\+\d][\d\s\-\(\)]{7,15}\d", text)
    return m.group(0).strip() if m else None


def _estimate_yoe(text: str) -> float | None:
    m = re.search(r"(\d+)\+?\s*years?\s*(?:of\s*)?experience", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    # Count unique years mentioned in date ranges
    years = set(re.findall(r"\b(20\d{2})\b", text))
    if len(years) >= 2:
        yr_list = sorted(int(y) for y in years)
        return float(yr_list[-1] - yr_list[0])
    return None


def _find_skills(text: str) -> list[str]:
    ml_keywords = [
        "python", "pytorch", "tensorflow", "nlp", "machine learning", "deep learning",
        "sql", "aws", "docker", "kubernetes", "react", "java", "golang", "rust",
        "data science", "llm", "bert", "transformer", "fastapi", "postgresql",
    ]
    found = [kw for kw in ml_keywords if kw.lower() in text.lower()]
    return found


def _split_sections(lines: list[str]) -> dict:
    section_headers = {
        "experience":  ["experience", "work history", "employment"],
        "education":   ["education", "academic"],
        "skills":      ["skills", "technical skills", "core competencies"],
        "projects":    ["projects", "personal projects"],
        "summary":     ["summary", "objective", "profile"],
    }
    sections: dict[str, list[str]] = {}
    current = "other"
    for line in lines:
        lower = line.lower()
        matched = None
        for key, headers in section_headers.items():
            if any(h in lower for h in headers):
                matched = key
                break
        if matched:
            current = matched
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return {k: "\n".join(v) for k, v in sections.items()}


def _strip_bias_fields(data: dict) -> dict:
    """Remove fields that must never influence scoring."""
    data.pop("name",  None)
    data.pop("photo", None)
    data.pop("dob",   None)
    data.pop("gender", None)
    data.pop("nationality", None)
    return data
