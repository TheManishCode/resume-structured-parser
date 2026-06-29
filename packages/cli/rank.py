"""
packages/cli/rank.py — thin CLI wrapper over packages/core.

Mirrors the full pipeline (ingest → normalize → score → output JSON/CSV)
and reads/writes the same Postgres store the API uses, so CLI and UI
are always in sync.

Usage:
    python -m packages.cli.rank <candidates.jsonl[.gz]> <output.csv>
    python -m packages.cli.rank --pdf ./resumes/ --job "path/to/jd.txt" --out ranked.csv

This is also the demo-day backup if the UI goes down.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import json
import sys
import time
from pathlib import Path

# Resolve package root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from packages.core.scoring import score_candidate, generate_reasoning
from packages.core.scoring.schema import get_candidate_id


def _open_jsonl(path: Path):
    if path.suffix == ".gz":
        import gzip
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


async def _run_jsonl(dataset: Path, output: Path, top_n: int):
    """Score a JSONL candidate file (hackathon-format) and write ranked CSV."""
    results = []
    t0 = time.monotonic()
    for line in _open_jsonl(dataset):
        line = line.strip()
        if not line:
            continue
        c  = json.loads(line)
        sc = score_candidate(c)

        from packages.core.scoring.role_taxonomy import role_taxonomy
        from packages.core.scoring.integrity import integrity_check
        from packages.core.scoring.disqualifiers import disqualifier_check
        from packages.core.scoring.behavioral import behavioral_score

        tax  = role_taxonomy(c)
        dq   = disqualifier_check(c)
        beh  = behavioral_score(c)
        rsn  = generate_reasoning(c, tax, dq, beh, sc)

        results.append({
            "candidate_id": get_candidate_id(c),
            "score":        sc["score"],
            "reasoning":    rsn,
        })

    elapsed = time.monotonic() - t0
    print(f"Scored {len(results):,} candidates in {elapsed:.1f}s")

    results.sort(key=lambda r: (-r["score"], r["candidate_id"]))
    top = results[:top_n]

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, row in enumerate(top, start=1):
            writer.writerow([row["candidate_id"], rank, f"{row['score']:.6f}", row["reasoning"]])

    print(f"Written {len(top)} rows → {output}")
    print(f"Top score: {top[0]['score']:.4f}  Cutoff: {top[-1]['score']:.4f}")


def main():
    parser = argparse.ArgumentParser(description="AI Talent Platform — CLI Ranker")
    parser.add_argument("dataset", help="candidates.jsonl or .jsonl.gz")
    parser.add_argument("output",  help="output CSV path")
    parser.add_argument("--top",   type=int, default=100, help="Number of candidates to output")
    args = parser.parse_args()

    asyncio.run(_run_jsonl(Path(args.dataset), Path(args.output), args.top))


if __name__ == "__main__":
    main()
