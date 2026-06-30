"""
packages/core/rag/embedder.py

Embedding layer for the RAG talent-suggestion feature.

Uses sentence-transformers (all-MiniLM-L6-v2) — 384-dim, fully offline,
no API cost. Vectors are stored in Postgres via pgvector.

The model is loaded once at process start and reused across requests.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

import numpy as np

_MODEL_NAME = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(_MODEL_NAME)


def embed(text: str) -> List[float]:
    """Return a 384-dim embedding for a single text string."""
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Batch embed for bulk resume ingestion (faster than one-by-one)."""
    model = _get_model()
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    return vecs.tolist()
